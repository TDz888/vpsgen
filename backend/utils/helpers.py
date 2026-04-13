"""
Utility Helper Functions
"""
import secrets
import string
import json
from datetime import datetime, timedelta

def generate_id(length=8):
    """Generate random ID"""
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_username():
    """Generate random username"""
    prefixes = ['user', 'dev', 'test', 'vm', 'node']
    prefix = secrets.choice(prefixes)
    suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    return f"{prefix}_{suffix}"

def generate_password(length=12):
    """Generate strong random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_repo_name(username):
    """Generate unique repository name"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = generate_id(4)
    return f"vps-{username}-{timestamp}-{random_suffix}"

def calculate_expiry(hours=6):
    """Calculate expiry timestamp"""
    return (datetime.now() + timedelta(hours=hours)).isoformat()

def is_expired(expiry_string):
    """Check if VM is expired"""
    if not expiry_string:
        return True
    try:
        expiry = datetime.fromisoformat(expiry_string)
        return datetime.now() > expiry
    except:
        return True

def format_vm_for_response(vm_dict):
    """Format VM data for API response"""
    # Remove sensitive/internal fields
    safe_fields = ['id', 'name', 'username', 'password', 'status', 'repoUrl', 
                   'workflowUrl', 'tailscaleIP', 'novncUrl', 'createdAt', 
                   'expiresAt', 'progress']
    return {k: v for k, v in vm_dict.items() if k in safe_fields}

def safe_json_loads(data, default=None):
    """Safely parse JSON"""
    try:
        return json.loads(data)
    except:
        return default if default is not None else {}

def truncate_string(text, max_length=100):
    """Truncate long strings"""
    if not text:
        return ""
    return text[:max_length] + "..." if len(text) > max_length else text
