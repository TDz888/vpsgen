# backend/config.py
# Cấu hình tập trung cho toàn bộ ứng dụng

import os
from datetime import timedelta

class Config:
    # Server config
    PORT = int(os.environ.get('PORT', 5000))
    HOST = os.environ.get('HOST', '0.0.0.0')
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # API config
    API_VERSION = "1.0.0"
    API_TITLE = "Singularity Club API"
    
    # GitHub config
    GITHUB_API = "https://api.github.com"
    GITHUB_TIMEOUT = 30
    
    # VM config
    VM_EXPIRE_HOURS = 6
    VM_MAX_COUNT = 20
    VM_CREATION_TIMEOUT = 360  # 6 phút (10s * 36)
    
    # Workflow config
    WORKFLOW_FILE_PATH = ".github/workflows/create-vm.yml"
    WORKFLOW_BRANCH = "main"
    
    # Logging config
    LOG_LEVEL = "INFO"
    LOG_FILE = "logs/app.log"
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5
    
    # Thread config
    MONITOR_INTERVAL = 10  # giây
    
    # Regex patterns
    IP_PATTERN = r'Tailscale IP: (\d+\.\d+\.\d+\.\d+)'
    CLOUDFLARE_PATTERN = r'Cloudflare URL: (https://[a-zA-Z0-9-]+\.trycloudflare\.com)'
    
    # Response messages
    MESSAGES = {
        'missing_token': 'Vui lòng nhập GitHub Token',
        'missing_tailscale': 'Vui lòng nhập Tailscale Key',
        'invalid_token': 'GitHub Token không hợp lệ hoặc đã hết hạn',
        'create_repo_failed': 'Không thể tạo repository trên GitHub',
        'create_workflow_failed': 'Không thể tạo workflow file',
        'trigger_failed': 'Không thể trigger GitHub Actions',
        'vm_not_found': 'Không tìm thấy VM',
        'vm_deleted': 'Đã xóa VM',
        'vm_creating': 'VM đang được tạo',
        'vm_ready': 'VM đã sẵn sàng'
    }
    
    # VM default specs
    VM_SPECS = {
        'cpu': '4 vCore',
        'ram': '16GB',
        'ssd': '25GB NVMe',
        'bandwidth': '1.2 Gbps'
    }

class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = "DEBUG"

class ProductionConfig(Config):
    DEBUG = False
    LOG_LEVEL = "INFO"

# Chọn config theo môi trường
def get_config():
    env = os.environ.get('FLASK_ENV', 'production')
    if env == 'development':
        return DevelopmentConfig
    return ProductionConfig
