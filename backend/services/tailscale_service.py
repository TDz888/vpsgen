"""
Tailscale API Service
"""
import requests
from utils.logger import logger
from config import config

class TailscaleService:
    """Tailscale API operations"""
    
    def __init__(self):
        self.base_url = config.TAILSCALE_API_BASE
        self.timeout = config.GITHUB_API_TIMEOUT
    
    def validate_key(self, tailscale_key):
        """Validate Tailscale auth key"""
        try:
            # Tailscale API doesn't have a direct key validation endpoint
            # We can check the format and make a lightweight request
            headers = {
                'Authorization': f'Bearer {tailscale_key}'
            }
            
            # Try to get tailnet info (will fail if key is invalid)
            response = requests.get(
                f'{self.base_url}/tailnet',
                headers=headers,
                timeout=5
            )
            
            # Any 2xx response means key has some access
            # 401 means invalid key
            if response.status_code == 401:
                return False, "Invalid Tailscale key"
            
            # Key is valid (might have limited permissions but works for auth)
            return True, "Key appears valid"
            
        except requests.exceptions.Timeout:
            logger.warning("Tailscale API timeout during validation")
            # Don't block creation on timeout
            return True, "Timeout, assuming key is valid"
        except Exception as e:
            logger.error(f"Tailscale key validation error: {e}")
            return True, "Validation skipped"
    
    def get_device_info(self, tailscale_key, device_name):
        """Get device info by name"""
        try:
            headers = {
                'Authorization': f'Bearer {tailscale_key}'
            }
            
            response = requests.get(
                f'{self.base_url}/devices',
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                devices = response.json().get('devices', [])
                for device in devices:
                    if device.get('hostname') == device_name:
                        return device
            return None
            
        except Exception as e:
            logger.error(f"Get device info error: {e}")
            return None

# Global Tailscale service instance
tailscale_service = TailscaleService()
