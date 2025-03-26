"""
ROI Calculator Server Example

This server provides a tool to calculate ROI.
"""
import logging
import os
from typing import Dict, List, Any

import mcp.types as types
from mcp_server import MCPBaseServer, Settings

logger = logging.getLogger(__name__)


class ROICalculatorServer(MCPBaseServer):
    """
    Server that provides a tool to calculate ROI.
    """
    
    def register_tools(self):
        """
        Register the ROI calculation tool with the MCP server.
        """
        @self.mcp_server.call_tool()
        async def calculate_roi(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
            """
            Tool handler for ROI calculation.
            
            Args:
                name: Tool name
                arguments: Tool arguments
                
            Returns:
                List of content items
                
            Raises:
                ValueError: If the tool name is unknown or arguments are invalid
            """
            logger.info(f"ROI calculation requested with arguments: {arguments}")
            
            try:
                if name != "ROI":
                    raise ValueError(f"Unknown tool: {name}")
                
                if "revenue" not in arguments:
                    raise ValueError("Missing required argument 'revenue'")
                
                if "months" not in arguments:
                    raise ValueError("Missing required argument 'months'")
                
                revenue = float(arguments['revenue'])
                months = float(arguments['months'])
                
                if revenue < 0:
                    raise ValueError("Revenue cannot be negative")
                
                if months <= 0:
                    raise ValueError("Months must be positive")
                
                # Calculate ROI (revenue * months * 9)
                result = revenue * months * 9
                
                logger.info(f"ROI calculation result: {result}")
                return [types.TextContent(type="text", text=str(result))]
                
            except Exception as e:
                logger.error(f"Error calculating ROI: {str(e)}")
                return [types.TextContent(type="text", text=f"Error calculating ROI: {str(e)}")]
        
        @self.mcp_server.list_tools()
        async def list_tools() -> List[types.Tool]:
            """
            List available tools.
            
            Returns:
                List of tools
            """
            return [
                types.Tool(
                    name="ROI",
                    description="Calculate ROI given revenue and months",
                    inputSchema={
                        "type": "object",
                        "required": ["revenue", "months"],
                        "properties": {
                            "revenue": {
                                "type": "number",
                                "description": "Revenue of a company",
                            },
                            "months": {
                                "type": "number",
                                "description": "Number of months",
                            }
                        },
                    },
                )
            ]


if __name__ == "__main__":
    # Get port from environment variable or use default
    port = int(os.environ.get("SERVER_PORT", 8002))
    
    # Create and run the server
    settings = Settings(
        server_name="roi-calculator-server",
        server_port=port,
    )
    
    server = ROICalculatorServer(settings)
    server.run()