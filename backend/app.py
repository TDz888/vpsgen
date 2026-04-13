#!/usr/bin/env python3
"""
Singularity Club VPS Backend - Production Ready
API Server with all 30 upgrades
"""
import os
import sys
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_compress import Compress

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config
from utils.logger import logger
from utils.validators import validate_github_token, validate_tailscale_key, validate_username, validate_password
from utils.cache import cache
from utils.helpers import generate_username, generate_password
from database.db_manager import db
from services.vm_manager import vm_manager
from middleware.rate_limiter import rate_limit

# Initialize Flask app
app = Flask(__name__, static_folder='../frontend')
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB max request size

# Enable CORS
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Enable compression
if config.COMPRESS_ENABLED:
    Compress(app)
    app.config['COMPRESS_LEVEL'] = config.COMPRESS_LEVEL

# Start background threads
def start_background_tasks():
    """Start all background threads"""
    vm_manager.start_cleanup_thread()
    
    # Cache cleanup thread
    def cache_cleanup_worker():
        while True:
            time.sleep(60)
            cache.cleanup()
    
    threading.Thread(target=cache_cleanup_worker, daemon=True).start()
    logger.info("Background tasks started")

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/')
def index():
    """Serve frontend"""
    return send_from_directory('../frontend', 'index.html')

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint with system status"""
    from services.github_service import github_service
    
    health_data = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'server': request.host,
        'vms_count': len(vm_manager.get_all_vms()),
        'uptime': time.time() - start_time if 'start_time' in globals() else 0
    }
    
    return jsonify(health_data)

@app.route('/api/vps', methods=['GET'])
def get_vps():
    """Get all VMs with caching"""
    # Try cache first
    cache_key = 'vps_list'
    if config.CACHE_ENABLED:
        cached = cache.get(cache_key)
        if cached:
            logger.debug("Returning cached VM list")
            return jsonify(cached)
    
    # Get from database
    vms = vm_manager.get_all_vms()
    
    response_data = {
        'success': True,
        'vms': vms,
        'count': len(vms)
    }
    
    # Cache response
    if config.CACHE_ENABLED:
        cache.set(cache_key, response_data, config.CACHE_TTL)
    
    return jsonify(response_data)

@app.route('/api/vps/<vm_id>', methods=['GET'])
def get_vps_detail(vm_id):
    """Get single VM details"""
    vm = vm_manager.get_vm(vm_id)
    if not vm:
        return jsonify({'success': False, 'error': 'VM not found'}), 404
    
    return jsonify({'success': True, 'vm': vm})

@app.route('/api/vps/<vm_id>/export', methods=['GET'])
def export_vm_info(vm_id):
    """Export VM info as plain text"""
    vm = vm_manager.get_vm(vm_id)
    if not vm:
        return jsonify({'success': False, 'error': 'VM not found'}), 404
    
    export_text = f"""========================================
