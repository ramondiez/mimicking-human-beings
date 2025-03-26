"""
Utility functions and classes for MCP servers.
"""
import time
import logging
from urllib.parse import urlparse
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for external service calls.
    
    Prevents cascading failures by failing fast when a service is unavailable.
    """
    def __init__(self, failure_threshold=5, reset_timeout=30):
        """
        Initialize the circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening the circuit
            reset_timeout: Time in seconds before attempting to close the circuit
        """
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.open_until = 0
        self.state = "closed"
        
    async def call(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        """
        Call a function with circuit breaker protection.
        
        Args:
            func: Async function to call
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            The result of the function call
            
        Raises:
            RuntimeError: If the circuit is open
            Any exception raised by the function
        """
        current_time = time.time()
        
        # Check if circuit is open
        if self.state == "open":
            if current_time < self.open_until:
                logger.warning(f"Circuit breaker is open, failing fast")
                raise RuntimeError("Circuit breaker is open")
            
            logger.info(f"Circuit breaker transitioning from open to half-open")
            self.state = "half-open"
            
        try:
            result = await func(*args, **kwargs)
            
            # Success in half-open state closes the circuit
            if self.state == "half-open":
                logger.info(f"Circuit breaker transitioning from half-open to closed")
                self.state = "closed"
                self.failure_count = 0
                
            return result
            
        except Exception as e:
            # Count failures
            self.failure_count += 1
            logger.warning(f"Circuit breaker recorded failure {self.failure_count}/{self.failure_threshold}")
            
            # Open circuit if threshold reached
            if self.failure_count >= self.failure_threshold:
                logger.warning(f"Circuit breaker threshold reached, opening circuit for {self.reset_timeout}s")
                self.state = "open"
                self.open_until = current_time + self.reset_timeout
                
            raise e


def validate_url(url: str) -> str:
    """
    Validate URL to prevent SSRF attacks.
    
    Args:
        url: URL to validate
        
    Returns:
        The validated URL
        
    Raises:
        ValueError: If the URL is invalid or points to an internal resource
    """
    if not url:
        raise ValueError("URL cannot be empty")
        
    parsed = urlparse(url)
    
    # Check scheme
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")
    
    # Block private IPs and localhost
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: no hostname")
        
    if hostname in ('localhost', '127.0.0.1', '::1') or \
       hostname.startswith('192.168.') or \
       hostname.startswith('10.') or \
       hostname.startswith('172.16.'):
        raise ValueError("Access to internal hosts is not allowed")
    
    return url