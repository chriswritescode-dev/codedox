"""MCP (Model Context Protocol) server implementation."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from ..config import get_settings
from ..database import get_db_manager
from .tools import MCPTools

logger = logging.getLogger(__name__)
settings = get_settings()


class MCPServer:
    """MCP server for exposing code extraction tools to AI assistants."""

    def __init__(self) -> None:
        """Initialize the MCP server."""
        self.server: Server = Server("codedox")
        self.db_manager = get_db_manager()
        self.tools = MCPTools()
        self._tool_definitions: list[Tool] = []
        self._register_handlers()

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions in a format suitable for HTTP API."""
        return [
            {"name": tool.name, "description": tool.description, "input_schema": tool.inputSchema}
            for tool in self._tool_definitions
        ]

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool by name with given arguments."""
        logger.debug(f"MCPServer.execute_tool called with name='{name}', arguments={arguments}")

        if name == "init_crawl":
            return await self.tools.init_crawl(
                name=arguments.get("name"),
                start_urls=arguments.get("start_urls"),
                max_depth=arguments.get("max_depth", 1),
                domain_filter=arguments.get("domain_filter"),
                metadata=arguments.get("metadata", {}),
                max_concurrent_crawls=arguments.get("max_concurrent_crawls"),
            )
        elif name == "search_libraries":
            return await self.tools.search_libraries(
                query=arguments.get("query", ""),
                limit=arguments.get("limit", 20),
                page=arguments.get("page", 1),
            )
        elif name == "get_content":
            return await self.tools.get_content(
                library_id=arguments.get("library_id"),
                query=arguments.get("query"),
                limit=arguments.get("limit", 20),
                page=arguments.get("page", 1),
            )
        elif name == "get_page_markdown":
            return await self.tools.get_page_markdown(
                url=arguments.get("url"),
                query=arguments.get("query"),  # Add the missing query parameter!
                max_tokens=arguments.get("max_tokens"),
                chunk_index=arguments.get("chunk_index"),
            )
        else:
            available_tools = [
                "init_crawl",
                "search_libraries",
                "get_content",
                "get_page_markdown",
            ]
            logger.error(f"Unknown tool requested: '{name}'. Available tools: {available_tools}")
            raise ValueError(
                f"Unknown tool: '{name}'. Available tools: {', '.join(available_tools)}"
            )

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
                        "max_concurrent_crawls": {
                            "type": "integer",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100,
                            "description": "Maximum concurrent page crawls",
                        },
                    },
                    "required": ["name", "start_urls"],
                },
            ),
            Tool(
                name="search_libraries",
                description="Search for available libraries or list all libraries in the system.\n\n"
                "**Usage:**\n"
                "- With query: Returns libraries matching the search term\n"
                "- Without query: Returns all available libraries\n\n"
                "**When searching with a query:**\n"
                "1. Analyzes the query to find matching libraries\n"
                "2. Returns matches based on:\n"
                "   - Name similarity (exact matches prioritized)\n"
                "   - Description relevance\n"
                "   - Documentation coverage (higher snippet counts preferred)\n\n"
                "**Response includes:**\n"
                "- Library ID (use this with get_content)\n"
                "- Library name\n"
                "- Description\n"
                "- Snippet count\n"
                "- Match confidence (when searching)\n\n"
                "**Pagination:**\n"
                "- Use `page` parameter to navigate through results\n"
                "- Use `limit` parameter to control page size (default: 20)\n\n"
                "**Examples:**\n"
                "- `query: 'react'` - finds React-related libraries\n"
                "- `query: ''` or no query - lists all libraries\n"
                "- `query: 'next'` - finds Next.js and similar libraries\n"
                "- `page: 2, limit: 30` - get page 2 with 30 results per page",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Optional search query for library names. If omitted or empty, returns all libraries.",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100,
                            "description": "Maximum results per page (default: 20)",
                        },
                        "page": {
                            "type": "integer",
                            "default": 1,
                            "minimum": 1,
                            "description": "Page number for paginated results (1-indexed). Use with limit to control pagination.",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="get_content",
                description="Get code snippets from a library (searches CODE only, not documentation text).\n\n"
                "**IMPORTANT: Each result includes a SOURCE URL - use this with get_page_markdown() for full documentation!**\n\n"
                "**Search Modes:**\n"
                "- **'code' (default)**: Direct code search, falls back to markdown if <5 results found\n"
                "- **'enhanced'**: ALWAYS searches markdown docs to find ALL related snippets, even those without exact keyword matches\n"
                "  Use 'enhanced' when you want comprehensive results beyond keyword matching!\n\n"
                "**What this searches:**\n"
                "- Code content, function names, imports\n"
                "- Code titles and descriptions\n"
                "- In 'enhanced' mode: Also searches full markdown to discover related code\n"
                "**Workflow for complete information:**\n"
                "1. Use get_content() to find code snippets\n"
                "2. Each result has SOURCE: url\n"
                "3. Use get_page_markdown(url=SOURCE) for full documentation context\n\n"
                "**Library identification:**\n"
                "- Use library name: 'nextjs', 'react', 'django', etc.\n"
                "- Or use UUID from search_libraries\n"
                "- Fuzzy matching helps find the right library\n\n"
                "**Examples:**\n"
                "- `library_id: 'react', query: 'useState'` - finds useState code snippets\n"
                "- `library_id: 'nextjs', query: 'api', search_mode: 'enhanced'` - finds ALL API-related code\n"
                "- `library_id: 'react', page: 2, limit: 10` - get second page of results\n"
                "- Then use SOURCE URLs with get_page_markdown() for complete docs if needed\n\n"
                "Returns formatted code snippets with SOURCE URLs for documentation access.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "library_id": {
                            "type": "string",
                            "description": "Library name (e.g., 'nextjs', 'react', '.NET') or UUID. Names are matched intelligently with fuzzy search.",
                        },
                        "query": {
                            "type": "string",
                            "description": "Optional search query to filter content within the library (e.g., 'authentication', 'routing', 'hooks')",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100,
                            "description": "Maximum results per page (default: 20)",
                        },
                        "page": {
                            "type": "integer",
                            "default": 1,
                            "minimum": 1,
                            "description": "Page number for paginated results (1-indexed). Use with limit to control pagination.",
                        },
                        "search_mode": {
                            "type": "string",
                            "enum": ["code", "enhanced"],
                            "default": "code",
                            "description": "Search strategy: 'code' (default) searches code directly with markdown fallback for <5 results. 'enhanced' always searches markdown docs to find ALL related snippets, even those without matching keywords.",
                        },
                    },
                    "required": ["library_id"],
                },
            ),
            Tool(
                name="get_page_markdown",
                description="Get full documentation from a page URL (typically from get_content SOURCE field).\n\n"
                "**PRIMARY USE: Get complete documentation context after finding code with get_content()**\n\n"
                "**Features:**\n"
                "- Get full documentation page from SOURCE URL\n"
                "- Search WITHIN a specific page using 'query' parameter\n"
                "- Limit content size with max_tokens for summaries\n"
                "- Chunk large documents for manageable reading\n\n"
                "**Common workflows:**\n"
                "1. After get_content: Use SOURCE URL here for full docs\n"
                "2. Search in page: Add query='search term' to find specific content\n"
                "3. Get summary: Use max_tokens=500 for brief overview\n"
                "4. Navigate large docs: Use chunk_index=0,1,2... for pagination\n\n"
                "**Examples:**\n"
                "- `url: 'https://react.dev/reference/useState'` - get full page\n"
                "- `url: '...', query: 'dependencies'` - search for 'dependencies' in that page\n"
                "- `url: '...', max_tokens: 1000` - get first 1000 tokens only\n"
                "- `url: '...', chunk_index: 0` - get first chunk of large document\n\n"
                "**Note:** The query parameter searches WITHIN this single document only, not across all docs.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL of the documentation page (typically from SOURCE field in get_content results)",
                        },
                        "query": {
                            "type": "string",
                            "description": "Optional: Search for this text WITHIN the document (highlights matches, returns relevant excerpts)",
                        },
                        "max_tokens": {
                            "type": "integer",
                            "description": "Optional: Limit response to first N tokens (useful for summaries) or define chunk size when using chunk_index (default: 2048)",
                            "minimum": 100,
                        },
                        "chunk_index": {
                            "type": "integer",
                            "description": "Optional: Get specific chunk of large document (0-based, use for pagination)",
                            "minimum": 0,
                        },

                    },
                    "required": ["url"],
                },
            ),
        ]

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available MCP tools."""
            return self._tool_definitions

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
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
                    "timestamp": datetime.utcnow().isoformat(),
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
                initialization_options=self.server.create_initialization_options(),
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
        logger.error(
            "Failed to connect to database. Please ensure PostgreSQL is running and the database exists."
        )
        logger.error("Run 'python cli.py init' to initialize the database.")
        raise RuntimeError("Database connection failed")

    # Start server
    server = MCPServer()
    server.run()


if __name__ == "__main__":
    main()
