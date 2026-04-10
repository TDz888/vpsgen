#!/usr/bin/env python3
# backend/app.py - Singularity Club Backend
# Hỗ trợ Cloudflare Tunnel cho noVNC

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import json
import time
import random
import string
import base64
import re
import threading
import subprocess
import os
import logging
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# ============================================ #
# CẤU HÌNH
# ============================================ #
VERSION = "PREMIUM 1.0"
BUILD_DATE = "2026-04-11"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lưu trữ
vms = {}
vm_counter = 0
monitor_threads = {}
cloudflare_tunnels = {}

# ============================================ #
# HÀM TIỆN ÍCH
# ============================================ #
def generate_username():
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(random.choices(chars, k=8))

def generate_password():
    upper = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
    lower = 'abcdefghijkmnopqrstuvwxyz'
    numbers = '0123456789'
    special = '!@#$%^&*'
    all_chars = upper + lower + numbers + special
    password = [random.choice(upper), random.choice(lower), random.choice(numbers), random.choice(special)]
    password.extend(random.choices(all_chars, k=random.randint(12, 16)))
    random.shuffle(password)
    return ''.join(password)

def generate_repo_name():
    return f'vm-{int(time.time())}-{random.randint(1000, 9999)}'

def generate_workflow_content(username, password):
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
      
      - name: Connect Tailscale
        shell: pwsh
        run: |
          & "C:\\Program Files\\Tailscale\\Tailscale.exe" up --auth-key "${{{{ github.event.inputs.tailscale_key }}}}"
          Start-Sleep -Seconds 15
          $ip = & "C:\\Program Files\\Tailscale\\Tailscale.exe" ip -4
          echo "TAILSCALE_IP=$ip" >> $env:GITHUB_ENV
          Write-Host "Tailscale IP: $ip"
      
      - name: Setup Windows
        shell: pwsh
        run: |
          net user {username} {password} /add
          net localgroup Administrators {username} /add
          net localgroup "Remote Desktop Users" {username} /add
          New-NetFirewallRule -DisplayName "RDP" -Direction Inbound -Protocol TCP -LocalPort 3389 -Action Allow
      
      - name: Setup noVNC
        shell: pwsh
        run: |
          git clone https://github.com/novnc/noVNC.git C:\\novnc
          git clone https://github.com/novnc/websockify.git C:\\websockify
          Start-Process -NoNewWindow -FilePath python -ArgumentList "C:\\websockify\\websockify.py", "--web=C:\\novnc", "6080", "localhost:3389"
          New-NetFirewallRule -DisplayName "noVNC" -Direction Inbound -Protocol TCP -LocalPort 6080 -Action Allow
      
      - name: Display Info
        shell: pwsh
        run: |
          Write-Host "=================================================="
          Write-Host "WINDOWS VM READY"
          Write-Host "Tailscale IP: $env:TAILSCALE_IP"
          Write-Host "Username: {username}"
          Write-Host "Password: {password}"
          Write-Host "noVNC URL: http://$env:TAILSCALE_IP:6080/vnc.html"
          Write-Host "=================================================="
      
      - name: Keep Alive
        shell: pwsh
        run: |
          $end = (Get-Date).AddHours(6)
          while ((Get-Date) -lt $end) {{
            $remaining = [math]::Round(($end - (Get-Date)).TotalMinutes)
            Write-Host "VM running... expires in $remaining minutes"
            Start-Sleep -Seconds 300
          }}
