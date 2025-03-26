"""
Middleware components for MCP servers.
"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Dict, List

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent abuse.
    """
    def __init__(self, app, calls_per_minute=60):
        """
        Initialize rate limiting middleware.
        
        Args:
            app: Starlette application
            calls_per_minute: Maximum number of calls per minute per IP
        """
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.request_timestamps: Dict[str, List[float]] = {}
        
    async def dispatch(self, request, call_next):
        """
        Process a request with rate limiting.
        
        Args:
            request: HTTP request
            call_next: Next middleware in chain
            
        Returns:
            HTTP response
        """
        client_ip = request.client.host
        current_time = time.time()
        
        # Clean old timestamps (older than 60 seconds)
        self.request_timestamps = {
            ip: [ts for ts in timestamps if ts > current_time - 60]
            for ip, timestamps in self.request_timestamps.items()
        }
        
        # Remove empty entries
        self.request_timestamps = {
            ip: timestamps for ip, timestamps in self.request_timestamps.items() 
            if timestamps
        }
        
        # Check rate limit
        if client_ip in self.request_timestamps:
            timestamps = self.request_timestamps[client_ip]
            if len(timestamps) >= self.calls_per_minute:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return JSONResponse(
                    {"error": "Rate limit exceeded"},
                    status_code=429
                )
            timestamps.append(current_time)
        else:
            self.request_timestamps[client_ip] = [current_time]
            
        return await call_next(request)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware for collecting metrics on HTTP requests.
    """
    def __init__(self, app):
        """
        Initialize metrics middleware.
        
        Args:
            app: Starlette application
        """
        super().__init__(app)
        
    async def dispatch(self, request, call_next):
        """
        Process a request and collect metrics.
        
        Args:
            request: HTTP request
            call_next: Next middleware in chain
            
        Returns:
            HTTP response
        """
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        logger.info(f"Request {request.method} {request.url.path} completed in {duration:.3f}s with status {response.status_code}")
        
        return response