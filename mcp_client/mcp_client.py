"""
MCP Client for interacting with multiple MCP servers.
"""
import logging
from typing import Dict, List, Any, Optional
from .server import Server
from .bedrock_client import BedrockClient

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Client for interacting with multiple MCP servers.
    """
    
    def __init__(self, server_configs=None, bedrock_model_id='us.amazon.nova-lite-v1:0', region=None):
        """
        Initialize the MCP client.
        
        Args:
            server_configs: List of server configurations (name, url)
            bedrock_model_id: Bedrock model ID to use
            region: AWS region for Bedrock
        """
        # Initialize Bedrock client
        self.bedrock_client = BedrockClient(model_id=bedrock_model_id, region=region)
        
        # Define our servers
        if server_configs is None:
            server_configs = [
                {"name": "url-fetcher", "url": "http://localhost:8001/sse"},
                {"name": "random-web", "url": "http://localhost:8003/sse"}
            ]
            
        self.servers = [Server(config["name"], config["url"]) for config in server_configs]
        
        # Map of tool names to servers
        self.tool_server_map = {}
        
        # System prompt for the model
        self.system_prompt = """
            Choose the appropriate tool based on the user's question. If no tool is needed, reply directly.
            Have in mind that you will get new context during your iteration.
            When a tool returns information that should be used as input to another tool, make sure to extract and use that information correctly. For example, if RandomWeb returns a URL, use that exact URL as input to the fetch tool.
            
            IMPORTANT: When you need to use a tool, you must ONLY respond with the exact JSON object format below, nothing else:
            {
                "tool": "tool-name",
                "arguments": {
                    "argument-name": "value"
                }
            }

            After receiving a tool's response:
            1. Transform the raw data into a natural, conversational response
            2. Keep responses concise but informative
            3. Focus on the most relevant information
            4. Use appropriate context from the user's question
            5. Avoid simply repeating the raw data

            Please use only the tools that are explicitly defined above.
        """

    async def initialize_servers(self):
        """
        Initialize all servers and map tools to servers.
        """
        for server in self.servers:
            try:
                await server.initialize()
                tools = await server.list_tools()
                
                # Map each tool to its server
                for tool in tools:
                    self.tool_server_map[tool["name"]] = server
                    
            except Exception as e:
                logger.error(f"Failed to initialize {server.name}: {e}")

    async def get_all_tools(self) -> List[Dict[str, Any]]:
        """
        Get all tools from all servers.
        
        Returns:
            List of all available tools
        """
        all_tools = []
        for server in self.servers:
            try:
                tools = await server.list_tools()
                all_tools.extend(tools)
            except Exception as e:
                logger.error(f"Error getting tools from {server.name}: {e}")
        return all_tools

    async def process_request(self, message: str) -> List[Dict[str, Any]]:
        """
        Process a request using all available tools from all servers.
        
        Args:
            message: User message
            
        Returns:
            List of conversation messages
        """
        # Initialize servers if not already done
        if not self.tool_server_map:
            await self.initialize_servers()
            
        if not self.tool_server_map:
            logger.error("No tools available from any server")
            return [{"role": "assistant", "content": [{"text": "No tools available. Make sure the servers are running."}]}]
            
        # Collect all tools from all servers
        all_tools = await self.get_all_tools()
        
        if not all_tools:
            logger.error("No tools available")
            return [{"role": "assistant", "content": [{"text": "No tools available. Make sure the servers are running."}]}]
            
        # Convert tools to Bedrock format
        tool_config = self.bedrock_client.convert_tool_format(all_tools)
        logger.info(f"Available tools: {[t['name'] for t in all_tools]}")
        
        # Create the initial message
        messages = [{
            "role": "user",
            "content": [{"text": message}]
        }]
        
        # System message to guide the model
        system = [{"text": self.system_prompt}]
        
        conversation_history = []
        conversation_history.append({"role": "user", "message": message})
        
        try:
            # Start conversation loop
            while True:
                # Call Bedrock with Nova

                response = self.bedrock_client.invoke_model(
                    messages=messages,
                    system=system,
                    tool_config=tool_config
                )
                
                output_message = response.get('output', {}).get('message')
                if not output_message:
                    logger.warning("No output message in response")
                    break

                # Add the response to messages
                messages.append(output_message)
                
                # Process the content
                tool_used = False
                assistant_message = {"role": "assistant", "message": ""}
                
                for content in output_message.get('content', []):
                    if 'text' in content:
                        assistant_message["message"] = content['text']
                        conversation_history.append(assistant_message)
                        
                    elif 'toolUse' in content:
                        tool_used = True
                        tool = content['toolUse']
                        tool_name = tool['name']
                        
                        tool_message = {
                            "role": "assistant", 
                            "tool_use": {
                                "name": tool_name,
                                "input": tool['input']
                            }
                        }
                        conversation_history.append(tool_message)
                        
                        # Find the server that has this tool
                        if tool_name in self.tool_server_map:
                            server = self.tool_server_map[tool_name]
                            try:
                                logger.info(f"Calling tool {tool_name} with input {tool['input']}")
                                tool_response = await server.execute_tool(
                                    tool_name,
                                    tool['input']
                                )
                                
                                # Extract text from the response
                                response_text = str(tool_response)
                                
                                tool_result = {
                                    "role": "tool",
                                    "name": tool_name,
                                    "result": response_text
                                }
                                conversation_history.append(tool_result)
                                
                                # Add tool response as a user message
                                messages.append({
                                    "role": "user",
                                    "content": [{
                                        "toolResult": {
                                            "toolUseId": tool['toolUseId'],
                                            "content": [{"text": response_text}]
                                        }
                                    }]
                                })
                            except Exception as e:
                                logger.error(f"Tool call failed: {str(e)}")
                                # Add error response as user message
                                error_message = f"Error: {str(e)}"
                                
                                tool_result = {
                                    "role": "tool",
                                    "name": tool_name,
                                    "error": error_message
                                }
                                conversation_history.append(tool_result)
                                
                                messages.append({
                                    "role": "user",
                                    "content": [{
                                        "toolResult": {
                                            "toolUseId": tool['toolUseId'],
                                            "content": [{"text": error_message}],
                                            "status": "error"
                                        }
                                    }]
                                })
                        else:
                            logger.error(f"No server found for tool: {tool_name}")
                            # Add error response as user message
                            error_message = f"Error: Tool {tool_name} not available"
                            
                            tool_result = {
                                "role": "tool",
                                "name": tool_name,
                                "error": error_message
                            }
                            conversation_history.append(tool_result)
                            
                            messages.append({
                                "role": "user",
                                "content": [{
                                    "toolResult": {
                                        "toolUseId": tool['toolUseId'],
                                        "content": [{"text": error_message}],
                                        "status": "error"
                                    }
                                }]
                            })
                
                # Check if we're done
                if not tool_used or response.get('stopReason') != 'tool_use':
                    break
                    
            return conversation_history
                    
        except Exception as e:
            logger.error(f"Error in process_request: {str(e)}")
            return [{"role": "assistant", "content": [{"text": f"Error: {str(e)}"}]}]
    
    async def cleanup(self):
        """
        Clean up all server connections.
        """
        for server in self.servers:
            await server.cleanup()
