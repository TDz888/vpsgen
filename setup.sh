#!/bin/bash
# setup.sh - Cài đặt môi trường và host web trên Ubuntu VPS
# Chạy: chmod +x setup.sh && ./setup.sh

set -e

# Màu sắc
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}=========================================="
echo "🚀 SINGULARITY CLUB - UBUNTU SETUP"
echo "==========================================${NC}"

# ============================================ #
# BƯỚC 1: CẬP NHẬT HỆ THỐNG
# ============================================ #
echo -e "${YELLOW}📦 Bước 1: Cập nhật hệ thống...${NC}"
sudo apt update && sudo apt upgrade -y

# ============================================ #
# BƯỚC 2: CÀI ĐẶT PYTHON VÀ PIP
# ============================================ #
echo -e "${YELLOW}🐍 Bước 2: Cài đặt Python...${NC}"
sudo apt install -y python3 python3-pip python3-venv

# ============================================ #
# BƯỚC 3: CÀI ĐẶT NGINX
# ============================================ #
echo -e "${YELLOW}🌐 Bước 3: Cài đặt Nginx...${NC}"
sudo apt install -y nginx

# ============================================ #
# BƯỚC 4: TẠO THƯ MỤC DỰ ÁN
# ============================================ #
echo -e "${YELLOW}📁 Bước 4: Tạo thư mục dự án...${NC}"
mkdir -p ~/singularity-web/backend
mkdir -p ~/singularity-web/frontend
cd ~/singularity-web

# ============================================ #
# BƯỚC 5: TẠO FILE BACKEND (app.py)
# ============================================ #
echo -e "${YELLOW}📝 Bước 5: Tạo file backend app.py...${NC}"
cat > backend/app.py << 'EOF'
# backend/app.py
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
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

vms = {}
vm_counter = 0

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
    password.extend(random.choices(all_chars, k=random.randint(8, 12)))
    random.shuffle(password)
    return ''.join(password)

