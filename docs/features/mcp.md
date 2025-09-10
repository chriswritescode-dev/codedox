# MCP Integration

CodeDox provides Model Context Protocol (MCP) tools for AI assistants to search and retrieve code snippets from documentation.

## Integration Methods

### HTTP Mode (Recommended)
The easiest way to use CodeDox with AI assistants is via HTTP when the API server is running:

```bash
# Start the API server (includes Web UI + MCP HTTP endpoints)
python cli.py serve

# MCP tools are now available at:
http://localhost:8000/mcp
```

**Supported MCP Transports:**
- **Streamable HTTP** (MCP 2025-03-26 spec) - Recommended for modern AI assistants
- **Server-Sent Events (SSE)** (MCP 2024-11-05) - Legacy support

### Claude Code Configuration
Add CodeDox to your Claude Code MCP settings (`.claude_code/config.json` or through the UI):

```json
{
  "mcpServers": {
    "codedox": {
      "url": "http://localhost:8000/mcp",
      "transport": "streamable"
    }
  }
}
```

Alternative for legacy SSE transport:
```json
{
  "mcpServers": {
    "codedox": {
      "url": "http://localhost:8000/mcp/v1/sse",
      "transport": "sse"
    }
  }
}
```

## Available MCP Tools

### 1. init_crawl
Start a new documentation crawl to index code snippets:

```json
{
  "name": "init_crawl",
  "arguments": {
    "name": "Next.js",
    "start_urls": ["https://nextjs.org/docs"],
    "max_depth": 2,
    "version": "v14",
    "domain_filter": "nextjs.org",
    "url_patterns": ["*docs*", "*guide*"],
    "max_concurrent_crawls": 20,
    "metadata": {
      "repository": "vercel/next.js",
      "description": "React framework documentation"
    }
  }
}
```

**Parameters:**
- `name`: Library/framework name (auto-detected if not provided)
- `start_urls`: List of URLs to start crawling from
- `max_depth`: Crawl depth (0-3, default: 1)
- `version`: Optional version identifier (e.g., "v14", "2.0")
- `domain_filter`: Restrict crawling to specific domain
- `url_patterns`: Include only URLs matching these patterns
- `max_concurrent_crawls`: Max concurrent sessions (default: 20)
- `metadata`: Additional metadata for the crawl

### 2. search_libraries
Find available libraries in the database:

```json
{
  "name": "search_libraries",
  "arguments": {
    "query": "react",
    "limit": 20,
    "page": 1
  }
}
```

**Parameters:**
- `query`: Search term for library names (optional, returns all if empty)
- `limit`: Results per page (default: 20, max: 100)
- `page`: Page number for pagination (default: 1)

**Returns:** List of matching libraries with IDs, names, descriptions, and snippet counts.

### 3. get_content
Retrieve code snippets from a specific library with enhanced search modes:

```json
{
  "name": "get_content",
  "arguments": {
    "library_id": "nextjs",
    "query": "authentication middleware",
    "limit": 20,
    "page": 1,
    "search_mode": "enhanced"
  }
}
```

**Parameters:**
- `library_id`: Library name or UUID (supports fuzzy matching)
- `query`: Search within library content (optional)
- `limit`: Results per page (default: 20, max: 100)
- `page`: Page number for pagination (default: 1)
- `search_mode`: Search strategy:
  - `"code"` (default): Direct code search with markdown fallback for <5 results
  - `"enhanced"`: Always searches markdown docs to find ALL related snippets

**Returns:** Formatted code snippets with titles, descriptions, language, and **SOURCE URLs** for full documentation access.

### 4. get_page_markdown ✨
Get the full markdown content of a documentation page for complete context:

```json
{
  "name": "get_page_markdown",
  "arguments": {
    "url": "https://nextjs.org/docs/app/building-your-application/routing",
    "query": "middleware",
    "max_tokens": 4000,
    "chunk_index": 0
  }
}
```

**Alternative: Access by snippet ID**
```json
{
  "name": "get_page_markdown",
  "arguments": {
    "snippet_id": "12345",
    "max_tokens": 2000
  }
}
```

