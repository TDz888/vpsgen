# backend/app.py
# Singularity Club - Virtual Machine Platform
# Tạo VM thật với GitHub Actions

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import time
import random
import string
import base64
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# Lưu trữ VM trong bộ nhớ
vms = {}
vm_counter = 0

# ============================================ #
# HÀM TIỆN ÍCH
# ============================================ #
def generate_strong_password():
    """Tạo mật khẩu mạnh 23 ký tự"""
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
    password.extend(random.choices(all_chars, k=19))
    random.shuffle(password)
    return ''.join(password)

def generate_username():
    """Tạo username 8 ký tự"""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=8))

def generate_repo_name():
    """Tạo tên repository ngẫu nhiên"""
    return f'vm-{int(time.time())}-{random.randint(1000, 9999)}'

def create_workflow_content(username, password):
    """Tạo nội dung workflow GitHub Actions"""
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
      
      - name: Install Python
        shell: pwsh
        run: |
          Write-Host "Installing Python..."
          $pythonUrl = "https://www.python.org/ftp/python/3.11.0/python-3.11.0-amd64.exe"
          $installer = "$env:TEMP\\python-installer.exe"
          Invoke-WebRequest -Uri $pythonUrl -OutFile $installer
          Start-Process -FilePath $installer -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait -NoNewWindow
          Write-Host "Python installed"
      
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

def create_workflow_file(token, owner, repo, username, password):
    """Tạo workflow file trong repository"""
    workflow_content = create_workflow_content(username, password)
    encoded_content = base64.b64encode(workflow_content.encode()).decode()
    
    url = f'https://api.github.com/repos/{owner}/{repo}/contents/.github/workflows/create-vm.yml'
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json'
    }
    data = {
        'message': 'Add GitHub Actions workflow for VM creation',
        'content': encoded_content,
        'branch': 'main'
    }
    
    response = requests.put(url, headers=headers, json=data)
    return response.status_code == 201

def trigger_workflow(token, owner, repo, tailscale_key):
    """Trigger GitHub Actions workflow"""
    url = f'https://api.github.com/repos/{owner}/{repo}/actions/workflows/create-vm.yml/dispatches'
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json'
    }
    data = {
        'ref': 'main',
        'inputs': {
            'tailscale_key': tailscale_key
        }
    }
    
    response = requests.post(url, headers=headers, json=data)
    return response.status_code == 204

def get_workflow_runs(token, owner, repo):
    """Lấy thông tin workflow runs"""
    url = f'https://api.github.com/repos/{owner}/{repo}/actions/runs'
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('workflow_runs', [])
    return []

def get_workflow_logs(token, owner, repo, run_id):
    """Lấy logs của workflow run"""
    url = f'https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/logs'
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    return ""

# ============================================ #
# API ENDPOINTS
# ============================================ #
@app.route('/api/vps', methods=['GET'])
def get_vms():
    return jsonify({'success': True, 'vms': list(vms.values())})

@app.route('/api/vps', methods=['DELETE'])
def delete_vm():
    vm_id = request.args.get('id')
    if vm_id and vm_id in vms:
        del vms[vm_id]
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Không tìm thấy VM'})

