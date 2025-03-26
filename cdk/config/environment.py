"""
Environment configuration for MCP Cluster CDK project.
"""
from typing import Dict, Any


class Environment:
    """Environment configuration for MCP Cluster CDK project."""
    
    @staticmethod
    def get_services() -> Dict[str, Any]:
        """
        Get service configurations.
        
        Returns:
            Dictionary of service configurations
        """
        return {
            "url-fetcher": {
                "name": "url-fetcher",
                "dockerfile": "docker/url-fetcher",  # Direct path to the Dockerfile
                "port": 8001,
                "path_pattern": "/url-fetcher*",
                "environment": {
                    "LOG_LEVEL": "INFO",
                    "SERVER_PORT": "8001",
                    "SERVER_HOST": "0.0.0.0",
                    "SERVER_DEBUG": "false",
                }
            },
            "random-web": {
                "name": "random-web",
                "dockerfile": "docker/random-web",  # Direct path to the Dockerfile
                "port": 8003,
                "path_pattern": "/random-web*",
                "environment": {
                    "LOG_LEVEL": "INFO",
                    "SERVER_PORT": "8003",
                    "SERVER_HOST": "0.0.0.0",
                    "SERVER_DEBUG": "false",
                }
            }
        }
