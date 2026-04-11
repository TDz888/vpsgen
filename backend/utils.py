# backend/utils.py
# Các hàm xử lý logic, GitHub API, monitor

import re
import time
import random
import string
import base64
import threading
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any

# Import config
from config import get_config

Config = get_config()

# Setup logger
logger = logging.getLogger(__name__)

# ============================================ #
# HÀM TIỆN ÍCH CƠ BẢN
# ============================================ #

def generate_username(length: int = 8) -> str:
    """Tạo username ngẫu nhiên"""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=length))

def generate_password(length: int = 16) -> str:
    """Tạo password mạnh ngẫu nhiên"""
    upper = string.ascii_uppercase
    lower = string.ascii_lowercase
    digits = string.digits
    special = '!@#$%^&*'
    all_chars = upper + lower + digits + special
    
    password = [
        random.choice(upper),
        random.choice(lower),
        random.choice(digits),
        random.choice(special)
    ]
    password.extend(random.choices(all_chars, k=length - 4))
    random.shuffle(password)
    return ''.join(password)

def generate_repo_name() -> str:
    """Tạo tên repository ngẫu nhiên"""
    timestamp = int(time.time())
    random_suffix = random.randint(1000, 9999)
    return f'vm-{timestamp}-{random_suffix}'

def format_countdown(seconds: int) -> str:
    """Format thời gian đếm ngược"""
    if seconds <= 0:
        return "Đã hết hạn"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours}h {minutes}m {secs}s"

def calculate_expiry(hours: int = Config.VM_EXPIRE_HOURS) -> datetime:
    """Tính thời gian hết hạn"""
    return datetime.now() + timedelta(hours=hours)

# ============================================ #
# GITHUB API HANDLERS
# ============================================ #

