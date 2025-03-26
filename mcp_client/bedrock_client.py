"""
Bedrock client module for MCP client.
"""
import logging
import boto3
from typing import Dict, List, Any
from .server import Server

logger = logging.getLogger(__name__)


class BedrockClient:
    """
    Client for interacting with Amazon Bedrock.
    """
    
    def __init__(self, model_id='us.amazon.nova-lite-v1:0', region=None):
        """
        Initialize the Bedrock client.
        
        Args:
            model_id: Bedrock model ID to use
            region: AWS region for Bedrock
        """
        self.model_id = model_id
        session_kwargs = {}
        if region:
            session_kwargs['region_name'] = region
            
        self.bedrock = boto3.client('bedrock-runtime', **session_kwargs)
        
    def convert_tool_format(self, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert tools to Bedrock Nova format.
        
        Args:
            tools: List of tool definitions
            
        Returns:
            Tool configuration in Bedrock format
        """
        converted_tools = []
        for tool in tools:
            converted_tool = {
                "toolSpec": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "inputSchema": {
                        "json": tool["inputSchema"]
                    }
                }
            }
            converted_tools.append(converted_tool)
        return {"tools": converted_tools}
        
    def invoke_model(self, messages: List[Dict[str, Any]], 
                    system: List[Dict[str, str]], 
                    tool_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke the Bedrock model.
        
        Args:
            messages: Conversation messages
            system: System instructions
            tool_config: Tool configuration
            
        Returns:
            Model response
        """
        try:
            logger.info(f"Calling Bedrock model {self.model_id}")
            logger.info(f"Messages: {messages}")
            logger.info(f"System: {system}")
            logger.info(f"Tool config: {tool_config}")
            response = self.bedrock.converse(
                modelId=self.model_id,
                messages=messages,
                system=system,
                inferenceConfig={
                    "maxTokens": 300,
                    "topP": 0.1,
                    "temperature": 0.3
                },
                toolConfig=tool_config
            )
            return response
        except Exception as e:
            logger.error(f"Error invoking Bedrock model: {e}")
            raise