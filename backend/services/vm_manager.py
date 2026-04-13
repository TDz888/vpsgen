"""
VM Lifecycle Manager
"""
import threading
import time
from datetime import datetime
from utils.logger import logger
from utils.helpers import calculate_expiry, generate_id, generate_repo_name
from database.db_manager import db
from services.github_service import github_service
from services.tailscale_service import tailscale_service
from config import config

class VMManager:
    """Manage VM lifecycle"""
    
    def __init__(self):
        self._cleanup_thread = None
        self._running = False
    
    def start_cleanup_thread(self):
        """Start background cleanup thread"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        
        self._running = True
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        logger.info("VM cleanup thread started")
    
    def _cleanup_worker(self):
        """Background worker for cleaning expired VMs"""
        while self._running:
            try:
                time.sleep(config.VM_CLEANUP_INTERVAL)
                expired_count = db.cleanup_expired()
                if expired_count > 0:
                    logger.info(f"Cleaned up {expired_count} expired VMs")
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")
    
    def stop_cleanup_thread(self):
        """Stop cleanup thread"""
        self._running = False
        logger.info("VM cleanup thread stopped")
    
    def create_vm(self, github_token, tailscale_key, vm_username, vm_password, creator_ip=None, startup_script=None):
        """Create a new VM - Full async flow"""
        
        # Step 1: Validate inputs
        from utils.validators import validate_github_token, validate_tailscale_key
        
        valid, error = validate_github_token(github_token)
        if not valid:
            return {'success': False, 'error': error}
        
        valid, error = validate_tailscale_key(tailscale_key)
        if not valid:
            return {'success': False, 'error': error}
        
        # Step 2: Validate GitHub token with API
        valid, result = github_service.validate_token(github_token)
        if not valid:
            return {'success': False, 'error': result}
        
        github_user = result['username']
        
        # Step 3: Check rate limit (if enabled)
        if config.RATE_LIMIT_ENABLED and creator_ip:
            allowed, count, reset_at = db.check_rate_limit(creator_ip, config.RATE_LIMIT_PER_HOUR)
            if not allowed:
                return {
                    'success': False, 
                    'error': f'Rate limit exceeded. Max {config.RATE_LIMIT_PER_HOUR} VMs per hour.'
                }
        
        # Step 4: Generate VM data
        vm_id = generate_id(8)
        vm_name = f"vps-{vm_username}-{vm_id}"
        repo_name = generate_repo_name(vm_username)
        
        # Step 5: Create repository
        repo_result, error = github_service.create_repository(
            github_token, 
            repo_name,
            f