class GitHubAPI:
    """Xử lý tất cả các cuộc gọi GitHub API"""
    
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Singularity-Club/1.0'
        }
    
    def verify_token(self) -> Tuple[bool, Optional[Dict]]:
        """Xác thực GitHub token"""
        try:
            response = requests.get(
                f'{Config.GITHUB_API}/user',
                headers=self.headers,
                timeout=Config.GITHUB_TIMEOUT
            )
            if response.status_code == 200:
                return True, response.json()
            logger.error(f"Token verification failed: {response.status_code}")
            return False, None
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return False, None
    
    def create_repository(self, name: str, description: str) -> Tuple[bool, Optional[Dict]]:
        """Tạo repository mới"""
        try:
            data = {
                'name': name,
                'description': description,
                'private': False,
                'auto_init': True
            }
            response = requests.post(
                f'{Config.GITHUB_API}/user/repos',
                headers=self.headers,
                json=data,
                timeout=Config.GITHUB_TIMEOUT
            )
            if response.status_code == 201:
                return True, response.json()
            logger.error(f"Create repo failed: {response.status_code}")
            return False, None
        except Exception as e:
            logger.error(f"Create repo error: {e}")
            return False, None
    
    def create_workflow_file(self, owner: str, repo: str, username: str, password: str) -> bool:
        """Tạo workflow file trong repository"""
        try:
            content = self._generate_workflow_content(username, password)
            encoded = base64.b64encode(content.encode()).decode()
            
            data = {
                'message': 'Add GitHub Actions workflow for VM creation',
                'content': encoded,
                'branch': Config.WORKFLOW_BRANCH
            }
            
            response = requests.put(
                f'{Config.GITHUB_API}/repos/{owner}/{repo}/contents/{Config.WORKFLOW_FILE_PATH}',
                headers={**self.headers, 'Content-Type': 'application/json'},
                json=data,
                timeout=Config.GITHUB_TIMEOUT
            )
            return response.status_code == 201
        except Exception as e:
            logger.error(f"Create workflow error: {e}")
            return False
    
    def trigger_workflow(self, owner: str, repo: str, tailscale_key: str) -> bool:
        """Trigger GitHub Actions workflow"""
        try:
            data = {
                'ref': Config.WORKFLOW_BRANCH,
                'inputs': {'tailscale_key': tailscale_key}
            }
            response = requests.post(
                f'{Config.GITHUB_API}/repos/{owner}/{repo}/actions/workflows/create-vm.yml/dispatches',
                headers={**self.headers, 'Content-Type': 'application/json'},
                json=data,
                timeout=Config.GITHUB_TIMEOUT
            )
            return response.status_code == 204
        except Exception as e:
            logger.error(f"Trigger workflow error: {e}")
            return False
    
    def get_workflow_runs(self, owner: str, repo: str, per_page: int = 5) -> list:
        """Lấy danh sách workflow runs"""
        try:
            response = requests.get(
                f'{Config.GITHUB_API}/repos/{owner}/{repo}/actions/runs?per_page={per_page}',
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get('workflow_runs', [])
            return []
        except Exception as e:
            logger.error(f"Get workflow runs error: {e}")
            return []
    
    def get_workflow_logs(self, owner: str, repo: str, run_id: int) -> str:
        """Lấy logs từ workflow run"""
        try:
            response = requests.get(
                f'{Config.GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/logs',
                headers=self.headers,
                timeout=30
            )
            if response.status_code == 200:
                return response.text
            return ""
        except Exception as e:
            logger.error(f"Get workflow logs error: {e}")
            return ""
    
    @staticmethod
    def _generate_workflow_content(username: str, password: str) -> str:
        """Tạo nội dung workflow file"""
        return f'''name: Create Windows VM

on:
  workflow_dispatch:
    inputs:
      tailscale_key:
        description: 'Tailscale Auth Key'
        required: true
        type: string

jobs:
  create-vm:
    runs-on: windows-latest
    timeout-minutes: 480
    
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Install Tailscale
        shell: pwsh
        run: |
          Write-Host "Installing Tailscale..."
          $url = "https://pkgs.tailscale.com/stable/tailscale-setup-latest.exe"
          $installer = "$env:TEMP\\tailscale.exe"
          Invoke-WebRequest -Uri $url -OutFile $installer
          Start-Process -FilePath $installer -ArgumentList "/S" -Wait -NoNewWindow
          Write-Host "Tailscale installed"
      
      - name: Connect Tailscale
        shell: pwsh
        run: |
          Write-Host "Connecting to Tailscale..."
          & "C:\\Program Files\\Tailscale\\Tailscale.exe" up --auth-key "${{{{ github.event.inputs.tailscale_key }}}}"
          Start-Sleep -Seconds 15
          $ip = & "C:\\Program Files\\Tailscale\\Tailscale.exe" ip -4
          echo "TAILSCALE_IP=$ip" >> $env:GITHUB_ENV
          Write-Host "Tailscale IP: $ip"
      
      - name: Setup noVNC
        shell: pwsh
        run: |
          Write-Host "Setting up noVNC..."
          git clone https://github.com/novnc/noVNC.git C:\\novnc
          git clone https://github.com/novnc/websockify.git C:\\websockify
          Write-Host "Starting noVNC server..."
          Start-Process -NoNewWindow -FilePath python -ArgumentList "C:\\websockify\\websockify.py", "--web=C:\\novnc", "6080", "localhost:3389"
          New-NetFirewallRule -DisplayName "noVNC" -Direction Inbound -Protocol TCP -LocalPort 6080 -Action Allow
          Write-Host "noVNC started on port 6080"
      
      - name: Configure Windows RDP
        shell: pwsh
        run: |
          Write-Host "Configuring Windows RDP..."
          Set-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server" -Name "fDenyTSConnections" -Value 0
          Set-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp" -Name "UserAuthentication" -Value 0
          net user {username} {password} /add
          net localgroup Administrators {username} /add
          net localgroup "Remote Desktop Users" {username} /add
          New-NetFirewallRule -DisplayName "RDP" -Direction Inbound -Protocol TCP -LocalPort 3389 -Action Allow
          Write-Host "RDP configured with user: {username}"
      
      - name: Display Connection Info
        shell: pwsh
        run: |
          Write-Host "=================================================="
          Write-Host "WINDOWS VM READY"
          Write-Host "=================================================="
          Write-Host "Tailscale IP: $env:TAILSCALE_IP"
          Write-Host "Username: {username}"
          Write-Host "Password: {password}"
          Write-Host "noVNC URL: http://$env:TAILSCALE_IP:6080/vnc.html"
          Write-Host "=================================================="
      
      - name: Keep VM Alive
        shell: pwsh
        run: |
          $end = (Get-Date).AddHours(6)
          Write-Host "VM will run for 6 hours, expires at: $end"
          while ((Get-Date) -lt $end) {{
            $remaining = [math]::Round(($end - (Get-Date)).TotalMinutes)
            Write-Host "VM running... expires in $remaining minutes"
            Start-Sleep -Seconds 300
          }}
          Write-Host "VM expired. Shutting down..."
'''

# ============================================ #
# VM MONITOR
# ============================================ #

class VMMonitor:
    """Theo dõi tiến trình tạo VM"""
    
    def __init__(self, vm_id: str, token: str, owner: str, repo: str, callback=None):
        self.vm_id = vm_id
        self.token = token
        self.owner = owner
        self.repo = repo
        self.callback = callback
        self.running = True
        self.attempts = 0
        self.max_attempts = Config.VM_CREATION_TIMEOUT // Config.MONITOR_INTERVAL
    
    def start(self):
        """Bắt đầu monitor trong thread riêng"""
        thread = threading.Thread(target=self._monitor, daemon=True)
        thread.start()
        return thread
    
    def stop(self):
        """Dừng monitor"""
        self.running = False
    
    def _monitor(self):
        """Vòng lặp monitor"""
        github = GitHubAPI(self.token)
        
        while self.running and self.attempts < self.max_attempts:
            time.sleep(Config.MONITOR_INTERVAL)
            self.attempts += 1
            
            try:
                runs = github.get_workflow_runs(self.owner, self.repo, 1)
                if not runs:
                    continue
                
                latest_run = runs[0]
                status = latest_run.get('status')
                conclusion = latest_run.get('conclusion')
                
                if status == 'completed' and conclusion == 'success':
                    # Lấy logs để trích xuất IP
                    logs = github.get_workflow_logs(self.owner, self.repo, latest_run.get('id'))
                    ip_match = re.search(Config.IP_PATTERN, logs)
                    
                    result = {
                        'status': 'running',
                        'tailscaleIP': ip_match.group(1) if ip_match else None,
                        'novncUrl': f'http://{ip_match.group(1)}:6080/vnc.html' if ip_match else None,
                        'completed': True
                    }
                    
                    if self.callback:
                        self.callback(self.vm_id, result)
                    break
                    
                elif status == 'completed' and conclusion != 'success':
                    result = {
                        'status': 'failed',
                        'error': f'Workflow {conclusion}',
                        'completed': True
                    }
                    if self.callback:
                        self.callback(self.vm_id, result)
                    break
                    
                elif status == 'in_progress':
                    # Cập nhật progress
                    progress = min(95, 20 + self.attempts * 2)
                    if self.callback:
                        self.callback(self.vm_id, {'progress': progress})
                        
            except Exception as e:
                logger.error(f"Monitor error for {self.vm_id}: {e}")
        
        if self.attempts >= self.max_attempts:
            if self.callback:
                self.callback(self.vm_id, {
                    'status': 'timeout',
                    'error': 'Quá thời gian chờ (6 phút)',
                    'completed': True
                })

# ============================================ #
# LOGGING SETUP
# ============================================ #

def setup_logging():
    """Cấu hình logging"""
    import os
    
    # Tạo thư mục logs nếu chưa có
    log_dir = os.path.dirname(Config.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Cấu hình logging
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(Config.LOG_FILE),
            logging.StreamHandler()
        ]
    )
    
    # Rotating file handler
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=Config.LOG_MAX_BYTES,
        backupCount=Config.LOG_BACKUP_COUNT
    )
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(logging.StreamHandler())
    
    return logger