@app.route('/api/vps', methods=['POST'])
def create_vm():
    global vm_counter
    
    data = request.get_json()
    github_token = data.get('githubToken', '')
    tailscale_key = data.get('tailscaleKey', '')
    username = data.get('vmUsername', '')
    password = data.get('vmPassword', '')
    
    if not github_token:
        return jsonify({'success': False, 'error': 'Vui lòng nhập GitHub Token'})
    
    if not tailscale_key:
        return jsonify({'success': False, 'error': 'Vui lòng nhập Tailscale Key'})
    
    if not username:
        username = generate_username()
    if not password:
        password = generate_strong_password()
    
    repo_url = None
    workflow_url = None
    status = 'creating'
    error_msg = None
    owner = None
    repo_name = None
    run_id = None
    
    headers = {
        'Authorization': f'Bearer {github_token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'Singularity-Club'
    }
    
    try:
        # Bước 1: Xác thực GitHub Token
        print("🔑 Bước 1: Xác thực GitHub token...")
        user_res = requests.get('https://api.github.com/user', headers=headers)
        
        if user_res.status_code != 200:
            status = 'failed'
            error_msg = 'Token GitHub không hợp lệ hoặc đã hết hạn'
        else:
            user = user_res.json()
            owner = user.get('login')
            print(f"✅ Đã xác thực: {owner}")
            
            # Bước 2: Tạo repository
            repo_name = generate_repo_name()
            print(f"📁 Bước 2: Tạo repository {repo_name}...")
            
            create_data = {
                'name': repo_name,
                'description': f'Virtual Machine created by {username}',
                'private': False,
                'auto_init': True
            }
            
            create_res = requests.post(
                'https://api.github.com/user/repos',
                headers=headers,
                json=create_data
            )
            
            if create_res.status_code == 201:
                repo = create_res.json()
                repo_url = repo.get('html_url')
                print(f"✅ Repository đã tạo: {repo_url}")
                
                # Bước 3: Tạo workflow file
                print("📝 Bước 3: Tạo workflow file...")
                time.sleep(3)  # Đợi GitHub index repository
                
                if create_workflow_file(github_token, owner, repo_name, username, password):
                    print("✅ Workflow file đã tạo")
                    
                    # Bước 4: Trigger workflow
                    print("🚀 Bước 4: Trigger GitHub Actions...")
                    time.sleep(2)
                    
                    if trigger_workflow(github_token, owner, repo_name, tailscale_key):
                        print("✅ Workflow đã được trigger")
                        workflow_url = f'https://github.com/{owner}/{repo_name}/actions'
                        status = 'running'
                        
                        # Lấy run ID để monitor
                        time.sleep(3)
                        runs = get_workflow_runs(github_token, owner, repo_name)
                        if runs:
                            run_id = runs[0].get('id')
                            print(f"📋 Run ID: {run_id}")
                    else:
                        status = 'failed'
                        error_msg = 'Không thể trigger workflow'
                else:
                    status = 'failed'
                    error_msg = 'Không thể tạo workflow file'
            else:
                status = 'failed'
                error_msg = create_res.json().get('message', 'Không thể tạo repository')
                
    except Exception as e:
        status = 'failed'
        error_msg = str(e)
        print(f"❌ Lỗi: {error_msg}")
    
    vm_counter += 1
    new_vm = {
        'id': str(vm_counter),
        'name': repo_name or f'vm-{int(time.time())}',
        'owner': owner,
        'username': username,
        'password': password,
        'status': status,
        'repoUrl': repo_url,
        'workflowUrl': workflow_url,
        'runId': run_id,
        'error': error_msg,
        'tailscaleIP': None,
        'novncUrl': None,
        'createdAt': datetime.now().isoformat(),
        'expiresAt': (datetime.now() + timedelta(hours=6)).isoformat()
    }
    
    vms[new_vm['id']] = new_vm
    
    if status == 'running':
        return jsonify({
            'success': True,
            **new_vm,
            'message': f'✅ VM "{username}" đã được khởi tạo! Đang chạy trên GitHub Actions...'
        })
    else:
        return jsonify({
            'success': False,
            'error': error_msg,
            **new_vm
        })

# ============================================ #
# MONITOR WORKFLOW - Lấy IP và noVNC
# ============================================ #
@app.route('/api/monitor/<vm_id>', methods=['GET'])
def monitor_vm(vm_id):
    """Lấy thông tin IP và noVNC từ logs"""
    if vm_id not in vms:
        return jsonify({'success': False, 'error': 'Không tìm thấy VM'})
    
    vm = vms[vm_id]
    if not vm.get('repoUrl') or not vm.get('owner') or not vm.get('name'):
        return jsonify({'success': False, 'error': 'Thiếu thông tin repository'})
    
    # Cần lấy token từ đâu đó - tạm thời không có
    # Bạn cần lưu token hoặc dùng cách khác
    return jsonify({'success': False, 'error': 'Cần cấu hình token để monitor'})

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'vms_count': len(vms)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
