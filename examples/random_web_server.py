"""
Random Web Server Example

This server provides tools to calculate ROI and return random web URLs.
"""
import logging
import random
import os
from typing import Dict, List, Any

import mcp.types as types
from mcp_server import MCPBaseServer, Settings

logger = logging.getLogger(__name__)


class RandomWebServer(MCPBaseServer):
    """
    Server that provides tools to calculate ROI and return random web URLs.
    """
    
    def __init__(self, settings: Settings = None):
        """
        Initialize the server with a list of popular websites.
        
        Args:
            settings: Server settings
        """
        super().__init__(settings)
        
        # List of popular websites to return randomly
        self.websites = [
            "http://www.example.com",
            "http://www.google.com",
            "http://www.github.com",
            "http://www.stackoverflow.com",
            "http://www.wikipedia.org",
            "http://www.reddit.com",
            "http://www.twitter.com",
            "http://www.amazon.com",
            "http://www.nytimes.com",
            "http://www.bbc.com",
            "http://www.cnn.com",
            "http://www.marca.com"
        ]
    
    def register_tools(self):
        """
        Register the ROI calculation and RandomWeb tools with the MCP server.
        """
        @self.mcp_server.call_tool()
        async def random_web(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
            """
            Tool handler for returning a random web URL.
            
            Args:
                name: Tool name
                arguments: Tool arguments (not used)
                
            Returns:
                List of content items
                
            Raises:
                ValueError: If the tool name is unknown
            """
            logger.info(f"Random web requested with arguments: {arguments}")
            
            try:
                if name != "RandomWeb":
                    raise ValueError(f"Unknown tool: {name}")
                
                # Select a random website from the list
                website = random.choice(self.websites)
                
                logger.info(f"Returning random website: {website}")
                return [types.TextContent(type="text", text=website)]
                
            except Exception as e:
                logger.error(f"Error returning random web: {str(e)}")
                return [types.TextContent(type="text", text=f"Error returning random web: {str(e)}")]
        
        @self.mcp_server.list_tools()
        async def list_tools() -> List[types.Tool]:
            """
            List available tools.
            
            Returns:
                List of tools
            """
            return [
                types.Tool(
                    name="RandomWeb",
                    description="Return a random web URL",
                    inputSchema={
                        "type": "object",
                        "required": [],
                        "properties": {},
                    },
                )
            ]


if __name__ == "__main__":
    # Get port from environment variable or use default
    port = int(os.environ.get("SERVER_PORT", 8003))
    
    # Create and run the server
    settings = Settings(
        server_name="random-web-server",
        server_port=port,
    )
    
    server = RandomWebServer(settings)
    server.run()