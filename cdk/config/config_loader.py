"""
Configuration loader for MCP Cluster CDK project.
"""
import os
import yaml
from typing import Dict, Any, Optional
import aws_cdk as cdk


class ConfigLoader:
    """Configuration loader for MCP Cluster CDK project."""
    
    def __init__(self, config_file: str = "config/settings.yaml"):
        """
        Initialize the configuration loader.
        
        Args:
            config_file: Path to the configuration file
        """
        self.config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), config_file)
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.
        
        Returns:
            Configuration dictionary
        """
        with open(self.config_file, 'r') as file:
            return yaml.safe_load(file)
    
    def get_environment_config(self, env_name: str = "dev") -> Dict[str, Any]:
        """
        Get environment-specific configuration.
        
        Args:
            env_name: Environment name
            
        Returns:
            Environment-specific configuration
        """
        # Start with default configuration
        default_config = self.config.get("default", {})
        
        # Override with environment-specific configuration
        env_config = self.config.get(env_name, {})
        
        # Merge configurations
        merged_config = self._deep_merge(default_config, env_config)
        
        return merged_config
    
    def _deep_merge(self, dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.
        
        Args:
            dict1: First dictionary
            dict2: Second dictionary
            
        Returns:
            Merged dictionary
        """
        result = dict1.copy()
        
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result
    
    def get_vpc_config(self, env_name: str = "dev") -> Dict[str, Any]:
        """
        Get VPC configuration.
        
        Args:
            env_name: Environment name
            
        Returns:
            VPC configuration
        """
        env_config = self.get_environment_config(env_name)
        return env_config.get("vpc", {})
    
    def get_ecs_config(self, env_name: str = "dev") -> Dict[str, Any]:
        """
        Get ECS configuration.
        
        Args:
            env_name: Environment name
            
        Returns:
            ECS configuration
        """
        env_config = self.get_environment_config(env_name)
        return env_config.get("ecs", {})
    
    def get_lambda_config(self, env_name: str = "dev") -> Dict[str, Any]:
        """
        Get Lambda configuration.
        
        Args:
            env_name: Environment name
            
        Returns:
            Lambda configuration
        """
        env_config = self.get_environment_config(env_name)
        return env_config.get("lambda", {})
    
    def get_load_balancer_config(self, env_name: str = "dev") -> Dict[str, Any]:
        """
        Get Load Balancer configuration.
        
        Args:
            env_name: Environment name
            
        Returns:
            Load Balancer configuration
        """
        env_config = self.get_environment_config(env_name)
        return env_config.get("load_balancer", {})
    
    @staticmethod
    def get_cdk_environment() -> cdk.Environment:
        """
        Get CDK environment.
        
        Returns:
            CDK environment with explicit region and account
        """
        # Use environment with explicit region and account from AWS CLI configuration
        import boto3
        session = boto3.Session()
        region = session.region_name
        account = session.client('sts').get_caller_identity().get('Account')
        
        return cdk.Environment(account=account, region=region)
