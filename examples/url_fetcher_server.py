"""
URL Fetcher Server Example

This server provides a tool to fetch only the title from URLs.
"""
import logging
import httpx
import os
from typing import Dict, List, Any
import re
from bs4 import BeautifulSoup

import mcp.types as types
from mcp_server import MCPBaseServer, Settings, validate_url

logger = logging.getLogger(__name__)


class URLFetcherServer(MCPBaseServer):
    """
    Server that provides a tool to fetch only the title from URLs.
    """
    
    def register_tools(self):
        """
        Register the URL fetcher tool with the MCP server.
        """
        @self.mcp_server.call_tool()
        async def fetch_url(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
            """
            Tool handler for URL title fetching.
            
            Args:
                name: Tool name
                arguments: Tool arguments
                
            Returns:
                List of content items with just the title
                
            Raises:
                ValueError: If the tool name is unknown or arguments are invalid
            """
            logger.info(f"URL title fetch requested with arguments: {arguments}")
            
            try:
                if name != "URLTitleFetcher":
                    raise ValueError(f"Unknown tool: {name}")
                
                if "url" not in arguments:
                    raise ValueError("Missing required argument 'url'")
                
                url = arguments["url"]
                
                if not validate_url(url):
                    raise ValueError(f"Invalid URL: {url}")
                
                # Fetch the URL content
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, follow_redirects=True, timeout=10.0)
                    response.raise_for_status()
                    
                    # Get content type
                    content_type = response.headers.get("content-type", "")
                    
                    # Handle HTML content to extract title
                    if "text/html" in content_type:
                        html_content = response.text
                        # Use BeautifulSoup to extract the title
                        soup = BeautifulSoup(html_content, 'html.parser')
                        title = soup.title.string if soup.title else "No title found"
                        content = f"Title: {title.strip()}"
                    elif "text/plain" in content_type:
                        # For plain text, try to find a title-like first line
                        text_content = response.text
                        first_line = text_content.strip().split('\n')[0][:100]
                        content = f"First line: {first_line}"
                    else:
                        content = f"Content type {content_type} not supported for title extraction"
                
                logger.info(f"Successfully fetched title from URL: {url}")
                return [types.TextContent(type="text", text=content)]
                
            except httpx.HTTPStatusError as e:
                error_msg = f"HTTP error: {e.response.status_code} - {e.response.reason_phrase}"
                logger.error(error_msg)
                return [types.TextContent(type="text", text=error_msg)]
                
            except httpx.RequestError as e:
                error_msg = f"Request error: {str(e)}"
                logger.error(error_msg)
                return [types.TextContent(type="text", text=error_msg)]
                
            except Exception as e:
                error_msg = f"Error fetching URL title: {str(e)}"
                logger.error(error_msg)
                return [types.TextContent(type="text", text=error_msg)]
        
        @self.mcp_server.list_tools()
        async def list_tools() -> List[types.Tool]:
            """
            List available tools.
            
            Returns:
                List of tools
            """
            return [
                types.Tool(
                    name="URLTitleFetcher",
                    description="Fetch only the title from a URL",
                    inputSchema={
                        "type": "object",
                        "required": ["url"],
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "URL to fetch title from",
                            }
                        },
                    },
                )
            ]


if __name__ == "__main__":
    # Get port from environment variable or use default
    port = int(os.environ.get("SERVER_PORT", 8001))
    
    # Create and run the server
    settings = Settings(
        server_name="url-fetcher-server",
        server_port=port,
    )
    
    server = URLFetcherServer(settings)
    server.run()
