"""
Lambda handler for MCP client.
"""
import os
import json
import logging
import sys
from typing import Dict, Any, List

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Debug: Print Python path and available modules
logger.info(f"Python path: {sys.path}")
logger.info(f"Contents of /opt: {os.listdir('/opt') if os.path.exists('/opt') else 'Directory not found'}")
logger.info(f"Contents of /opt/python: {os.listdir('/opt/python') if os.path.exists('/opt/python') else 'Directory not found'}")

# Try to import and list all installed packages
try:
    import pkg_resources
    installed_packages = [f"{pkg.key}=={pkg.version}" for pkg in pkg_resources.working_set]
    logger.info(f"Installed packages: {installed_packages}")
except Exception as e:
    logger.error(f"Error listing installed packages: {str(e)}")

# Try to import specific packages
for package in ['boto3', 'mcp', 'httpx', 'anyio', 'pydantic']:
    try:
        __import__(package)
        logger.info(f"Successfully imported {package}")
    except ImportError as e:
        logger.error(f"Failed to import {package}: {str(e)}")

# Try different import approaches
try:
    # First try direct import
    from mcp_client import MCPClient
    logger.info("Successfully imported MCPClient directly")
except ImportError as e1:
    logger.error(f"Failed to import MCPClient directly: {str(e1)}")
    try:
        # Then try nested import
        from mcp_client.mcp_client import MCPClient
        logger.info("Successfully imported MCPClient from mcp_client.mcp_client")
    except ImportError as e2:
        logger.error(f"Failed to import MCPClient from mcp_client.mcp_client: {str(e2)}")
        # Try to list all available modules
        import pkgutil
        logger.info(f"Available modules: {[name for _, name, _ in pkgutil.iter_modules()]}")
        raise

import asyncio
import boto3

def get_server_configs():
    """
    Get server configurations from environment variables.
    
    Returns:
        List of server configurations
    """
    server_configs = []
    
    # URL fetcher server
    if "URL_FETCHER_URL" in os.environ:
        server_configs.append({
            "name": "url-fetcher",
            "url": f"{os.environ['URL_FETCHER_URL']}/sse"
        })
    
    # Random web server
    if "RANDOM_WEB_URL" in os.environ:
        server_configs.append({
            "name": "random-web",
            "url": f"{os.environ['RANDOM_WEB_URL']}/sse"
        })
    
    return server_configs


async def process_message(message: str):
    """
    Process a message using the MCP client.
    
    Args:
        message: User message
        
    Returns:
        Conversation history
    """
    # Get server configurations
    server_configs = get_server_configs()
    
    # Initialize MCP client
    client = MCPClient(
        server_configs=server_configs,
        bedrock_model_id=os.environ.get("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0"),
        region=os.environ.get("AWS_REGION", "us-east-1")
    )
    
    try:
        # Initialize servers
        await client.initialize_servers()
        
        # Process request
        conversation = await client.process_request(message)
        
        # Clean up
        await client.cleanup()
        
        return conversation
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return [{"role": "assistant", "message": f"Error: {str(e)}"}]


def handler(event, context):
    """
    Lambda handler function.
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        Lambda response
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Extract message from event
        if isinstance(event.get("body"), dict):
            # Body is already a dictionary
            body = event.get("body", {})
        else:
            # Body is a string, parse it as JSON
            body = json.loads(event.get("body", "{}"))
            
        message = body.get("message", "")
        
        if not message:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing message"})
            }
        
        # Process message
        conversation = asyncio.run(process_message(message))
        
        # Format response
        response = {
            "conversation": conversation
        }
        
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response)
        }
    except Exception as e:
        logger.error(f"Error in handler: {str(e)}", exc_info=True)
        
        # Log additional context information that might be useful for debugging
        logger.error(f"Event data: {json.dumps(event)}")
        logger.error(f"Lambda context: Request ID: {context.aws_request_id}, "
                    f"Function: {context.function_name}, "
                    f"Remaining time: {context.get_remaining_time_in_millis()}ms")
        
        # This will cause the Lambda to fail and trigger the DLQ if retries are exhausted
        raise
