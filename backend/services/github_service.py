"""
GitHub API Service with Connection Pooling & Retry Logic
"""
import requests
import base64
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from utils.logger import logger
from config import config

class GitHubService:
    """GitHub API operations with retry and connection pooling"""
    
    def __init__(self):
        self.base_url = config.GITHUB_API_BASE
        self.timeout = config.GITHUB_API_TIMEOUT
        self.session = self._create_session()
    
    def _create_session(self):
        """Create session with connection pooling and retry"""
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=config.GITHUB_RETRY_COUNT,
            backoff_factor=1,
            status_forcelist=[408, 429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"]
        )
        
        # Connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        
        return session
    
    def _headers(self, token):
        """Build request headers"""
        return {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Singularity-VPS/2.0'
        }
    
    def validate_token(self, token):
        """Validate GitHub token and check scopes"""
        try:
            # Get user info
            response = self.session.get(
                f'{self.base_url}/user',
                headers=self._headers(token),
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.warning(f"Token validation failed: {response.status_code}")
                return False, f"Invalid token (HTTP {response.status_code})"
            
            user_data = response.json()
            username = user_data.get('login')
            
            # Check token scopes (via separate endpoint)
            response = self.session.get(
                f'{self.base_url}/user/repos',
                headers=self._headers(token),
                timeout=self.timeout
            )
            
            scopes = response.headers.get('X-OAuth-Scopes', '')
            
            if 'repo' not in scopes:
                return False, "Token missing 'repo' scope"
            if 'workflow' not in scopes:
                return False, "Token missing 'workflow' scope"
            
            logger.info(f"Token validated for user: {username}")
            return True, {'username': username, 'scopes': scopes}
            
        except requests.exceptions.Timeout:
            logger.error("GitHub API timeout during token validation")
            return False, "Connection timeout"
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return False, str(e)
    
    def create_repository(self, token, repo_name, description=""):
        """Create a new GitHub repository"""
        try:
            data = {
                'name': repo_name,
                'private': False,
                'auto_init': True,
                'description': description or f'VPS created by Singularity Club'
            }
            
            response = self.session.post(
                f'{self.base_url}/user/repos',
                headers=self._headers(token),
                json=data,
                timeout=self.timeout
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"Failed to create repo: {response.status_code} - {response.text}")
                return None, f"Failed to create repository: {response.text}"
            
            repo_data = response.json()
            
            logger.info(f"Repository created: {repo_data.get('html_url')}")
            return {
                'name': repo_data.get('name'),
                'full_name': repo_data.get('full_name'),
                'url': repo_data.get('html_url'),
                'clone_url': repo_data.get('clone_url'),
                'owner': repo_data.get('owner', {}).get('login')
            }, None
            
        except Exception as e:
            logger.error(f"Repository creation error: {e}")
            return None, str(e)
    
    def create_workflow_file(self, token, owner, repo, vm_config):
        """Create GitHub Actions workflow file"""
        try:
            workflow_content = self._generate_workflow_content(vm_config)
            
            # Encode to base64
            content_bytes = workflow_content.encode('utf-8')
            content_base64 = base64.b64encode(content_bytes).decode('utf-8')
            
            workflow_path = '.github/workflows/vps.yml'
            
            # Check if file exists
            check_url = f'{self.base_url}/repos/{owner}/{repo}/contents/{workflow_path}'
            check_response = self.session.get(
                check_url,
                headers=self._headers(token),
                timeout=self.timeout
            )
            
            data = {
                'message': f'Create VPS workflow for {vm_config.get("name")}',
                'content': content_base64
            }
            
            if check_response.status_code == 200:
                # File exists, need SHA to update
                data['sha'] = check_response.json().get('sha')
            
            # Create/update file
            response = self.session.put(
                check_url,
                headers=self._headers(token),
                json=data,
                timeout=self.timeout
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"Failed to create workflow: {response.status_code}")
                return None, f"Failed to create workflow: {response.text}"
            
            workflow_url = f"https://github.com/{owner}/{repo}/actions"
            logger.info(f"Workflow created: {workflow_url}")
            
            return workflow_url, None
            
        except Exception as e:
            logger.error(f"Workflow creation error: {e}")
            return None, str(e)
    
    def _generate_workflow_content(self, vm_config):
        """Generate workflow YAML content"""
        name = vm_config.get('name', 'vps')
        username = vm_config.get('username', 'user')
        password = vm_config.get('password', 'pass')
        tailscale_key = vm_config.get('tailscale_key', '')
        startup_script = vm_config.get('startup_script', '')
        
        script_section = ""
        if startup_script:
            script_section = f"""
        # Custom startup script
        echo '{startup_script}' | base64 -d > /tmp/startup.sh
        chmod +x /tmp/startup.sh
        /tmp/startup.sh
"""
        
        return f'''name: VPS - {name}

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
      
    - name: Setup VPS Environment
      run: |
        echo "=== Singularity Club VPS ==="
        echo "VM Name: {name}"
        echo "Username: {username}"
        echo "Created: $(date)"
        echo "Expires: $(date -d '+{config.VM_LIFETIME_HOURS} hours')"
        
        # Install packages
        sudo apt-get update -qq
        sudo apt-get install -y curl wget git unzip openssh-server \\
            xfce4 xfce4-goodies tightvncserver novnc websockify \\
            python3 python3-pip htop neofetch
        
        # Create user
        sudo useradd -m -s /bin/bash {username}
        echo "{username}:{password}" | sudo chpasswd
        sudo usermod -aG sudo {username}
        
        # Configure SSH
        sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config
        sudo sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
        sudo service ssh start
        
        # Install Tailscale
        curl -fsSL https://tailscale.com/install.sh | sh
        sudo tailscale up --authkey={tailscale_key} --hostname={name}
        
        # Get Tailscale IP
        TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "pending")
        echo "Tailscale IP: $TAILSCALE_IP"
        
        # Setup VNC
        sudo -u {username} mkdir -p ~/.vnc
        sudo -u {username} bash -c "echo '{password}' | vncpasswd -f > ~/.vnc/passwd"
        sudo -u {username} chmod 600 ~/.vnc/passwd
        sudo -u {username} vncserver :1 -geometry 1280x800 -depth 24
        
        # Start noVNC
        websockify --web /usr/share/novnc 6080 localhost:5901 &
{script_section}
        echo "=== VPS Ready ==="
        echo "Username: {username}"
        echo "Password: {password}"
        echo "Tailscale IP: $TAILSCALE_IP"
        echo "noVNC: http://localhost:6080/vnc.html"
        
    - name: Keep Alive ({config.VM_LIFETIME_HOURS} hours)
      run: |
        echo "VPS running for {config.VM_LIFETIME_HOURS} hours..."
        for i in $(seq 1 {config.VM_LIFETIME_HOURS * 60}); do
          echo "Runtime: $i/{config.VM_LIFETIME_HOURS * 60} minutes"
          sleep 60
        done
'''
    
    def trigger_workflow(self, token, owner, repo):
        """Trigger workflow dispatch"""
        try:
            # Get workflow ID
            workflows_url = f'{self.base_url}/repos/{owner}/{repo}/actions/workflows'
            response = self.session.get(
                workflows_url,
                headers=self._headers(token),
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.warning(f"Could not fetch workflows: {response.status_code}")
                return True
            
            workflows = response.json().get('workflows', [])
            if not workflows:
                logger.warning("No workflows found")
                return True
            
            workflow_id = workflows[0].get('id')
            
            # Trigger workflow
            trigger_url = f'{self.base_url}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches'
            response = self.session.post(
                trigger_url,
                headers=self._headers(token),
                json={'ref': 'main'},
                timeout=self.timeout
            )
            
            logger.info(f"Workflow triggered for {owner}/{repo}")
            return True
            
        except Exception as e:
            logger.error(f"Trigger workflow error: {e}")
            return True  # Still return True as VM is created
    
    def get_rate_limit(self, token):
        """Get GitHub API rate limit status"""
        try:
            response = self.session.get(
                f'{self.base_url}/rate_limit',
                headers=self._headers(token),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return None

# Global GitHub service instance
github_service = GitHubService()
