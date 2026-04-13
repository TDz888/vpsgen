"""
Token & Input Validators
"""
import re
from utils.logger import logger

# Pre-compiled patterns for performance
GITHUB_TOKEN_PATTERN = re.compile(r'^ghp_[A-Za-z0-9]{36,}$')
TAILSCALE_KEY_PATTERN = re.compile(r'^tskey-(?:auth|client)-[A-Za-z0-9]+-[A-Za-z0-9]+$')
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,20}$')
PASSWORD_PATTERN = re.compile(r'^.{8,50}$')

def validate_github_token(token):
    """Validate GitHub token format"""
    if not token:
        return False, "Token cannot be empty"
    if not GITHUB_TOKEN_PATTERN.match(token):
        return False, "Invalid GitHub token format (should start with 'ghp_')"
    return True, None

def validate_tailscale_key(key):
    """Validate Tailscale key format"""
    if not key:
        return False, "Tailscale key cannot be empty"
    if not TAILSCALE_KEY_PATTERN.match(key):
        return False, "Invalid Tailscale key format (should start with 'tskey-')"
    return True, None

def validate_username(username):
    """Validate username format"""
    if not username:
        return False, "Username cannot be empty"
    if not USERNAME_PATTERN.match(username):
        return False, "Username must be 3-20 characters (letters, numbers, underscore)"
    return True, None

def validate_password(password):
    """Validate password strength"""
    if not password:
        return False, "Password cannot be empty"
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    return True, None

def sanitize_input(text, max_length=100):
    """Sanitize user input"""
    if not text:
        return ""
    # Remove dangerous characters
    text = re.sub(r'[<>"\'&]', '', text)
    # Truncate
    return text[:max_length]

logger.info("Validators module loaded")
