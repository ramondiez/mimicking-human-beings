"""
Server connection module for MCP client.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)


class Server:
    """
    Manages MCP server connections and tool execution.
    """

    def __init__(self, name: str, url: str) -> None:
        """
        Initialize a server connection.
        
        Args:
            name: Server name
            url: Server URL for SSE connection
        """
        self.name: str = name
        self.url: str = url
        self.session: Optional[ClientSession] = None
        self.sse_context = None
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self.capabilities: Optional[Dict[str, Any]] = None

    async def initialize(self) -> None:
        """
        Initialize the server connection.
        
        Raises:
            Exception: If connection fails
        """
        try:
            logger.info(f"Connecting to server {self.name} at {self.url}")
            self.sse_context = sse_client(self.url)
            streams = await self.sse_context.__aenter__()
            self.session = ClientSession(streams[0], streams[1])
            await self.session.__aenter__()
            self.capabilities = await self.session.initialize()
            logger.info(f"Successfully connected to server {self.name}")
        except Exception as e:
            logger.error(f"Error initializing server {self.name}: {e}")
            await self.cleanup()
            raise

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available tools from the server.
        
        Returns:
            List of tool definitions
            
        Raises:
            RuntimeError: If server is not initialized
        """
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")
        
        tools_response = await self.session.list_tools()
        tools = []
        
        for tool in tools_response.tools:
            tool_info = {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema
            }
            tools.append(tool_info)
            logger.info(f"Available tool on {self.name}: {tool.name}")
        
        return tools

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute a tool with retry mechanism.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            
        Returns:
            Tool execution result
            
        Raises:
            RuntimeError: If server is not initialized
            Exception: If tool execution fails
        """
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        try:
            logger.info(f"Executing tool {tool_name} on server {self.name}")
            result = await self.session.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name} on server {self.name}: {e}")
            raise

    async def cleanup(self) -> None:
        """
        Clean up server resources.
        """
        async with self._cleanup_lock:
            try:
                if self.session:
                    try:
                        await self.session.__aexit__(None, None, None)
                    except Exception as e:
                        logger.warning(f"Warning during session cleanup for {self.name}: {e}")
                    finally:
                        self.session = None

                if self.sse_context:
                    try:
                        await self.sse_context.__aexit__(None, None, None)
                    except Exception as e:
                        logger.warning(f"Warning during SSE context cleanup for {self.name}: {e}")
                    finally:
                        self.sse_context = None
            except Exception as e:
                logger.error(f"Error during cleanup of server {self.name}: {e}")