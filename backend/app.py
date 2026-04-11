#!/usr/bin/env python3
# backend/app.py - Singularity Club Backend
# Sử dụng utils.py để xử lý logic

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import logging
from datetime import datetime

# Import các module đã tách
from config import get_config, Config
from utils import (
    generate_username, generate_password, generate_repo_name,
    GitHubAPI, VMMonitor, setup_logging,
    validate_input, sanitize_input,
    success_response, error_response,
    calculate_expiry
)

# ============================================ #
# KHỞI TẠO APP
# ============================================ #

# Setup logging
logger = setup_logging()

# Load config
config = get_config()

# Khởi tạo Flask app
app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# Lưu trữ dữ liệu (dùng dict, có thể thay bằng database sau)
vms = {}
vm_counter = 0
monitors = {}

# ============================================ #
# CALLBACK CHO MONITOR
# ============================================ #

def on_vm_update(vm_id: str, update_data: dict):
    """Callback khi monitor cập nhật trạng thái VM"""
    if vm_id in vms:
        if 'status' in update_data:
            vms[vm_id]['status'] = update_data['status']
        if 'tailscaleIP' in update_data:
            vms[vm_id]['tailscaleIP'] = update_data['tailscaleIP']
        if 'novncUrl' in update_data:
            vms[vm_id]['novncUrl'] = update_data['novncUrl']
        if 'progress' in update_data:
            vms[vm_id]['progress'] = update_data['progress']
        if 'error' in update_data:
            vms[vm_id]['error'] = update_data['error']
        
        logger.info(f"VM {vm_id} updated: {vms[vm_id]['status']}")
        
        # Nếu hoàn tất, xóa monitor khỏi danh sách
        if update_data.get('completed'):
            if vm_id in monitors:
                del monitors[vm_id]

# ============================================ #
# API ENDPOINTS
# ============================================ #

@app.route('/')
def serve_frontend():
    """Phục vụ frontend"""
    return send_from_directory('../frontend', 'index.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    """Kiểm tra sức khỏe backend"""
    return jsonify(success_response({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': Config.API_VERSION,
        'vms_count': len(vms),
        'monitors_count': len(monitors)
    }))

@app.route('/api/vps', methods=['GET'])
def get_vms():
    """Lấy danh sách VM"""
    return jsonify(success_response({
        'vms': list(vms.values()),
        'timestamp': datetime.now().isoformat()
    }))

@app.route('/api/vps', methods=['DELETE'])
def delete_vm():
    """Xóa VM"""
    vm_id = request.args.get('id')
    
    if not vm_id or vm_id not in vms:
        return jsonify(error_response(Config.MESSAGES['vm_not_found'], 404))
    
    # Dừng monitor nếu đang chạy
    if vm_id in monitors:
        monitors[vm_id].stop()
        del monitors[vm_id]
    
    del vms[vm_id]
    logger.info(f"VM {vm_id} deleted")
    
    return jsonify(success_response(message=Config.MESSAGES['vm_deleted']))

@app.route('/api/vps', methods=['POST'])
def create_vm():
    """Tạo VM mới"""
    global vm_counter
    
    data = request.get_json()
    github_token = sanitize_input(data.get('githubToken', ''))
    tailscale_key = sanitize_input(data.get('tailscaleKey', ''))
    username = sanitize_input(data.get('vmUsername', ''))
    password = sanitize_input(data.get('vmPassword', ''))
    
    # Validate input
    is_valid, error_msg = validate_input(github_token, tailscale_key, username, password)
    if not is_valid:
        return jsonify(error_response(error_msg))
    
    # Tạo username/password mặc định
    if not username:
        username = generate_username()
    if not password:
        password = generate_password()
    
    logger.info(f"Creating VM for user: {username}")
    
    # Khởi tạo GitHub API handler
    github = GitHubAPI(github_token)
    
    # Xác thực token
    token_valid, user_info = github.verify_token()
    if not token_valid:
        logger.error("Invalid GitHub token")
        return jsonify(error_response(Config.MESSAGES['invalid_token']))
    
    owner = user_info.get('login')
    repo_name = generate_repo_name()
    
    # Tạo repository
    repo_success, repo_data = github.create_repository(repo_name, f'VM by {username}')
    if not repo_success:
        logger.error(f"Failed to create repo: {repo_name}")
        return jsonify(error_response(Config.MESSAGES['create_repo_failed']))
    
    repo_url = repo_data.get('html_url')
    logger.info(f"Repository created: {repo_url}")
    
    # Đợi GitHub xử lý
    time.sleep(2)
    
    # Tạo workflow file
    workflow_success = github.create_workflow_file(owner, repo_name, username, password)
    if not workflow_success:
        logger.error("Failed to create workflow file")
        return jsonify(error_response(Config.MESSAGES['create_workflow_failed']))
    
    logger.info("Workflow file created")
    
    # Đợi GitHub index workflow
    time.sleep(2)
    
    # Trigger workflow
    trigger_success = github.trigger_workflow(owner, repo_name, tailscale_key)
    if not trigger_success:
        logger.error("Failed to trigger workflow")
        return jsonify(error_response(Config.MESSAGES['trigger_failed']))
    
    logger.info("Workflow triggered")
    
    # Lấy run ID (nếu có)
    run_id = None
    try:
        time.sleep(3)
        runs = github.get_workflow_runs(owner, repo_name, 1)
        if runs:
            run_id = runs[0].get('id')
            logger.info(f"Run ID: {run_id}")
    except Exception as e:
        logger.error(f"Error getting run ID: {e}")
    
    # Tạo VM record
    vm_counter += 1
    expires_at = calculate_expiry()
    new_vm = {
        'id': str(vm_counter),
        'name': repo_name,
        'owner': owner,
        'username': username,
        'password': password,
        'status': 'creating',
        'progress': 10,
        'repoUrl': repo_url,
        'workflowUrl': f'https://github.com/{owner}/{repo_name}/actions',
        'runId': run_id,
        'tailscaleIP': None,
        'novncUrl': None,
        'createdAt': datetime.now().isoformat(),
        'expiresAt': expires_at.isoformat(),
        'error': None
    }
    
    vms[new_vm['id']] = new_vm
    
    # Bắt đầu monitor nếu có run_id
    if run_id:
        monitor = VMMonitor(
            vm_id=new_vm['id'],
            token=github_token,
            owner=owner,
            repo=repo_name,
            callback=on_vm_update
        )
        monitors[new_vm['id']] = monitor
        monitor.start()
        logger.info(f"Monitor started for VM {new_vm['id']}")
    
    return jsonify(success_response(
        data=new_vm,
        message=f'✅ VM "{username}" đang được tạo! Quá trình tạo mất 3-5 phút.'
    ))

# ============================================ #
# MAIN
# ============================================ #

if __name__ == '__main__':
    print("")
    print("=" * 60)
    print("🚀 SINGULARITY CLUB BACKEND")
    print("=" * 60)
    print(f"📡 Server: http://{Config.HOST}:{Config.PORT}")
    print(f"🔗 API: http://{Config.HOST}:{Config.PORT}/api/vps")
    print(f"💚 Health: http://{Config.HOST}:{Config.PORT}/api/health")
    print(f"📝 Log file: {Config.LOG_FILE}")
    print("=" * 60)
    print("⚠️  Nhấn Ctrl+C để dừng server")
    print("=" * 60)
    print("")
    
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, threaded=True)