'''

# ============================================ #
# CLOUDFLARE TUNNEL
# ============================================ #
def install_cloudflared():
    try:
        result = subprocess.run(['which', 'cloudflared'], capture_output=True, text=True)
        if result.returncode != 0:
            logger.info("Installing cloudflared...")
            subprocess.run(['wget', '-q', 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb'], check=False)
            subprocess.run(['dpkg', '-i', 'cloudflared-linux-amd64.deb'], check=False)
            subprocess.run(['rm', '-f', 'cloudflared-linux-amd64.deb'], check=False)
            logger.info("Cloudflared installed")
        return True
    except Exception as e:
        logger.error(f"Failed to install cloudflared: {e}")
        return False

def start_cloudflare_tunnel(vm_id, local_port=6080):
    try:
        install_cloudflared()
        
        # Khởi động tunnel
        tunnel_process = subprocess.Popen(
            ['cloudflared', 'tunnel', '--url', f'http://localhost:{local_port}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Đọc output để lấy URL
        time.sleep(3)
        # Đọc stderr để lấy URL
        stderr_output = ""
        for _ in range(20):
            line = tunnel_process.stderr.readline()
            if not line:
                break
            stderr_output += line
            if 'trycloudflare.com' in line:
                url_match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                if url_match:
                    tunnel_url = url_match.group(0)
                    logger.info(f"Cloudflare tunnel started for VM {vm_id}: {tunnel_url}")
                    return tunnel_process, tunnel_url
        
        logger.warning(f"Could not get tunnel URL for VM {vm_id}")
        return tunnel_process, None
    except Exception as e:
        logger.error(f"Failed to start Cloudflare tunnel: {e}")
        return None, None

def stop_cloudflare_tunnel(vm_id):
    if vm_id in cloudflare_tunnels:
        try:
            cloudflare_tunnels[vm_id].terminate()
            del cloudflare_tunnels[vm_id]
            logger.info(f"Cloudflare tunnel stopped for VM {vm_id}")
        except Exception as e:
            logger.error(f"Error stopping tunnel: {e}")

# ============================================ #
# GITHUB API FUNCTIONS
# ============================================ #
def verify_github_token(token):
    try:
        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github.v3+json'}
        response = requests.get('https://api.github.com/user', headers=headers, timeout=10)
        if response.status_code == 200:
            return True, response.json()
        return False, None
    except Exception as e:
        logger.error(f"Verify token error: {e}")
        return False, None

def create_github_repo(token, name, description):
    try:
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json'
        }
        data = {'name': name, 'description': description, 'private': False, 'auto_init': True}
        response = requests.post('https://api.github.com/user/repos', headers=headers, json=data, timeout=30)
        if response.status_code == 201:
            return True, response.json()
        return False, None
    except Exception as e:
        logger.error(f"Create repo error: {e}")
        return False, None

def create_workflow_file(token, owner, repo, username, password):
    try:
        content = generate_workflow_content(username, password)
        encoded = base64.b64encode(content.encode()).decode()
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json'
        }
        data = {
            'message': 'Add GitHub Actions workflow for VM creation',
            'content': encoded,
            'branch': 'main'
        }
        url = f'https://api.github.com/repos/{owner}/{repo}/contents/.github/workflows/create-vm.yml'
        response = requests.put(url, headers=headers, json=data, timeout=30)
        return response.status_code == 201
    except Exception as e:
        logger.error(f"Create workflow error: {e}")
        return False

def trigger_workflow(token, owner, repo, tailscale_key):
    try:
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json'
        }
        data = {
            'ref': 'main',
            'inputs': {'tailscale_key': tailscale_key}
        }
        url = f'https://api.github.com/repos/{owner}/{repo}/actions/workflows/create-vm.yml/dispatches'
        response = requests.post(url, headers=headers, json=data, timeout=30)
        return response.status_code == 204
    except Exception as e:
        logger.error(f"Trigger workflow error: {e}")
        return False

def get_workflow_runs(token, owner, repo):
    try:
        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github.v3+json'}
        url = f'https://api.github.com/repos/{owner}/{repo}/actions/runs'
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('workflow_runs', [])
        return []
    except Exception as e:
        logger.error(f"Get workflow runs error: {e}")
        return []

def get_workflow_logs(token, owner, repo, run_id):
    try:
        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github.v3+json'}
        url = f'https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/logs'
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.text
        return ""
    except Exception as e:
        logger.error(f"Get workflow logs error: {e}")
        return ""

def monitor_workflow(vm_id, token, owner, repo, tailscale_key=None):
    max_attempts = 36
    attempt = 0
    
    while attempt < max_attempts and vm_id in vms:
        time.sleep(10)
        attempt += 1
        
        try:
            runs = get_workflow_runs(token, owner, repo)
            if not runs:
                continue
            
            latest_run = runs[0]
            status = latest_run.get('status')
            conclusion = latest_run.get('conclusion')
            
            if status == 'completed' and conclusion == 'success':
                logs = get_workflow_logs(token, owner, repo, latest_run.get('id'))
                ip_match = re.search(r'Tailscale IP: (\d+\.\d+\.\d+\.\d+)', logs)
                
                if vm_id in vms:
                    vms[vm_id]['status'] = 'running'
                    if ip_match:
                        tailscale_ip = ip_match.group(1)
                        vms[vm_id]['tailscaleIP'] = tailscale_ip
                        vms[vm_id]['novncUrl'] = f'http://{tailscale_ip}:6080/vnc.html'
                        
                        # Khởi động Cloudflare tunnel
                        logger.info(f"Starting Cloudflare tunnel for VM {vm_id}")
                        tunnel_process, tunnel_url = start_cloudflare_tunnel(vm_id, 6080)
                        if tunnel_process and tunnel_url:
                            cloudflare_tunnels[vm_id] = tunnel_process
                            vms[vm_id]['novncUrl'] = tunnel_url
                            vms[vm_id]['cloudflare_tunnel'] = True
                            logger.info(f"Cloudflare tunnel URL: {tunnel_url}")
                    logger.info(f"VM {vm_id} is running")
                    break
            elif status == 'completed' and conclusion != 'success':
                if vm_id in vms:
                    vms[vm_id]['status'] = 'failed'
                logger.warning(f"VM {vm_id} failed: {conclusion}")
                break
            elif status == 'in_progress':
                if vm_id in vms and vms[vm_id]['status'] == 'creating':
                    vms[vm_id]['status'] = 'creating'
        except Exception as e:
            logger.error(f"Monitor error for {vm_id}: {e}")
    
    if vm_id in monitor_threads:
        del monitor_threads[vm_id]
    logger.info(f"Monitor stopped for VM {vm_id}")

# ============================================ #
# API ENDPOINTS
# ============================================ #
@app.route('/')
def serve_frontend():
    return send_from_directory('../frontend', 'index.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'vms_count': len(vms),
        'tunnels_count': len(cloudflare_tunnels)
    })

@app.route('/api/version', methods=['GET'])
def get_version():
    return jsonify({
        'version': VERSION,
        'build_date': BUILD_DATE,
        'features': ['Cloudflare Tunnel', 'Auto noVNC', '6h Countdown', 'Export TXT']
    })

@app.route('/api/vps', methods=['GET'])
def get_vms():
    logger.info(f"GET /api/vps - Total VMs: {len(vms)}")
    return jsonify({
        'success': True,
        'vms': list(vms.values()),
        'version': VERSION
    })

@app.route('/api/vps', methods=['DELETE'])
def delete_vm():
    vm_id = request.args.get('id')
    if vm_id and vm_id in vms:
        if vm_id in cloudflare_tunnels:
            stop_cloudflare_tunnel(vm_id)
        del vms[vm_id]
        logger.info(f"DELETE /api/vps - Deleted VM: {vm_id}")
        return jsonify({'success': True, 'message': 'Đã xóa VM'})
    return jsonify({'success': False, 'error': 'Không tìm thấy VM'})

@app.route('/api/vps', methods=['POST'])
def create_vm():
    global vm_counter
    
    data = request.get_json()
    github_token = data.get('githubToken', '')
    tailscale_key = data.get('tailscaleKey', '')
    username = data.get('vmUsername', '')
    password = data.get('vmPassword', '')
    
    logger.info(f"POST /api/vps - Creating VM with username: {username or 'auto'}")
    
    if not github_token:
        return jsonify({'success': False, 'error': 'Vui lòng nhập GitHub Token'})
    if not tailscale_key:
        return jsonify({'success': False, 'error': 'Vui lòng nhập Tailscale Key'})
    
    if not username:
        username = generate_username()
    if not password:
        password = generate_password()
    
    token_valid, user_info = verify_github_token(github_token)
    if not token_valid:
        return jsonify({'success': False, 'error': 'GitHub Token không hợp lệ hoặc đã hết hạn'})
    
    owner = user_info.get('login')
    repo_name = generate_repo_name()
    
    repo_success, repo_data = create_github_repo(github_token, repo_name, f'VM by {username}')
    if not repo_success:
        return jsonify({'success': False, 'error': 'Không thể tạo repository trên GitHub'})
    
    repo_url = repo_data.get('html_url')
    time.sleep(2)
    
    workflow_success = create_workflow_file(github_token, owner, repo_name, username, password)
    if not workflow_success:
        return jsonify({'success': False, 'error': 'Không thể tạo workflow file'})
    
    time.sleep(2)
    
    trigger_success = trigger_workflow(github_token, owner, repo_name, tailscale_key)
    if not trigger_success:
        return jsonify({'success': False, 'error': 'Không thể trigger GitHub Actions'})
    
    run_id = None
    try:
        time.sleep(3)
        runs = get_workflow_runs(github_token, owner, repo_name)
        if runs:
            run_id = runs[0].get('id')
            logger.info(f"Run ID: {run_id}")
    except Exception as e:
        logger.error(f"Error getting run ID: {e}")
    
    vm_counter += 1
    expires_at = datetime.now() + timedelta(hours=6)
    new_vm = {
        'id': str(vm_counter),
        'name': repo_name,
        'owner': owner,
        'username': username,
        'password': password,
        'status': 'creating',
        'repoUrl': repo_url,
        'workflowUrl': f'https://github.com/{owner}/{repo_name}/actions',
        'runId': run_id,
        'tailscaleIP': None,
        'novncUrl': None,
        'cloudflare_tunnel': False,
        'createdAt': datetime.now().isoformat(),
        'expiresAt': expires_at.isoformat(),
        'version': VERSION
    }
    
    vms[new_vm['id']] = new_vm
    
    if run_id:
        thread = threading.Thread(target=monitor_workflow, args=(new_vm['id'], github_token, owner, repo_name, tailscale_key))
        thread.daemon = True
        thread.start()
        monitor_threads[new_vm['id']] = thread
        logger.info(f"Monitor thread started for VM {new_vm['id']}")
    
    return jsonify({
        'success': True,
        **new_vm,
        'message': f'✅ VM "{username}" đang được tạo! Quá trình tạo mất 3-5 phút.'
    })

# ============================================ #
# MAIN
# ============================================ #
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 5000))
    HOST = os.environ.get('HOST', '0.0.0.0')
    
    print("")
    print("=" * 60)
    print("🚀 SINGULARITY CLUB BACKEND - PREMIUM EDITION")
    print("=" * 60)
    print(f"📌 Phiên bản: {VERSION}")
    print(f"📅 Ngày build: {BUILD_DATE}")
    print("=" * 60)
    print(f"📡 Server: http://{HOST}:{PORT}")
    print(f"🔗 API: http://{HOST}:{PORT}/api/vps")
    print(f"🌐 Frontend: http://{HOST}:{PORT}")
    print(f"💚 Health: http://{HOST}:{PORT}/api/health")
    print("=" * 60)
    print("✨ Tính năng:")
    print("   - Tạo VM qua GitHub Actions")
    print("   - Monitor workflow realtime")
    print("   - Lấy IP Tailscale tự động")
    print("   - Hỗ trợ Cloudflare Tunnel")
    print("   - Đếm ngược 6h")
    print("   - Export thông tin TXT")
    print("=" * 60)
    print("⚠️  Nhấn Ctrl+C để dừng server")
    print("=" * 60)
    print("")
    
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