SINGULARITY CLUB VPS - {vm.get('name')}
========================================
Username:     {vm.get('username')}
Password:     {vm.get('password')}
Tailscale IP: {vm.get('tailscaleIP', 'Pending...')}
noVNC URL:    {vm.get('novncUrl', 'Pending...')}
Repository:   {vm.get('repoUrl', 'N/A')}
Workflow:     {vm.get('workflowUrl', 'N/A')}
Created:      {vm.get('createdAt')}
Expires:      {vm.get('expiresAt')}
Status:       {vm.get('status')}
========================================
"""
    
    return export_text, 200, {'Content-Type': 'text/plain; charset=utf-8'}

@app.route('/api/vps', methods=['POST'])
@rate_limit
def create_vps():
    """Create new VPS"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        github_token = data.get('githubToken', '').strip()
        tailscale_key = data.get('tailscaleKey', '').strip()
        vm_username = data.get('vmUsername', '').strip()
        vm_password = data.get('vmPassword', '').strip()
        startup_script = data.get('startupScript', '').strip()
        
        # Generate random credentials if not provided
        if not vm_username:
            vm_username = generate_username()
        if not vm_password:
            vm_password = generate_password()
        
        # Validate inputs
        valid, error = validate_username(vm_username)
        if not valid:
            return jsonify({'success': False, 'error': error}), 400
        
        valid, error = validate_password(vm_password)
        if not valid:
            return jsonify({'success': False, 'error': error}), 400
        
        # Get client IP
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Check max VMs per IP
        vm_count = db.count_vms_by_ip(client_ip, 24)  # Last 24 hours
        if vm_count >= config.MAX_VMS_PER_IP:
            return jsonify({
                'success': False, 
                'error': f'Max {config.MAX_VMS_PER_IP} VMs per day per IP'
            }), 429
        
        # Create VM
        result = vm_manager.create_vm(
            github_token, tailscale_key, vm_username, vm_password,
            creator_ip=client_ip, startup_script=startup_script
        )
        
        if result.get('success'):
            # Clear cache
            cache.delete('vps_list')
            cache.delete('stats')
            
            return jsonify(result), 201
        else:
            return jsonify(result), 400
        
    except Exception as e:
        logger.error(f"Create VPS error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/vps', methods=['DELETE'])
def delete_vps():
    """Delete single VPS"""
    vm_id = request.args.get('id')
    if not vm_id:
        return jsonify({'success': False, 'error': 'Missing VM ID'}), 400
    
    deleted = vm_manager.delete_vm(vm_id)
    
    if deleted:
        cache.delete('vps_list')
        cache.delete('stats')
        return jsonify({'success': True, 'message': f'VM {vm_id} deleted'})
    else:
        return jsonify({'success': False, 'error': 'VM not found'}), 404

@app.route('/api/vps/batch-delete', methods=['POST'])
def batch_delete_vps():
    """Delete multiple VMs"""
    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify({'success': False, 'error': 'No IDs provided'}), 400
    
    vm_ids = data['ids']
    count = vm_manager.delete_batch_vms(vm_ids)
    
    cache.delete('vps_list')
    cache.delete('stats')
    
    return jsonify({'success': True, 'deleted': count})

@app.route('/api/vps/<vm_id>/status', methods=['PUT'])
def update_vm_status(vm_id):
    """Update VM status"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    status = data.get('status')
    progress = data.get('progress')
    
    updated = db.update_vm_status(vm_id, status, progress)
    
    if updated:
        cache.delete('vps_list')
        cache.delete('stats')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'VM not found'}), 404

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get statistics with caching"""
    cache_key = 'stats'
    if config.CACHE_ENABLED:
        cached = cache.get(cache_key)
        if cached:
            return jsonify(cached)
    
    stats = vm_manager.get_stats()
    
    response_data = {'success': True, 'stats': stats}
    
    if config.CACHE_ENABLED:
        cache.set(cache_key, response_data, config.CACHE_TTL)
    
    return jsonify(response_data)

@app.route('/api/validate/github', methods=['POST'])
def validate_github():
    """Validate GitHub token"""
    from services.github_service import github_service
    
    data = request.get_json()
    token = data.get('token', '').strip()
    
    valid, result = github_service.validate_token(token)
    
    if valid:
        return jsonify({
            'success': True,
            'valid': True,
            'username': result['username'],
            'scopes': result['scopes']
        })
    else:
        return jsonify({
            'success': True,
            'valid': False,
            'error': result
        })

@app.route('/api/validate/tailscale', methods=['POST'])
def validate_tailscale():
    """Validate Tailscale key"""
    from services.tailscale_service import tailscale_service
    
    data = request.get_json()
    key = data.get('key', '').strip()
    
    valid, message = tailscale_service.validate_key(key)
    
    return jsonify({
        'success': True,
        'valid': valid,
        'message': message
    })

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'success': False, 'error': 'Method not allowed'}), 405

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal server error: {e}")
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

# ============================================
# MAIN ENTRY POINT
# ============================================
if __name__ == '__main__':
    # Record start time
    start_time = time.time()
    
    # Create required directories
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    
    # Start background tasks
    start_background_tasks()
    
    # Log startup
    logger.info("=" * 60)
    logger.info("🚀 Singularity Club VPS Backend v2.0")
    logger.info("=" * 60)
    logger.info(f"📍 Server: http://{config.HOST}:{config.PORT}")
    logger.info(f"📁 Database: {config.DATABASE_PATH}")
    logger.info(f"📊 Cache TTL: {config.CACHE_TTL}s")
    logger.info(f"⏱️  VM Lifetime: {config.VM_LIFETIME_HOURS}h")
    logger.info(f"🚦 Rate Limit: {config.RATE_LIMIT_PER_HOUR}/hour")
    logger.info("=" * 60)
    
    # Run Flask app
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG, threaded=True)
