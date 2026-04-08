#!/bin/bash
# deploy.sh - Script deploy tự động cho Ubuntu VPS
# Singularity Club v1.0 (beta-version)

echo "========================================="
echo "Singularity Club v1.0 (beta) - Deploy Script"
echo "========================================="

# Màu sắc
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Cập nhật hệ thống
echo -e "${YELLOW}📦 Cập nhật hệ thống...${NC}"
sudo apt update && sudo apt upgrade -y

# Cài đặt Python và pip
echo -e "${YELLOW}🐍 Cài đặt Python...${NC}"
sudo apt install python3 python3-pip python3-venv -y

# Cài đặt Nginx
echo -e "${YELLOW}🌐 Cài đặt Nginx...${NC}"
sudo apt install nginx -y

# Tạo thư mục dự án
echo -e "${YELLOW}📂 Tạo thư mục dự án...${NC}"
mkdir -p /home/ubuntu/singularity-vm
cd /home/ubuntu/singularity-vm

# Tạo virtual environment
echo -e "${YELLOW}🔧 Tạo virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Cài đặt dependencies
echo -e "${YELLOW}📦 Cài đặt Python dependencies...${NC}"
pip install flask flask-cors requests gunicorn

# Tạo file requirements.txt
cat > requirements.txt << 'EOF'
flask==2.3.3
flask-cors==4.0.0
requests==2.31.0
gunicorn==21.2.0
EOF

# Tạo service systemd
echo -e "${YELLOW}⚙️ Tạo systemd service...${NC}"
sudo cat > /etc/systemd/system/singularity-vm.service << 'EOF'
[Unit]
Description=Singularity VM API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/singularity-vm
ExecStart=/home/ubuntu/singularity-vm/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Cấu hình Nginx
echo -e "${YELLOW}🌐 Cấu hình Nginx...${NC}"
sudo cat > /etc/nginx/sites-available/singularity-vm << 'EOF'
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
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Kích hoạt site
sudo ln -s /etc/nginx/sites-available/singularity-vm /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# Khởi động service
echo -e "${YELLOW}🚀 Khởi động service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable singularity-vm
sudo systemctl start singularity-vm

# Mở port firewall
echo -e "${YELLOW}🔥 Cấu hình firewall...${NC}"
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 5000
sudo ufw --force enable

echo -e "${GREEN}========================================="
echo -e "✅ DEPLOY HOÀN TẤT!"
echo -e "=========================================${NC}"
echo -e "🌐 Web: http://$(curl -s ifconfig.me)"
echo -e "🔗 API: http://$(curl -s ifconfig.me):5000/api/vps"
echo -e "========================================="
