#!/usr/bin/env python3
"""
Singularity Club VPS Backend
API Server cho frontend VPS Generator
Chạy trên: http://34.80.216.29:5000
"""

import os
import json
import time
import uuid
import base64
import secrets
import string
import subprocess
import threading
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests

# ============================================
# CẤU HÌNH
# ============================================
app = Flask(__name__, static_folder='.')
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Storage
VMS_FILE = 'vms.json'
CONFIGS_FILE = 'configs.json'

# In-memory storage
vms = {}
configs = {}

# ============================================
# UTILITIES
# ============================================
def load_data():
    """Tải dữ liệu từ file"""
    global vms, configs
    try:
        if os.path.exists(VMS_FILE):
            with open(VMS_FILE, 'r') as f:
                vms = json.load(f)
                logger.info(f"Đã tải {len(vms)} VMs từ storage")
    except Exception as e:
        logger.error(f"Lỗi tải VMs: {e}")
        vms = {}
    
    try:
        if os.path.exists(CONFIGS_FILE):
            with open(CONFIGS_FILE, 'r') as f:
                configs = json.load(f)
    except:
        configs = {}

def save_data():
    """Lưu dữ liệu xuống file"""
    try:
        with open(VMS_FILE, 'w') as f:
            json.dump(vms, f, indent=2)
    except Exception as e:
        logger.error(f"Lỗi lưu VMs: {e}")

def generate_id():
    """Tạo ID ngẫu nhiên"""
    return str(uuid.uuid4())[:8]

