"""MCP Server implementation mounted to FastAPI."""

import logging

from mcp.server import Server

from ..mcp_server.server import MCPServer

logger = logging.getLogger(__name__)


def create_mcp_server() -> Server:
    """Create and configure MCP server instance."""

    # Use the central MCP server instance
    mcp_server_instance = MCPServer()

    # Return the underlying server object
    return mcp_server_instance.server
