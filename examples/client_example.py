#!/usr/bin/env python3
"""
Example script demonstrating the use of the MCP client.
"""
import asyncio
import logging
import sys
import os
from logging.handlers import RotatingFileHandler

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mcp_client import MCPClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Configure logging to file
#log_file = 'mcp_client.log'
#handler = RotatingFileHandler(
#    log_file,
#    maxBytes=1024 * 1024,  # 1MB
#    backupCount=5
#)
#formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#handler.setFormatter(formatter)
#
## Configure root logger
#logging.basicConfig(
#    level=logging.INFO,
#    handlers=[handler]
#)
logger = logging.getLogger(__name__)


async def main():
    """
    Main function demonstrating the use of MCPClient.
    """
    # Initialize the client with default server configurations
    client = MCPClient()
    
    try:
        print("Initializing connections to MCP servers...")
        await client.initialize_servers()
        
        while True:
            print("\nEnter your message (or 'quit' to exit):")
            message = input("> ").strip()

            if message.lower() in ['quit', 'exit', 'q']:
                print("Exiting program...")
                break

            if not message:
                print("Please enter a valid message")
                continue

            try:
                print("\nProcessing message...")
                conversation = await client.process_request(message)
                
                # Print the conversation in a user-friendly format
                for msg in conversation:
                    if msg["role"] == "user":
                        print(f"\nUser: {msg.get('message', '')}")
                    elif msg["role"] == "assistant":
                        if "tool_use" in msg:
                            tool = msg["tool_use"]
                            print(f"\nAssistant: Using tool {tool['name']} with input: {tool['input']}")
                        else:
                            print(f"\nAssistant: {msg.get('message', '')}")
                    elif msg["role"] == "tool":
                        if "error" in msg:
                            print(f"\nTool {msg['name']} error: {msg['error']}")
                        else:
                            print(f"\nTool {msg['name']} response: {msg['result']}")
                
                print("\nProcessing complete")

            except KeyboardInterrupt:
                print("\nOperation cancelled by user")
                break
            except Exception as e:
                print(f"\nError processing message: {e}")
                logger.exception("Detailed error information:")
                continue
    finally:
        # Clean up resources
        await client.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
        sys.exit(0)