# ============================================ #
# VALIDATION FUNCTIONS
# ============================================ #

def validate_input(github_token: str, tailscale_key: str, username: str, password: str) -> Tuple[bool, str]:
    """Kiểm tra dữ liệu đầu vào"""
    if not github_token or len(github_token.strip()) < 10:
        return False, Config.MESSAGES['missing_token']
    
    if not tailscale_key or len(tailscale_key.strip()) < 10:
        return False, Config.MESSAGES['missing_tailscale']
    
    if username and len(username) > 50:
        return False, "Tên đăng nhập quá dài (tối đa 50 ký tự)"
    
    return True, "OK"

def sanitize_input(text: str) -> str:
    """Làm sạch input để tránh injection"""
    if not text:
        return ""
    # Loại bỏ ký tự đặc biệt nguy hiểm
    dangerous_chars = ['<', '>', '&', '"', "'", ';', '`', '$', '(', ')']
    for char in dangerous_chars:
        text = text.replace(char, '')
    return text.strip()

# ============================================ #
# RESPONSE HELPERS
# ============================================ #

def success_response(data: Any = None, message: str = None) -> Dict:
    """Tạo response thành công"""
    response = {'success': True}
    if data:
        response.update(data)
    if message:
        response['message'] = message
    return response

def error_response(error: str, code: int = 400) -> Dict:
    """Tạo response lỗi"""
    return {
        'success': False,
        'error': error,
        'code': code
    }