**Parameters:**
- `url`: Documentation page URL (typically from SOURCE field in get_content results) 
- `snippet_id`: Alternative - get document containing this specific snippet
- `query`: Optional search within this specific document only (highlights matches)
- `max_tokens`: Limit response tokens (default: 2048, useful for summaries)
- `chunk_index`: Navigate large documents (0-based pagination)

**Key Features:**
- **Complete Context**: Get full documentation page, not just code snippets
- **In-Page Search**: Use `query` parameter to search within specific documents
- **Smart Chunking**: Large documents automatically chunked with overlap
- **Token Management**: Control response size for optimal context usage

**Returns:** Full markdown content with metadata, search highlights, and pagination info.

### 5. get_snippet
Get a specific code snippet by its ID with flexible token management:

```json
{
  "name": "get_snippet",
  "arguments": {
    "snippet_id": "12345",
    "max_tokens": 2000,
    "chunk_index": 0
  }
}
```

**Parameters:**
- `snippet_id`: The specific snippet ID to retrieve
- `max_tokens`: Token limit (100-10000, default: 2000)
- `chunk_index`: Navigate large snippets (0-based)

**Features:**
- **Direct Access**: Get specific snippets when you know the exact ID
- **Flexible Sizing**: Control output size from 100 to 10,000 tokens
- **Smart Chunking**: Large snippets automatically chunked with navigation
- **Full Metadata**: Includes title, description, language, and source URL

**Returns:** Complete snippet with metadata and smart token management.

## 🚀 What's New in MCP Integration

### HTTP-First Architecture
- **No Setup Required**: MCP tools instantly available when API server runs
- **Modern Transport**: Streamable HTTP (MCP 2025-03-26 spec) as primary method
- **Unified Server**: Single `python cli.py serve` command starts everything

### Enhanced Search & Documentation Access
- **Enhanced Search Mode**: `search_mode: "enhanced"` finds ALL related snippets via markdown search
- **Full Documentation Access**: New `get_page_markdown` tool provides complete context from any SOURCE URL
- **Smart Token Management**: Configurable limits, chunking, and pagination for optimal AI context usage

### Complete AI Assistant Workflow
1. **Find** libraries with fuzzy matching
2. **Search** code with enhanced modes  
3. **Access** full documentation for complete context

## Direct API Access
You can also interact with MCP tools directly via REST API:

```bash
# List available tools
curl http://localhost:8000/mcp/tools

# Execute a tool
curl -X POST http://localhost:8000/mcp/execute/get_content \
  -H "Content-Type: application/json" \
  -d '{
    "library_id": "nextjs",
    "query": "routing", 
    "search_mode": "enhanced",
    "limit": 10
  }'
```

## Stdio Mode (Alternative)
For AI assistants that require stdio communication:

```bash
python cli.py serve --mcp
```

Configure in Claude Desktop:
```json
{
  "mcpServers": {
    "codedox": {
      "command": "python",
      "args": ["/path/to/codedox/cli.py", "serve", "--mcp"]
    }
  }
}
```

## Authentication (Optional)
For remote deployments, secure the MCP endpoint:

```bash
# Set in .env
MCP_AUTH_TOKEN=your-secret-token

# Use in requests
curl -H "Authorization: Bearer your-secret-token" \
  http://localhost:8000/mcp/tools
```

## Usage Examples

### Complete Workflow for AI Assistants
1. **Find Libraries**: Use `search_libraries` with query like "react"

2. **Get Code Snippets**: Use `get_content` with library_id from search results
   - Each result includes **SOURCE URLs** for full documentation access
   - Use `search_mode: "enhanced"` for comprehensive results beyond keyword matching

3. **Get Full Documentation**: Use `get_page_markdown` with SOURCE URLs for complete context
   - Or use `snippet_id` directly to get the document containing a specific snippet
   - Use `query` parameter to search within the specific document
   - Use `max_tokens` for summaries or `chunk_index` for large documents

**Example Workflow:**
```
1. search_libraries(query="nextjs") → Returns library info
2. get_content(library_id="nextjs", query="middleware", search_mode="enhanced") → Returns code snippets with SOURCE URLs
3. get_page_markdown(url="SOURCE_URL_from_step_2", query="authentication") → Returns full documentation with highlights
```

### Starting a New Crawl
```
Use init_crawl to index new documentation:
- Provide documentation URL
- Set appropriate depth (1-2 for most docs)
- Add domain filter to stay within docs site
```