@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

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
    username = data.get('vmUsername', '') or generate_username()
    password = data.get('vmPassword', '') or generate_password()
    
    if not github_token:
        return jsonify({'success': False, 'error': 'Vui lòng nhập GitHub Token'})
    if not tailscale_key:
        return jsonify({'success': False, 'error': 'Vui lòng nhập Tailscale Key'})
    
    vm_counter += 1
    new_vm = {
        'id': str(vm_counter),
        'name': f'vm-{int(time.time())}-{random.randint(1000,9999)}',
        'username': username,
        'password': password,
        'status': 'creating',
        'tailscaleIP': None,
        'novncUrl': None,
        'repoUrl': None,
        'workflowUrl': None,
        'createdAt': datetime.now().isoformat(),
        'expiresAt': (datetime.now() + timedelta(hours=6)).isoformat()
    }
    vms[new_vm['id']] = new_vm
    
    # Mô phỏng tạo VM (demo)
    def simulate():
        time.sleep(5)
        if new_vm['id'] in vms:
            new_vm['status'] = 'running'
            new_vm['tailscaleIP'] = f'100.64.{random.randint(1,255)}.{random.randint(1,255)}'
            new_vm['novncUrl'] = f'http://{new_vm["tailscaleIP"]}:6080/vnc.html'
            new_vm['repoUrl'] = 'https://github.com/demo/vm-repo'
            new_vm['workflowUrl'] = 'https://github.com/demo/vm-repo/actions'
    
    threading.Thread(target=simulate).start()
    
    return jsonify({'success': True, **new_vm, 'message': f'✅ VM "{username}" đang được tạo!'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
EOF

# ============================================ #
# BƯỚC 6: TẠO FILE REQUIREMENTS.TXT
# ============================================ #
echo -e "${YELLOW}📦 Bước 6: Tạo requirements.txt...${NC}"
cat > backend/requirements.txt << 'EOF'
flask==2.3.3
flask-cors==4.0.0
requests==2.31.0
gunicorn==21.2.0
EOF

# ============================================ #
# BƯỚC 7: TẠO FILE FRONTEND (index.html)
# ============================================ #
echo -e "${YELLOW}🎨 Bước 7: Tạo file frontend index.html...${NC}"
cat > frontend/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Singularity Club | VPS Generator</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --primary: #8b5cf6;
            --secondary: #ec4899;
            --success: #10b981;
            --warning: #f59e0b;
            --error: #ef4444;
            --bg: #0f0f1a;
            --card: rgba(30,30,50,0.7);
            --border: rgba(255,255,255,0.1);
            --text: #f1f5f9;
            --text-muted: #94a3b8;
        }
        body { background: var(--bg); font-family: 'Inter', sans-serif; color: var(--text); min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        
        .header { text-align: center; margin-bottom: 30px; }
        .logo { font-size: 2rem; font-weight: 700; background: linear-gradient(135deg, #fff, var(--primary), var(--secondary)); -webkit-background-clip: text; background-clip: text; color: transparent; }
        .subtitle { color: var(--text-muted); font-size: 0.8rem; margin-top: 5px; }
        
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 30px; }
        @media (max-width: 768px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } }
        .stat-card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 16px; }
        .stat-label { font-size: 0.7rem; color: var(--text-muted); margin-bottom: 5px; }
        .stat-value { font-size: 1.8rem; font-weight: 700; background: linear-gradient(135deg, var(--primary), var(--secondary)); -webkit-background-clip: text; background-clip: text; color: transparent; }
        
        .two-columns { display: grid; grid-template-columns: 1fr 1.2fr; gap: 24px; }
        @media (max-width: 900px) { .two-columns { grid-template-columns: 1fr; } }
        
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 20px; padding: 24px; }
        .card-title { font-size: 1.1rem; font-weight: 600; margin-bottom: 20px; display: flex; align-items: center; gap: 8px; }
        
        .input-group { margin-bottom: 18px; }
        .input-label { font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px; display: block; }
        .input-field { width: 100%; background: rgba(0,0,0,0.3); border: 1px solid var(--border); border-radius: 12px; padding: 12px; color: var(--text); font-size: 0.85rem; }
        .input-field:focus { outline: none; border-color: var(--primary); }
        .input-row { display: flex; gap: 12px; }
        .input-row .input-group { flex: 1; margin-bottom: 0; }
        .random-btn { background: rgba(139,92,246,0.2); border: 1px solid var(--border); border-radius: 12px; padding: 12px 16px; color: var(--primary); cursor: pointer; }
        
        .btn { padding: 12px; border-radius: 12px; font-weight: 600; cursor: pointer; border: none; width: 100%; }
        .btn-primary { background: linear-gradient(135deg, var(--primary), var(--secondary)); color: white; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(139,92,246,0.3); }
        
        .quick-actions { display: flex; gap: 10px; margin-top: 20px; flex-wrap: wrap; }
        .quick-btn { flex: 1; background: rgba(0,0,0,0.25); border: 1px solid var(--border); border-radius: 10px; padding: 8px; font-size: 0.7rem; cursor: pointer; text-align: center; }
        
        .vm-controls { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        .vm-search { flex: 1; background: rgba(0,0,0,0.25); border: 1px solid var(--border); border-radius: 30px; padding: 8px 14px; color: var(--text); }
        .vm-filter, .vm-sort { background: rgba(0,0,0,0.25); border: 1px solid var(--border); border-radius: 30px; padding: 8px 14px; color: var(--text); cursor: pointer; }
        .vm-count { background: rgba(139,92,246,0.15); border-radius: 30px; padding: 8px 14px; font-size: 0.75rem; }
        
        .vm-item { background: rgba(0,0,0,0.25); border-radius: 16px; margin-bottom: 12px; border: 1px solid var(--border); }
        .vm-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; cursor: pointer; }
        .vm-info { display: flex; align-items: center; gap: 12px; }
        .vm-icon { width: 40px; height: 40px; background: linear-gradient(135deg, rgba(139,92,246,0.2), rgba(236,72,153,0.2)); border-radius: 12px; display: flex; align-items: center; justify-content: center; }
        .vm-name { font-weight: 600; font-size: 0.9rem; }
        .vm-time { font-size: 0.6rem; color: var(--text-muted); margin-top: 3px; }
        .vm-status { font-size: 0.65rem; padding: 3px 10px; border-radius: 50px; }
        .status-creating { background: rgba(245,158,11,0.2); color: var(--warning); }
        .status-running { background: rgba(16,185,129,0.2); color: var(--success); }
        .vm-expand-icon { transition: transform 0.2s; }
        .vm-item.open .vm-expand-icon { transform: rotate(180deg); }
        .vm-detail { max-height: 0; overflow: hidden; transition: max-height 0.3s; border-top: 1px solid transparent; }
        .vm-item.open .vm-detail { max-height: 300px; border-top-color: var(--border); padding: 16px; }
        
        .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
        .info-box { background: rgba(0,0,0,0.2); border-radius: 12px; padding: 12px; }
        .info-title { font-size: 0.65rem; color: var(--text-muted); margin-bottom: 8px; }
        .info-value { font-family: monospace; font-size: 0.8rem; display: flex; justify-content: space-between; align-items: center; }
        .copy-btn { background: rgba(139,92,246,0.2); border: none; color: var(--primary); padding: 4px 8px; border-radius: 6px; cursor: pointer; }
        
        .vm-links { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
        .vm-link { background: rgba(59,130,246,0.15); padding: 6px 12px; border-radius: 8px; font-size: 0.7rem; text-decoration: none; color: #3b82f6; }
        .vm-delete { background: rgba(239,68,68,0.15); color: var(--error); padding: 6px 12px; border-radius: 8px; cursor: pointer; border: none; }
        
        .toast { position: fixed; bottom: 20px; right: 20px; background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 10px 16px; transform: translateX(400px); transition: transform 0.3s; z-index: 1000; border-left: 3px solid var(--primary); }
        .toast.show { transform: translateX(0); }
        .empty-state { text-align: center; padding: 40px; color: var(--text-muted); }
        .spinner { width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.6s linear infinite; display: inline-block; }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .footer { text-align: center; padding: 20px; margin-top: 24px; border-top: 1px solid var(--border); color: var(--text-muted); font-size: 0.65rem; }
        @media (max-width: 640px) { .container { padding: 12px; } .info-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo"><i class="fas fa-infinity"></i> SINGULARITY CLUB</div>
            <div class="subtitle">Virtual Machine Platform • Powered by GitHub Actions</div>
        </div>

        <div class="stats-grid">
            <div class="stat-card"><div class="stat-label">TOTAL VMS</div><div class="stat-value" id="statTotal">0</div></div>
            <div class="stat-card"><div class="stat-label">ACTIVE VMS</div><div class="stat-value" id="statActive">0</div></div>
            <div class="stat-card"><div class="stat-label">UPTIME</div><div class="stat-value" id="statUptime">00:00:00</div></div>
            <div class="stat-card"><div class="stat-label">SUCCESS RATE</div><div class="stat-value" id="statRate">100%</div></div>
        </div>

        <div class="two-columns">
            <div class="card">
                <div class="card-title"><i class="fas fa-rocket"></i> Khởi tạo Virtual Machine</div>
                <div class="input-group"><label class="input-label"><i class="fab fa-github"></i> GitHub Token</label><input type="password" class="input-field" id="githubToken" placeholder="ghp_xxxxxxxxxxxx"></div>
                <div class="input-group"><label class="input-label"><i class="fas fa-network-wired"></i> Tailscale Key</label><input type="password" class="input-field" id="tailscaleKey" placeholder="tskey-xxxxxxxxxxxx"></div>
                <div class="input-row"><div class="input-group"><label class="input-label"><i class="fas fa-user"></i> Tên đăng nhập</label><input type="text" class="input-field" id="vmUsername" placeholder="username"></div><button class="random-btn" id="randomUserBtn">Random</button></div>
                <div class="input-row"><div class="input-group"><label class="input-label"><i class="fas fa-lock"></i> Mật khẩu</label><input type="password" class="input-field" id="vmPassword" placeholder="password"></div><button class="random-btn" id="randomPassBtn">Random</button></div>
                <button class="btn btn-primary" id="createBtn"><i class="fas fa-play"></i> Tạo VM Ngay</button>
                <div class="quick-actions"><div class="quick-btn" id="demoBtn">Demo</div><div class="quick-btn" id="clearBtn">Xóa</div><div class="quick-btn" id="refreshBtn">Làm mới</div></div>
            </div>

            <div class="card">
                <div class="card-title"><i class="fas fa-server"></i> Virtual Machines</div>
                <div class="vm-controls"><input type="text" class="vm-search" id="searchInput" placeholder="🔍 Tìm kiếm..."><select class="vm-filter" id="filterSelect"><option value="all">Tất cả</option><option value="running">Đang chạy</option><option value="creating">Đang tạo</option></select><select class="vm-sort" id="sortSelect"><option value="newest">Mới nhất</option><option value="oldest">Cũ nhất</option></select><div class="vm-count"><span id="vmCount">0</span></div></div>
                <div id="vmList"><div class="empty-state">✨ Chưa có VM nào ✨</div></div>
            </div>
        </div>
        
        <div class="footer">© 2026 Singularity Club | <i class="fab fa-github"></i> GitHub</div>
    </div>
    <div id="toast" class="toast"><i class="fas fa-check-circle"></i> <span id="toastMsg"></span></div>

    <script>
        const API_URL = '/api/vps';
        let vms = [], sessionStart = Date.now();
        let currentFilter = 'all', currentSort = 'newest';
        let totalCreations = 0, successfulCreations = 0;
        
        const elements = {
            githubToken: document.getElementById('githubToken'),
            tailscaleKey: document.getElementById('tailscaleKey'),
            vmUsername: document.getElementById('vmUsername'),
            vmPassword: document.getElementById('vmPassword'),
            createBtn: document.getElementById('createBtn'),
            vmList: document.getElementById('vmList'),
            searchInput: document.getElementById('searchInput'),
            filterSelect: document.getElementById('filterSelect'),
            sortSelect: document.getElementById('sortSelect'),
            vmCount: document.getElementById('vmCount'),
            statTotal: document.getElementById('statTotal'),
            statActive: document.getElementById('statActive'),
            statUptime: document.getElementById('statUptime'),
            statRate: document.getElementById('statRate'),
            toast: document.getElementById('toast'),
            toastMsg: document.getElementById('toastMsg')
        };
        
        function showToast(msg, type = 'success') {
            elements.toastMsg.textContent = msg;
            elements.toast.classList.add('show');
            setTimeout(() => elements.toast.classList.remove('show'), 3000);
        }
        
        function randomUsername() {
            return Math.random().toString(36).substring(2, 10);
        }
        
        function randomPassword() {
            const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';
            return Array(12).fill().map(() => chars[Math.floor(Math.random() * chars.length)]).join('');
        }
        
        function updateStats() {
            elements.statTotal.textContent = vms.length;
            elements.statActive.textContent = vms.filter(v => v.status === 'running').length;
            const rate = totalCreations > 0 ? Math.floor((successfulCreations / totalCreations) * 100) : 100;
            elements.statRate.textContent = rate + '%';
            const elapsed = Math.floor((Date.now() - sessionStart) / 1000);
            elements.statUptime.textContent = `${Math.floor(elapsed/3600).toString().padStart(2,'0')}:${Math.floor((elapsed%3600)/60).toString().padStart(2,'0')}:${(elapsed%60).toString().padStart(2,'0')}`;
        }
        
        function renderVMList() {
            let filtered = [...vms];
            const search = elements.searchInput.value.toLowerCase();
            if (search) filtered = filtered.filter(v => (v.name || '').toLowerCase().includes(search) || (v.username || '').toLowerCase().includes(search));
            if (currentFilter !== 'all') filtered = filtered.filter(v => v.status === currentFilter);
            if (currentSort === 'newest') filtered.sort((a,b) => new Date(b.createdAt) - new Date(a.createdAt));
            else filtered.sort((a,b) => new Date(a.createdAt) - new Date(b.createdAt));
            elements.vmCount.textContent = filtered.length;
            updateStats();
            if (filtered.length === 0) { elements.vmList.innerHTML = '<div class="empty-state">✨ Chưa có VM nào ✨</div>'; return; }
            elements.vmList.innerHTML = filtered.map(vm => `
                <div class="vm-item" data-id="${vm.id}">
                    <div class="vm-header" onclick="toggleVM('${vm.id}')">
                        <div class="vm-info">
                            <div class="vm-icon"><i class="fas ${vm.status === 'running' ? 'fa-play-circle' : 'fa-spinner fa-pulse'}"></i></div>
                            <div><div class="vm-name">${vm.name || vm.id.substring(0,15)}</div><div class="vm-time">${new Date(vm.createdAt).toLocaleString()}</div></div>
                        </div>
                        <div style="display:flex; gap:10px; align-items:center;"><span class="vm-status status-${vm.status}">${vm.status}</span><i class="fas fa-chevron-down vm-expand-icon"></i></div>
                    </div>
                    <div class="vm-detail">
                        <div class="info-grid">
                            <div class="info-box"><div class="info-title"><i class="fas fa-user"></i> THÔNG TIN ĐĂNG NHẬP</div>
                                <div class="info-value"><span>${vm.username}</span><button class="copy-btn" onclick="copyText('${vm.username}')">Sao chép</button></div>
                                <div class="info-value" style="margin-top:8px;"><span>••••••••</span><button class="copy-btn" onclick="copyText('${vm.password}')">Sao chép</button></div>
                            </div>
                            <div class="info-box"><div class="info-title"><i class="fas fa-clock"></i> THỜI GIAN</div>
                                <div class="info-value">Tạo: ${new Date(vm.createdAt).toLocaleString()}</div>
                                <div class="info-value" style="margin-top:4px;">Hết hạn: ${new Date(vm.expiresAt).toLocaleString()}</div>
                            </div>
                        </div>
                        ${vm.tailscaleIP ? `<div class="info-box" style="margin-top:12px;"><div class="info-title"><i class="fas fa-network-wired"></i> KẾT NỐI</div><div class="info-value"><span>Tailscale IP: ${vm.tailscaleIP}</span><button class="copy-btn" onclick="copyText('${vm.tailscaleIP}')">Sao chép</button></div></div>` : ''}
                        <div class="vm-links">${vm.repoUrl ? `<a href="${vm.repoUrl}" target="_blank" class="vm-link"><i class="fab fa-github"></i> Repository</a>` : ''}${vm.workflowUrl ? `<a href="${vm.workflowUrl}" target="_blank" class="vm-link"><i class="fas fa-code-branch"></i> Actions</a>` : ''}<button class="vm-delete" onclick="deleteVM('${vm.id}')"><i class="fas fa-trash"></i> Xóa VM</button></div>
                    </div>
                </div>
            `).join('');
        }
        
        window.toggleVM = function(id) { document.querySelector(`.vm-item[data-id="${id}"]`).classList.toggle('open'); };
        window.copyText = function(text) { navigator.clipboard.writeText(text); showToast('Đã sao chép!'); };
        
        async function loadVMs() {
            try { const res = await fetch(API_URL); const data = await res.json(); if (data.success) { vms = data.vms; renderVMList(); } } catch(e) { console.log(e); }
        }
        
        window.deleteVM = async function(id) {
            if (!confirm('Xóa VM này?')) return;
            try { await fetch(`${API_URL}?id=${id}`, { method: 'DELETE' }); showToast('Đã xóa VM'); await loadVMs(); } catch(e) { showToast('Lỗi xóa', 'error'); }
        };
        
        async function createVM() {
            const githubToken = elements.githubToken.value.trim();
            const tailscaleKey = elements.tailscaleKey.value.trim();
            let username = elements.vmUsername.value.trim() || randomUsername();
            let password = elements.vmPassword.value.trim() || randomPassword();
            if (!githubToken) { showToast('Nhập GitHub Token', 'error'); return; }
            if (!tailscaleKey) { showToast('Nhập Tailscale Key', 'error'); return; }
            
            elements.createBtn.disabled = true;
            elements.createBtn.innerHTML = '<span class="spinner"></span> Đang tạo...';
            
            try {
                const res = await fetch(API_URL, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ githubToken, tailscaleKey, vmUsername: username, vmPassword: password }) });
                const data = await res.json();
                totalCreations++;
                if (data.success) { successfulCreations++; showToast(`✅ VM "${username}" đã được tạo!`); await loadVMs(); elements.githubToken.value = ''; elements.tailscaleKey.value = ''; }
                else { showToast(data.error || 'Tạo thất bại', 'error'); }
            } catch(e) { showToast('Lỗi kết nối', 'error'); }
            elements.createBtn.disabled = false;
            elements.createBtn.innerHTML = '<i class="fas fa-play"></i> Tạo VM Ngay';
        }
        
        document.getElementById('createBtn').onclick = createVM;
        document.getElementById('randomUserBtn').onclick = () => { elements.vmUsername.value = randomUsername(); showToast('Username random'); };
        document.getElementById('randomPassBtn').onclick = () => { elements.vmPassword.value = randomPassword(); showToast('Password random'); };
        document.getElementById('demoBtn').onclick = () => { elements.githubToken.value = 'ghp_demo'; elements.tailscaleKey.value = 'tskey_demo'; showToast('Demo token'); };
        document.getElementById('clearBtn').onclick = () => { elements.githubToken.value = ''; elements.tailscaleKey.value = ''; elements.vmUsername.value = ''; elements.vmPassword.value = ''; };
        document.getElementById('refreshBtn').onclick = () => { loadVMs(); };
        elements.filterSelect.onchange = (e) => { currentFilter = e.target.value; renderVMList(); };
        elements.sortSelect.onchange = (e) => { currentSort = e.target.value; renderVMList(); };
        elements.searchInput.oninput = () => { renderVMList(); };
        
        elements.vmUsername.value = randomUsername();
        elements.vmPassword.value = randomPassword();
        loadVMs();
        setInterval(loadVMs, 10000);
        setInterval(updateStats, 1000);
    </script>
