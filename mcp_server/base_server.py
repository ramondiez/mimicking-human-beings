"""
Base server implementation for MCP servers.
"""
import logging
import time
import signal
import sys
import uuid
from typing import Dict, List, Any, Optional, Callable, Awaitable

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request

from mcp.server import Server
from mcp.server.sse import SseServerTransport

from .config import Settings
from .middleware import RateLimitMiddleware, MetricsMiddleware
from .utils import CircuitBreaker

# Optional Prometheus metrics
try:
    from prometheus_client import start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)


class MCPBaseServer:
    """
    Base class for MCP servers.
    
    Provides common functionality for MCP servers:
    - HTTP server with SSE transport
    - Health check endpoint
    - Metrics endpoint
    - Middleware for security and monitoring
    - Signal handling for graceful shutdown
    
    Subclasses should override:
    - register_tools: Register tools with the MCP server
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize the server.
        
        Args:
            settings: Server settings, or None to use default settings
        """
        self.settings = settings or Settings()
        self.start_time = time.time()
        
        # Set up logging
        logging.basicConfig(
            level=getattr(logging, self.settings.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Initialize MCP server
        self.mcp_server = Server(self.settings.server_name)
        
        # Initialize SSE transport
        self.sse = SseServerTransport("/messages")
        
        # Initialize circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.settings.circuit_failure_threshold,
            reset_timeout=self.settings.circuit_reset_timeout
        )
        
        # Register tools
        self.register_tools()
        
        # Set up middleware
        middleware = [
            Middleware(
                CORSMiddleware, 
                allow_origins=self.settings.cors_origins,
                allow_methods=self.settings.cors_methods,
                allow_headers=["*"]
            ),
            Middleware(
                RateLimitMiddleware, 
                calls_per_minute=self.settings.rate_limit
            )
        ]
        
        if self.settings.enable_metrics and PROMETHEUS_AVAILABLE:
            middleware.append(Middleware(MetricsMiddleware))
        
        # Create Starlette application
        self.app = Starlette(
            debug=self.settings.debug,
            routes=[
                Route("/health", endpoint=self.health_check),
                Route("/sse", endpoint=self.handle_sse),
                Route("/messages", endpoint=self.handle_messages, methods=["POST"]),
            ],
            middleware=middleware
        )
        
        # Add metrics endpoint if enabled
        if self.settings.enable_metrics:
            self.app.routes.append(Route("/metrics", endpoint=self.metrics))
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
    
    def register_tools(self):
        """
        Register tools with the MCP server.
        
        This method should be overridden by subclasses to register tools.
        """
        pass
    
    async def health_check(self, request: Request) -> JSONResponse:
        """
        Health check endpoint.
        
        Args:
            request: HTTP request
            
        Returns:
            JSON response with health status
        """
        return JSONResponse({
            "status": "healthy",
            "server": self.settings.server_name,
            "uptime": time.time() - self.start_time,
            "circuit_breaker": self.circuit_breaker.state
        })
    
    async def metrics(self, request: Request) -> JSONResponse:
        """
        Metrics endpoint.
        
        Args:
            request: HTTP request
            
        Returns:
            JSON response with metrics
        """
        if not PROMETHEUS_AVAILABLE:
            return JSONResponse({
                "error": "Prometheus client not installed"
            }, status_code=501)
            
        return JSONResponse({
            "message": "Metrics available at /metrics endpoint with Prometheus"
        })
    
    async def handle_sse(self, request: Request):
        """
        Handle SSE connections.
        
        Args:
            request: HTTP request
            
        Returns:
            SSE response
        """
        session_id = request.query_params.get('session_id', str(uuid.uuid4()))
        logger.info(f"SSE connection request received for session: {session_id}")
        
        try:
            async with self.sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                logger.info(f"SSE connection established for session: {session_id}")
                await self.mcp_server.run(
                    streams[0], 
                    streams[1], 
                    self.mcp_server.create_initialization_options()
                )
        except Exception as e:
            logger.error(f"SSE connection error for session {session_id}: {e}")
            raise
    
    async def handle_messages(self, request: Request) -> JSONResponse:
        """
        Handle incoming messages.
        
        Args:
            request: HTTP request
            
        Returns:
            JSON response
        """
        session_id = request.query_params.get('session_id')
        logger.info(f"Message received with session_id: {session_id}")
        
        try:
            body = await request.body()
            logger.debug(f"Received message body: {body}")
            
            body_sent = False
            
            async def buffered_receive():
                nonlocal body_sent
                if not body_sent:
                    body_sent = True
                    return {
                        "type": "http.request",
                        "body": body,
                        "more_body": False
                    }
                return {
                    "type": "http.request",
                    "body": b"",
                    "more_body": False
                }
            
            responses = []
            async def buffered_send(message):
                logger.debug(f"Transport sending response: {message}")
                responses.append(message)
            
            try:
                await self.sse.handle_post_message(
                    request.scope,
                    buffered_receive,
                    buffered_send
                )
                
                return JSONResponse(
                    {"status": "accepted", "session_id": session_id},
                    status_code=202
                )
                
            except Exception as e:
                logger.error(f"Message processing error: {e}")
                return JSONResponse(
                    {"error": str(e), "session_id": session_id},
                    status_code=500
                )
                
        except Exception as e:
            logger.error(f"Message handling error: {e}")
            return JSONResponse(
                {"error": str(e), "session_id": session_id},
                status_code=500
            )
    
    def _handle_signal(self, sig, frame):
        """
        Handle termination signals.
        
        Args:
            sig: Signal number
            frame: Current stack frame
        """
        logger.info(f"Received signal {sig}, shutting down...")
        sys.exit(0)
    
    def run(self):
        """
        Run the server.
        """
        logger.info(f"Starting {self.settings.server_name} on {self.settings.server_host}:{self.settings.server_port}")
        
        # Start metrics server if enabled and on a different port
        if (self.settings.enable_metrics and 
            PROMETHEUS_AVAILABLE and 
            self.settings.metrics_port is not None):
            start_http_server(self.settings.metrics_port)
            logger.info(f"Metrics server started on port {self.settings.metrics_port}")
        
        # Start the main server
        uvicorn.run(
            self.app, 
            host=self.settings.server_host, 
            port=self.settings.server_port,
            log_level=self.settings.log_level
        )