"""
Configuration & Environment Variables
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Server
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # GitHub API
    GITHUB_API_BASE = os.getenv('GITHUB_API_BASE', 'https://api.github.com')
    GITHUB_API_TIMEOUT = int(os.getenv('GITHUB_API_TIMEOUT', 10))
    GITHUB_RETRY_COUNT = int(os.getenv('GITHUB_RETRY_COUNT', 3))
    
    # Tailscale API
    TAILSCALE_API_BASE = os.getenv('TAILSCALE_API_BASE', 'https://api.tailscale.com/api/v2')
    
    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/vms.db')
    
    # Rate Limiting
    RATE_LIMIT_PER_HOUR = int(os.getenv('RATE_LIMIT_PER_HOUR', 5))
    RATE_LIM