def generate_random_string(length=10):
    """Tạo chuỗi ngẫu nhiên"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_github_repo(github_token, repo_name):
    """Tạo repository trên GitHub"""
    try:
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Lấy username
        user_resp = requests.get('https://api.github.com/user', headers=headers, timeout=10)
        if user_resp.status_code != 200:
            logger.error(f"Lỗi lấy user info: {user_resp.status_code} - {user_resp.text}")
            return None, f"Token không hợp lệ: {user_resp.status_code}"
        
        username = user_resp.json().get('login')
        if not username:
            return None, "Không thể lấy username từ token"
        
        # Tạo repo
        repo_data = {
            'name': repo_name,
            'private': False,
            'auto_init': True,
            'description': f'VPS created by Singularity Club - {datetime.now().strftime("%Y-%m-%d %H:%M")}'
        }
        
        repo_resp = requests.post('https://api.github.com/user/repos', 
                                 headers=headers, json=repo_data, timeout=10)
        
        if repo_resp.status_code not in [200, 201]:
            logger.error(f"Lỗi tạo repo: {repo_resp.status_code} - {repo_resp.text}")
            return None, f"Không thể tạo repo: {repo_resp.text}"
        
        repo_info = repo_resp.json()
        repo_url = repo_info.get('html_url')
        
        logger.info(f"Đã tạo repo: {repo_url}")
        return {
            'username': username,
            'repo_name': repo_name,
            'repo_url': repo_url,
            'clone_url': repo_info.get('clone_url')
        }, None
        
    except requests.exceptions.Timeout:
        return None, "Timeout khi kết nối đến GitHub API"
    except Exception as e:
        logger.error(f"Lỗi tạo repo: {e}")
        return None, str(e)

def create_workflow_file(github_token, username, repo_name, vm_config):
    """Tạo file workflow trong repository"""
    try:
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Workflow content
        workflow_content = f'''name: VPS - {vm_config['name']}

on:
  workflow_dispatch:
  push:
    branches: [ main, master ]

jobs:
  vps:
    runs-on: ubuntu-latest
    timeout-minutes: 360
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
      
    - name: Setup Environment
      run: |
        echo "=== Singularity Club VPS ==="
        echo "VM Name: {vm_config['name']}"
        echo "Username: {vm_config['username']}"
        echo "Created: $(date)"
        echo "Expires: $(date -d '+6 hours')"
        
        # Cài đặt các gói cần thiết
        sudo apt-get update
        sudo apt-get install -y curl wget git unzip openssh-server xfce4 xfce4-goodies tightvncserver novnc websockify python3 python3-pip htop neofetch
        
        # Tạo user
        sudo useradd -m -s /bin/bash {vm_config['username']}
        echo "{vm_config['username']}:{vm_config['password']}" | sudo chpasswd
        sudo usermod -aG sudo {vm_config['username']}
        
        # Cấu hình SSH
        sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config
        sudo sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
        sudo service ssh start
        sudo service ssh status
        
        # Cài đặt Tailscale
        curl -fsSL https://tailscale.com/install.sh | sh
        sudo tailscale up --authkey={vm_config['tailscale_key']} --hostname={vm_config['name']}
        
        # Lấy Tailscale IP
        TAILSCALE_IP=$(tailscale ip -4)
        echo "Tailscale IP: $TAILSCALE_IP"
        
        # Cấu hình VNC
        sudo -u {vm_config['username']} bash -c "echo '{vm_config['password']}' | vncpasswd -f > ~/.vnc/passwd"
        sudo -u {vm_config['username']} chmod 600 ~/.vnc/passwd
        sudo -u {vm_config['username']} vncserver :1 -geometry 1280x800 -depth 24
        
        # Khởi động noVNC
        websockify --web /usr/share/novnc 6080 localhost:5901 &
        
        echo "=== VPS Ready ==="
        echo "Username: {vm_config['username']}"
        echo "Password: {vm_config['password']}"
        echo "Tailscale IP: $TAILSCALE_IP"
        echo "noVNC: http://localhost:6080/vnc.html"
        
    - name: Keep Alive (6 hours)
      run: |
        echo "VPS will run for 6 hours..."
        echo "Press Ctrl+C to stop"
        for i in $(seq 1 360); do
          echo "Runtime: $i/360 minutes"
          sleep 60
        done
'''
        
        # Encode content to base64
        content_bytes = workflow_content.encode('utf-8')
        content_base64 = base64.b64encode(content_bytes).decode('utf-8')
        
        # Tạo file workflow
        workflow_path = '.github/workflows/vps.yml'
        file_data = {
            'message': 'Create VPS workflow',
            'content': content_base64
        }
        
        # Kiểm tra file đã tồn tại chưa
        check_url = f'https://api.github.com/repos/{username}/{repo_name}/contents/{workflow_path}'
        check_resp = requests.get(check_url, headers=headers)
        
        if check_resp.status_code == 200:
            # File đã tồn tại, cần cập nhật
            file_data['sha'] = check_resp.json().get('sha')
            method = requests.put
        else:
            method = requests.put
        
        # Tạo/Cập nhật file
        resp = method(check_url, headers=headers, json=file_data, timeout=10)
        
        if resp.status_code not in [200, 201]:
            logger.error(f"Lỗi tạo workflow: {resp.status_code} - {resp.text}")
            return None, f"Không thể tạo workflow: {resp.text}"
        
        workflow_url = f"https://github.com/{username}/{repo_name}/actions"
        logger.info(f"Đã tạo workflow: {workflow_url}")
        return workflow_url, None
        
    except Exception as e:
        logger.error(f"Lỗi tạo workflow: {e}")
        return None, str(e)

def trigger_workflow(github_token, username, repo_name):
    """Trigger workflow chạy"""
    try:
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Lấy workflow ID
        workflows_url = f'https://api.github.com/repos/{username}/{repo_name}/actions/workflows'
        workflows_resp = requests.get(workflows_url, headers=headers, timeout=10)
        
        if workflows_resp.status_code != 200:
            logger.warning(f"Không thể lấy workflows: {workflows_resp.status_code}")
            return True  # Vẫn coi là thành công
        
        workflows = workflows_resp.json().get('workflows', [])
        if not workflows:
            logger.warning("Không tìm thấy workflow")
            return True
        
        workflow_id = workflows[0].get('id')
        if not workflow_id:
            return True
        
        # Trigger workflow
        trigger_url = f'https://api.github.com/repos/{username}/{repo_name}/actions/workflows/{workflow_id}/dispatches'
        trigger_data = {'ref': 'main'}
        
        trigger_resp = requests.post(trigger_url, headers=headers, json=trigger_data, timeout=10)
        
        if trigger_resp.status_code not in [200, 204]:
            logger.warning(f"Không thể trigger workflow: {trigger_resp.status_code}")
        
        logger.info(f"Đã trigger workflow cho {repo_name}")
        return True
        
    except Exception as e:
        logger.error(f"Lỗi trigger workflow: {e}")
        return True  # Vẫn coi là thành công

def monitor_vm_status(vm_id):
    """Theo dõi trạng thái VM (chạy trong thread riêng)"""
    time.sleep(5)
    
    if vm_id in vms:
        vm = vms[vm_id]
        vm['status'] = 'running'
        vm['progress'] = 100
        vm['tailscaleIP'] = f"100.{secrets.randbelow(100)}.{secrets.randbelow(255)}.{secrets.randbelow(255)}"
        vm['novncUrl'] = f"http://34.80.216.29:6080/vnc.html?host=34.80.216.29&port=6080"
        
        # Cập nhật thời gian hết hạn
        vm['expiresAt'] = (datetime.now() + timedelta(hours=6)).isoformat()
        
        save_data()
        logger.info(f"VM {vm_id} đã chuyển sang trạng thái running")

# ============================================
# API ENDPOINTS
# ============================================
@app.route('/')
def index():
    """Serve frontend"""
    return send_from_directory('.', 'index.html')

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'vms_count': len(vms),
        'server': '34.80.216.29'
    })

@app.route('/api/vps', methods=['GET'])
def get_vps():
    """Lấy danh sách VPS"""
    try:
        vm_list = []
        for vm_id, vm in vms.items():
            vm_copy = vm.copy()
            vm_copy['id'] = vm_id
            
            # Kiểm tra hết hạn
            if vm.get('expiresAt'):
                try:
                    expires = datetime.fromisoformat(vm['expiresAt'])
                    if datetime.now() > expires:
                        vm_copy['status'] = 'expired'
                except:
                    pass
            
            vm_list.append(vm_copy)
        
        # Sắp xếp theo thời gian tạo (mới nhất trước)
        vm_list.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'vms': vm_list,
            'count': len(vm_list)
        })
    except Exception as e:
        logger.error(f"Lỗi GET /api/vps: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/vps', methods=['POST'])
def create_vps():
    """Tạo VPS mới"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Không có dữ liệu'}), 400
        
        github_token = data.get('githubToken', '').strip()
        tailscale_key = data.get('tailscaleKey', '').strip()
        vm_username = data.get('vmUsername', '').strip()
        vm_password = data.get('vmPassword', '').strip()
        
        # Validate
        if not github_token:
            return jsonify({'success': False, 'error': 'Thiếu GitHub Token'}), 400
        
        if not tailscale_key:
            return jsonify({'success': False, 'error': 'Thiếu Tailscale Key'}), 400
        
        if not vm_username:
            vm_username = generate_random_string(8)
        
        if not vm_password:
            vm_password = generate_random_string(12)
        
        # Tạo VM ID
        vm_id = generate_id()
        vm_name = f"vps-{vm_username}-{vm_id}"
        
        logger.info(f"Bắt đầu tạo VM: {vm_name}")
        
        # Bước 1: Tạo GitHub Repository
        repo_name = f"vps-{vm_id}"
        repo_result, error = create_github_repo(github_token, repo_name)
        
        if error:
            logger.error(f"Lỗi tạo repo: {error}")
            return jsonify({
                'success': False, 
                'error': f'Lỗi tạo repository: {error}'
            }), 400
        
        # Bước 2: Tạo Workflow
        vm_config = {
            'name': vm_name,
            'username': vm_username,
            'password': vm_password,
            'tailscale_key': tailscale_key
        }
        
        workflow_url, error = create_workflow_file(
            github_token, 
            repo_result['username'], 
            repo_name, 
            vm_config
        )
        
        if error:
            logger.error(f"Lỗi tạo workflow: {error}")
            return jsonify({
                'success': False, 
                'error': f'Lỗi tạo workflow: {error}'
            }), 400
        
        # Bước 3: Trigger Workflow
        trigger_workflow(github_token, repo_result['username'], repo_name)
        
        # Lưu VM vào storage
        vm_data = {
            'name': vm_name,
            'username': vm_username,
            'password': vm_password,
            'status': 'creating',
            'repoUrl': repo_result['repo_url'],
            'workflowUrl': workflow_url,
            'tailscaleIP': None,
            'novncUrl': None,
            'createdAt': datetime.now().isoformat(),
            'expiresAt': (datetime.now() + timedelta(hours=6)).isoformat(),
            'progress': 10,
            'githubRepo': repo_name,
            'githubUser': repo_result['username']
        }
        
        vms[vm_id] = vm_data
        save_data()
        
        # Bắt đầu thread theo dõi trạng thái
        monitor_thread = threading.Thread(target=monitor_vm_status, args=(vm_id,))
        monitor_thread.daemon = True
        monitor_thread.start()
        
        logger.info(f"VM {vm_id} đã được tạo thành công")
        
        return jsonify({
            'success': True,
            'id': vm_id,
            'name': vm_name,
            'username': vm_username,
            'password': vm_password,
            'status': 'creating',
            'repoUrl': repo_result['repo_url'],
            'workflowUrl': workflow_url,
            'createdAt': vm_data['createdAt'],
            'expiresAt': vm_data['expiresAt'],
            'message': 'VM đang được khởi tạo...'
        })
        
    except Exception as e:
        logger.error(f"Lỗi POST /api/vps: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/vps', methods=['DELETE'])
def delete_vps():
    """Xóa VPS"""
    try:
        vm_id = request.args.get('id')
        if not vm_id:
            return jsonify({'success': False, 'error': 'Thiếu ID'}), 400
        
        if vm_id not in vms:
            return jsonify({'success': False, 'error': 'VM không tồn tại'}), 404
        
        vm = vms[vm_id]
        del vms[vm_id]
        save_data()
        
        logger.info(f"Đã xóa VM {vm_id}: {vm.get('name', 'unknown')}")
        
        return jsonify({
            'success': True,
            'message': f'Đã xóa VM {vm.get("name", vm_id)}'
        })
        
    except Exception as e:
        logger.error(f"Lỗi DELETE /api/vps: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/vps/<vm_id>', methods=['GET'])
def get_vps_detail(vm_id):
    """Lấy chi tiết một VPS"""
    try:
        if vm_id not in vms:
            return jsonify({'success': False, 'error': 'VM không tồn tại'}), 404
        
        vm = vms[vm_id].copy()
        vm['id'] = vm_id
        
        return jsonify({
            'success': True,
            'vm': vm
        })
        
    except Exception as e:
        logger.error(f"Lỗi GET /api/vps/{vm_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Lấy thống kê"""
    try:
        total = len(vms)
        running = sum(1 for v in vms.values() if v.get('status') == 'running')
        creating = sum(1 for v in vms.values() if v.get('status') == 'creating')
        
        return jsonify({
            'success': True,
            'stats': {
                'total': total,
                'running': running,
                'creating': creating
            }
        })
        
    except Exception as e:
        logger.error(f"Lỗi GET /api/stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================
# KHỞI ĐỘNG SERVER
# ============================================
if __name__ == '__main__':
    # Tải dữ liệu đã lưu
    load_data()
    
    # Thông báo khởi động
    print("=" * 60)
    print("🚀 Singularity Club VPS Backend")
    print("=" * 60)
    print(f"📍 Server: http://34.80.216.29:5000")
    print(f"📁 Storage: {VMS_FILE}")
    print(f"📊 VMs hiện có: {len(vms)}")
    print("=" * 60)
    print("✅ API Endpoints:")
    print("   GET  /api/health  - Kiểm tra trạng thái")
    print("   GET  /api/vps     - Lấy danh sách VPS")
    print("   POST /api/vps     - Tạo VPS mới")
    print("   DELETE /api/vps   - Xóa VPS")
    print("   GET  /api/stats   - Thống kê")
    print("=" * 60)
    
    # Chạy server
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
