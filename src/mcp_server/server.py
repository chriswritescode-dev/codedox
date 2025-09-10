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
        self._register_handlers()

    def _build_tool_definitions(self) -> list[Tool]:
        """Build the core tool definitions."""
        return [
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
                description="Get code snippets from a library with optional search.\n\n"
                "**Purpose: Search and retrieve code snippets from documentation**\n"
                "- Use `library_id` to specify which library to search\n"
                "- Returns multiple snippets (limited to prevent context overflow)\n"
                "- Each snippet is truncated to 500 tokens when returning multiple\n"
                "- For full snippets, use get_snippet() with the snippet ID\n\n"
                "**IMPORTANT: Each result includes a SOURCE URL - use this with get_page_markdown() for full documentation!**\n\n"
                "**Search Modes:**\n"
                "- **'code' (default)**: Direct code search, falls back to markdown if <5 results found\n"
                "- **'enhanced'**: ALWAYS searches markdown docs to find ALL related snippets\n\n"
                "**What this searches:**\n"
                "- Code content, function names, imports\n"
                "- Code titles and descriptions\n"
                "- In 'enhanced' mode: Also searches full markdown to discover related code\n\n"
                "**Library identification:**\n"
                "- Use library name: 'nextjs', 'react', 'django', etc.\n"
                "- Or use UUID from search_libraries\n"
                "- Fuzzy matching helps find the right library\n\n"
                "**Examples:**\n"
                "- `library_id: 'react', query: 'useState'` - finds useState code snippets\n"
                "- `library_id: 'nextjs', query: 'api', search_mode: 'enhanced'` - finds ALL API-related code\n"
                "- `library_id: 'react', page: 2, limit: 10` - get second page of results\n\n"
                "Returns formatted code snippets with automatic size limiting to prevent context overflow.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "library_id": {
                            "type": "string",
                            "description": "Library name (e.g., 'nextjs', 'react', '.NET') or UUID. Names are matched intelligently with fuzzy search.",
                        },
                        "query": {
                            "type": "string",
                            "description": "Optional search query to filter content within the library (e.g., 'authentication', 'routing', 'hooks').",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100,
                            "description": "Maximum results per page (default: 20).",
                        },
                        "page": {
                            "type": "integer",
                            "default": 1,
                            "minimum": 1,
                            "description": "Page number for paginated results (1-indexed).",
                        },
                        "search_mode": {
                            "type": "string",
                            "enum": ["code", "enhanced"],
                            "default": "code",
                            "description": "Search strategy: 'code' (default) searches code directly with markdown fallback for <5 results. 'enhanced' always searches markdown docs to find ALL related snippets.",
                        },
                    },
                    "required": ["library_id"],
                },
            ),
            Tool(
                name="get_snippet",
                description="Retrieve a specific code snippet by its ID with customizable token limits.\n\n"
                "**Purpose: Direct access to individual snippets with size control**\n"
                "- Use snippet_id to get a specific snippet directly\n"
                "- Control output size with max_tokens parameter\n"
                "- Supports chunked reading for large snippets\n\n"
                "**Features:**\n"
                "- Get full or partial snippet content by ID\n"
                "- Customize token limit (100-10000 tokens)\n"
                "- Navigate large snippets with chunk_index\n"
                "- Automatic truncation with continuation info\n\n"
                "**Examples:**\n"
                "- `snippet_id: '24758'` - gets snippet with default 2000 token limit\n"
                "- `snippet_id: '24758', max_tokens: 500` - gets first 500 tokens\n"
                "- `snippet_id: '24758', max_tokens: 5000` - gets up to 5000 tokens\n"
                "- `snippet_id: '24758', chunk_index: 0, max_tokens: 1000` - first 1000-token chunk\n\n"
                "Returns formatted code snippet with SOURCE URL for documentation.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "snippet_id": {
                            "type": "string",
                            "description": "The ID of the specific code snippet to retrieve",
                        },
                        "max_tokens": {
                            "type": "integer",
                            "minimum": 100,
                            "maximum": 10000,
                            "default": 2000,
                            "description": "Maximum tokens to return (100-10000, default: 2000). Useful for controlling context size.",
                        },
                        "chunk_index": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "For large snippets, get a specific chunk (0-based). Each chunk size is determined by max_tokens.",
                        },
                    },
                    "required": ["snippet_id"],
                },
            ),
            Tool(
                name="get_page_markdown",
                description="Get full documentation from a page URL or snippet ID.\n\n"
                "**PRIMARY USE: Get complete documentation context after finding code with get_content()**\n\n"
                "**Two ways to access:**\n"
                "1. **By URL**: Use SOURCE URL from get_content results\n"
                "2. **By snippet_id**: Use snippet ID to automatically get the associated document\n\n"
                "**Features:**\n"
                "- Get full documentation page from SOURCE URL or snippet ID\n"
                "- Search WITHIN a specific page using 'query' parameter\n"
                "- Limit content size with max_tokens for summaries\n"
                "- Chunk large documents for manageable reading\n\n"
                "**Common workflows:**\n"
                "1. After get_content: Use SOURCE URL here for full docs\n"
                "2. Direct snippet access: Use snippet_id to get the document containing that snippet\n"
                "3. Search in page: Add query='search term' to find specific content\n"
                "4. Get summary: Use max_tokens=500 for brief overview\n"
                "5. Navigate large docs: Use chunk_index=0,1,2... for pagination\n\n"
                "**Examples:**\n"
                "- `url: 'https://react.dev/reference/useState'` - get full page by URL\n"
                "- `snippet_id: '12345'` - get document containing snippet 12345\n"
                "- `url: '...', query: 'dependencies'` - search for 'dependencies' in that page\n"
                "- `snippet_id: '12345', max_tokens: 1000` - get first 1000 tokens from snippet's document\n"
                "- `url: '...', chunk_index: 0` - get first chunk of large document\n\n"
                "**Note:** Provide either 'url' OR 'snippet_id', not both. The query parameter searches WITHIN this single document only, not across all docs.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL of the documentation page (typically from SOURCE field in get_content results)",
                        },
                        "snippet_id": {
                            "type": "string",
                            "description": "The ID of a code snippet to get its associated document",
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
                    "required": [],
                },
            ),
        ]

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions in a format suitable for HTTP API."""
        return [
            {"name": tool.name, "description": tool.description, "input_schema": tool.inputSchema}
            for tool in self._build_tool_definitions()
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
                search_mode=arguments.get("search_mode", "code"),
            )
        elif name == "get_snippet":
            return await self.tools.get_snippet(
                snippet_id=arguments.get("snippet_id"),
                max_tokens=arguments.get("max_tokens"),
                chunk_index=arguments.get("chunk_index"),
            )
        elif name == "get_page_markdown":
            return await self.tools.get_page_markdown(
                url=arguments.get("url"),
                snippet_id=arguments.get("snippet_id"),
                query=arguments.get("query"),
                max_tokens=arguments.get("max_tokens"),
                chunk_index=arguments.get("chunk_index"),
            )
        else:
            available_tools = [tool.name for tool in self._build_tool_definitions()]
            logger.error(f"Unknown tool requested: '{name}'. Available tools: {available_tools}")
            raise ValueError(
                f"Unknown tool: '{name}'. Available tools: {', '.join(available_tools)}"
            )

    def _register_handlers(self) -> None:
        """Register MCP tool handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available MCP tools."""
            return self._build_tool_definitions()

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
