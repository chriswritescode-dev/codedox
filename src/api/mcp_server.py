"""MCP Server implementation mounted to FastAPI."""

import logging
from typing import Any
from mcp.server.models import InitializationOptions
from mcp.shared.exceptions import McpError
from mcp.server import Server
from mcp.types import Tool, TextContent

from ..mcp_server.tools import MCPTools

logger = logging.getLogger(__name__)


def create_mcp_server() -> Server:
    """Create and configure MCP server instance."""
    
    # Create MCP server
    server = Server("codedox-mcp")
    
    # Initialize tools
    mcp_tools = MCPTools()
    
    # Register handlers
    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        """List available MCP tools."""
        return [
            Tool(
                name="init_crawl",
                description="Initialize a new web crawl job for documentation",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Library/framework name (e.g., 'Next.js', '.NET')"
                        },
                        "start_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "URLs to start crawling from"
                        },
                        "max_depth": {
                            "type": "integer",
                            "default": 1,
                            "minimum": 0,
                            "maximum": 3,
                            "description": "Maximum crawl depth (0-3)"
                        },
                        "domain_filter": {
                            "type": "string",
                            "description": "Optional domain restriction pattern"
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Additional metadata (repository, description, etc.)"
                        }
                    },
                    "required": ["name", "start_urls"]
                }
            ),
            Tool(
                name="get_sources",
                description="Get list of available libraries/sources with stats",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "Optional specific job ID to filter by"
                        }
                    }
                }
            ),
            Tool(
                name="search_content",
                description="Search code snippets across all sources or in a specific library",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for content"
                        },
                        "source": {
                            "type": "string",
                            "description": "Optional library name filter (e.g., 'Next.js', '.NET')"
                        },
                        "language": {
                            "type": "string",
                            "description": "Optional programming language filter"
                        },
                        "max_results": {
                            "type": "integer",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 50,
                            "description": "Maximum results to return"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="get_snippet_details",
                description="Get detailed information about a specific code snippet by ID",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "snippet_id": {
                            "type": "integer",
                            "description": "The ID of the snippet (from search results)"
                        }
                    },
                    "required": ["snippet_id"]
                }
            )
        ]
    
    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Execute a tool and return results."""
        try:
            if name == "init_crawl":
                result = await mcp_tools.init_crawl(
                    name=arguments["name"],
                    start_urls=arguments["start_urls"],
                    max_depth=arguments.get("max_depth", 1),
                    domain_filter=arguments.get("domain_filter"),
                    metadata=arguments.get("metadata", {})
                )
                
            elif name == "get_sources":
                result = await mcp_tools.get_sources(
                    job_id=arguments.get("job_id")
                )
                
            elif name == "search_content":
                result = await mcp_tools.search_content(
                    query=arguments["query"],
                    source=arguments.get("source"),
                    language=arguments.get("language"),
                    max_results=arguments.get("max_results", 10)
                )
                
            elif name == "get_snippet_details":
                result = await mcp_tools.get_snippet_details(
                    snippet_id=arguments["snippet_id"]
                )
                
            else:
                raise McpError(f"Unknown tool: {name}")
            
            # Format result as text
            if isinstance(result, str):
                return [TextContent(type="text", text=result)]
            else:
                import json
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            raise McpError(f"Tool execution failed: {str(e)}")
    
    return server