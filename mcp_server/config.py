"""
Configuration management for MCP servers.
"""
try:
    # Try importing from pydantic-settings (Pydantic v2)
    from pydantic_settings import BaseSettings
    from pydantic import Field
except ImportError:
    # Fall back to Pydantic v1
    from pydantic import BaseSettings, Field

from typing import List, Optional


class Settings(BaseSettings):
    """
    Server configuration settings loaded from environment variables.
    
    Environment variables are prefixed with SERVER_, e.g.:
    SERVER_PORT=8001 sets the port to 8001
    """
    # Server settings
    server_name: str = "mcp-server"
    server_port: int = Field(8001, ge=1024, le=65535)
    server_host: str = "0.0.0.0"
    log_level: str = "info"
    debug: bool = False
    
    # Security settings
    cors_origins: List[str] = ["*"]
    cors_methods: List[str] = ["GET", "POST"]
    rate_limit: int = 60  # requests per minute
    
    # Request settings
    max_content_length: int = 1_000_000  # 1MB limit
    request_timeout: float = 10.0
    
    # Circuit breaker settings
    circuit_failure_threshold: int = 5
    circuit_reset_timeout: int = 30
    
    # Metrics settings
    enable_metrics: bool = True
    metrics_port: Optional[int] = None  # If None, metrics are exposed on the main port
    
    class Config:
        env_prefix = "SERVER_"
        case_sensitive = False