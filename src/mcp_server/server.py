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
        self._tool_definitions = []
        self._register_handlers()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions in a format suitable for HTTP API."""
        return [
            {"name": tool.name, "description": tool.description, "input_schema": tool.inputSchema}
            for tool in self._tool_definitions
        ]

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool by name with given arguments."""
        logger.debug(f"MCPServer.execute_tool called with name='{name}', arguments={arguments}")

        if name == "init_crawl":
            return await self.tools.init_crawl(
                name=arguments.get("name"),
                start_urls=arguments.get("start_urls"),
                max_depth=arguments.get("max_depth", 1),
                domain_filter=arguments.get("domain_filter"),
                metadata=arguments.get("metadata", {}),
            )
        elif name == "search_libraries":
            return await self.tools.search_libraries(
                query=arguments.get("query"), max_results=arguments.get("max_results", 10)
            )
        elif name == "get_content":
            return await self.tools.get_content(
                library_id=arguments.get("library_id"),
                query=arguments.get("query"),
                language=arguments.get("language"),
                max_results=arguments.get("max_results", 10),
            )
        elif name == "get_snippet_details":
            return await self.tools.get_snippet_details(snippet_id=arguments.get("snippet_id"))
        else:
            available_tools = [
                "init_crawl",
                "search_libraries",
                "get_content",
                "get_snippet_details",
            ]
            logger.error(f"Unknown tool requested: '{name}'. Available tools: {available_tools}")
            raise ValueError(f"Unknown tool: '{name}'. Available tools: {', '.join(available_tools)}")

    def _register_handlers(self) -> None:
        """Register MCP tool handlers."""

        # Define tools
        self._tool_definitions = [
            Tool(
                name="init_crawl",
                description="Initialize a new web crawl job for documentation",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Library/framework name (e.g., 'Next.js', '.NET')",
                        },
                        "start_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "URLs to start crawling from",
                        },
                        "max_depth": {
                            "type": "integer",
                            "default": 1,
                            "minimum": 0,
                            "maximum": 3,
                            "description": "Maximum crawl depth (0-3)",
                        },
                        "domain_filter": {
                            "type": "string",
                            "description": "Optional domain restriction pattern",
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Additional metadata (repository, description, etc.)",
                        },
                    },
                    "required": ["name", "start_urls"],
                },
            ),
            Tool(
                name="search_libraries",
                description="You MUST call this function before 'search_content' to obtain a valid library ID UNLESS the user explicitly provides a library ID in their query.\n\nSelection Process:\n1. Analyze the query to understand what library/package the user is looking for\n2. Return the most relevant match based on:\n   - Name similarity to the query (exact matches prioritized)\n   - Description relevance to the query's intent\n   - Documentation coverage (prioritize libraries with higher Code Snippet counts)\n\nResponse Format:\n- Return the selected library ID in a clearly marked section\n- Provide a brief explanation for why this library was chosen\n- If multiple good matches exist, acknowledge this but proceed with the most relevant one\n- If no good matches exist, clearly state this and suggest query refinements\n\nFor ambiguous queries, request clarification before proceeding with a best-guess match.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for library names (e.g., 'react', 'nextjs', 'django')",
                        },
                        "max_results": {
                            "type": "integer",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 50,
                            "description": "Maximum results to return",
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="get_content",
                description="Get the latest code snippets and documentation from a specific library. Requires a library_id (obtained from search_libraries). Can optionally filter results with a search query. Returns code examples from the specified library's documentation.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "library_id": {
                            "type": "string",
                            "description": "Library ID (required) - obtained from search_libraries tool",
                        },
                        "query": {
                            "type": "string",
                            "description": "Optional search query to filter content within the library",
                        },
                        "language": {
                            "type": "string",
                            "description": "Optional programming language filter",
                        },
                        "max_results": {
                            "type": "integer",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 50,
                            "description": "Maximum results to return",
                        },
                    },
                    "required": ["library_id"],
                },
            ),
            Tool(
                name="get_snippet_details",
                description="Get detailed information about a specific code snippet by ID, not necessary unless the get_content tool did not return enough information to answer the user's question or request.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "snippet_id": {
                            "type": "integer",
                            "description": "The ID of the snippet (from search_content tool - search results)",
                        }
                    },
                    "required": ["snippet_id"],
                },
            ),
        ]

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available MCP tools."""
            return self._tool_definitions

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Execute a tool and return results."""
            try:
                result = await self.execute_tool(name, arguments)

                # Format result based on tool
                if name == "get_content" and isinstance(result, str):
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
        logger.info("Starting MCP server on stdio transport")

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
