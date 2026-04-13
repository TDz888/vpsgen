"""
Rate Limiting Middleware
"""
from functools import wraps
from flask import request, jsonify
from database.db_manager import db
from config import config
from utils.logger import logger

def rate_limit(f):
    """Rate limiting decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not config.RATE_LIMIT_ENABLED:
            return f(*args, **kwargs)
        
        # Get client IP
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Check rate limit
        allowed, count, reset_at = db.check_rate_limit(client_ip, config.RATE_LIMIT_PER_HOUR)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return jsonify({
                'success': False,
                'error': f'Rate limit exceeded. Max {config.RATE_LIMIT_PER_HOUR} requests per hour.',
                'retryAfter': reset_at
            }), 429
        
        # Add rate limit headers to response
        response = f(*args, **kwargs)
        
        if isinstance(response, tuple):
            resp, status = response
            if hasattr(resp, 'headers'):
                resp.headers['X-RateLimit-Limit'] = str(config.RATE_LIMIT_PER_HOUR)
                resp.headers['X-RateLimit-Remaining'] = str(config.RATE_LIMIT_PER_HOUR - count)
                resp.headers['X-RateLimit-Reset'] = reset_at
            return resp, status
        else:
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(config.RATE_LIMIT_PER_HOUR)
                response.headers['X-RateLimit-Remaining'] = str(config.RATE_LIMIT_PER_HOUR - count)
                response.headers['X-RateLimit-Reset'] = reset_at
            return response
    
    return decorated_function
