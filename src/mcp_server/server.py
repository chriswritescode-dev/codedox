"""MCP (Model Context Protocol) server implementation."""

import asyncio
import logging
import json
from typing import Dict, Any, List
from datetime import datetime

from mcp.server import Server
from mcp.types import Tool, TextContent

from ..config import get_settings
from ..database import get_db_manager
from .tools import MCPTools

logger = logging.getLogger(__name__)
settings = get_settings()


class MCPServer:
    """MCP server for exposing code extraction tools to AI assistants."""
    
    def __init__(self) -> None:
        """Initialize the MCP server."""
        self.server = Server("rag-pipeline")
        self.db_manager = get_db_manager()
        self.tools = MCPTools()
        self._register_handlers()
    
    def _register_handlers(self) -> None:
        """Register MCP tool handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
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
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Execute a tool and return results."""
            try:
                result: Any
                if name == "init_crawl":
                    result = await self.tools.init_crawl(
                        name=arguments["name"],
                        start_urls=arguments["start_urls"],
                        max_depth=arguments.get("max_depth", 1),
                        domain_filter=arguments.get("domain_filter"),
                        metadata=arguments.get("metadata", {})
                    )
                    
                elif name == "get_sources":
                    result = await self.tools.get_sources(
                        job_id=arguments.get("job_id")
                    )
                    
                elif name == "search_content":
                    result = await self.tools.search_content(
                        query=arguments["query"],
                        source=arguments.get("source"),
                        language=arguments.get("language"),
                        max_results=arguments.get("max_results", 10)
                    )
                    
                elif name == "get_snippet_details":
                    result = await self.tools.get_snippet_details(
                        snippet_id=arguments["snippet_id"]
                    )
                    
                else:
                    result = {"error": f"Unknown tool: {name}"}
                
                # Format result based on tool
                if name == "search_content" and isinstance(result, str):
                    # Already formatted search results
                    return [TextContent(type="text", text=result)]
                else:
                    # JSON results
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                    
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}")
                error_result = {
                    "error": str(e),
                    "tool": name,
                    "timestamp": datetime.utcnow().isoformat()
                }
                return [TextContent(type="text", text=json.dumps(error_result, indent=2))]
    
    async def start(self) -> None:
        """Start the MCP server with stdio transport."""
        logger.info(f"Starting MCP server on stdio transport")
        
        try:
            # MCP servers use stdio for communication
            # The actual network binding (if needed) should be handled by a wrapper
            import sys
            await self.server.run(
                read_stream=sys.stdin.buffer,
                write_stream=sys.stdout.buffer,
                initialization_options=self.server.create_initialization_options()
            )
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise
    
    def run(self) -> None:
        """Run the MCP server (blocking)."""
        asyncio.run(self.start())


def main() -> None:
    """Main entry point for MCP server."""
    # Test database connection
    db_manager = get_db_manager()
    if not db_manager.test_connection():
        logger.error("Failed to connect to database. Please ensure PostgreSQL is running and the database exists.")
        logger.error("Run 'python cli.py init' to initialize the database.")
        raise RuntimeError("Database connection failed")
    
    # Start server
    server = MCPServer()
    server.run()


if __name__ == "__main__":
    main()