</body>
</html>
HTMLEOF

# ============================================ #
# BƯỚC 8: TẠO FILE REQUIREMENTS.TXT
# ============================================ #
echo -e "${YELLOW}📦 Bước 8: Cài đặt Python packages...${NC}"
cd ~/singularity-web/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# ============================================ #
# BƯỚC 9: TẠO FILE START.SH
# ============================================ #
echo -e "${YELLOW}🚀 Bước 9: Tạo script khởi động...${NC}"
cat > ~/singularity-web/start.sh << 'STARTEOF'
#!/bin/bash
cd ~/singularity-web/backend
source venv/bin/activate
python3 app.py
STARTEOF
chmod +x ~/singularity-web/start.sh

# ============================================ #
# BƯỚC 10: TẠO FILE STOP.SH
# ============================================ #
echo -e "${YELLOW}🛑 Bước 10: Tạo script dừng...${NC}"
cat > ~/singularity-web/stop.sh << 'STOPEOF'
#!/bin/bash
pkill -f "python3 app.py"
echo "✅ Đã dừng server"
STOPEOF
chmod +x ~/singularity-web/stop.sh

# ============================================ #
# BƯỚC 11: CẤU HÌNH NGINX (TÙY CHỌN)
# ============================================ #
echo -e "${YELLOW}🌐 Bước 11: Cấu hình Nginx (tùy chọn)...${NC}"
sudo cat > /etc/nginx/sites-available/singularity << 'NGINXEOF'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
NGINXEOF

sudo ln -s /etc/nginx/sites-available/singularity /etc/nginx/sites-enabled/ 2>/dev/null
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# ============================================ #
# HOÀN TẤT
# ============================================ #
IP=$(curl -s ifconfig.me)
echo -e "${GREEN}=========================================="
echo "✅ CÀI ĐẶT HOÀN TẤT!"
echo "==========================================${NC}"
echo ""
echo -e "${BLUE}🌐 TRUY CẬP WEB:${NC}"
echo "   http://$IP"
echo "   http://localhost:5000"
echo ""
echo -e "${YELLOW}🚀 ĐỂ CHẠY WEB:${NC}"
echo "   cd ~/singularity-web && ./start.sh"
echo ""
echo -e "${YELLOW}🛑 ĐỂ DỪNG WEB:${NC}"
echo "   ./stop.sh"
echo ""
echo -e "${GREEN}==========================================${NC}"
