# MCP Integration

CodeDox provides Model Context Protocol (MCP) tools for AI assistants to search and retrieve code snippets from documentation.

## Integration Methods

### HTTP Mode (Recommended)
The easiest way to use CodeDox with AI assistants is via HTTP when the API server is running:

```bash
# Start the API server
python cli.py serve

# MCP endpoint is now available at:
http://localhost:8000/mcp
```

### Claude Code Configuration
Add CodeDox to your Claude Code MCP settings (`.claude_code/config.json` or through the UI):

```json
{
  "mcpServers": {
    "codedox": {
      "url": "http://localhost:8000/mcp",
      "transport": "sse"
    }
  }
}
```

Or using the Claude CLI:
```bash
claude mcp add-json codedox '{"type":"sse","url":"http://localhost:8000/mcp"}'
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
Retrieve code snippets from a specific library:

```json
{
  "name": "get_content",
  "arguments": {
    "library_id": "nextjs",
    "query": "authentication middleware",
    "limit": 20,
    "page": 1
  }
}
```

**Parameters:**
- `library_id`: Library name or UUID (supports fuzzy matching)
- `query`: Search within library content (optional)
- `limit`: Results per page (default: 20, max: 100)
- `page`: Page number for pagination (default: 1)

**Returns:** Formatted code snippets with titles, descriptions, language, and source URLs.

### 4. get_page_markdown
Get the full markdown content of a documentation page:

```json
{
  "name": "get_page_markdown",
  "arguments": {
    "url": "https://nextjs.org/docs/app/building-your-application/routing",
    "max_tokens": 4000,
    "chunk_index": 0,
    "chunk_size": 4000
  }
}
```

**Parameters:**
- `url`: Documentation page URL (typically from snippet results)
- `max_tokens`: Maximum tokens to return (optional)
- `chunk_index`: For paginated content (optional)
- `chunk_size`: Size of each chunk (default: 4000)

**Returns:** Full markdown content of the documentation page for complete context.

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

### Finding and Using Documentation
1. Search for available libraries:
   ```
   Use search_libraries with query "react"
   ```

2. Get code snippets from a library:
   ```
   Use get_content with library_id from search results
   ```

3. Get full page context:
   ```
   Use get_page_markdown with URL from snippet results
   ```

### Starting a New Crawl
```
Use init_crawl to index new documentation:
- Provide documentation URL
- Set appropriate depth (1-2 for most docs)
- Add domain filter to stay within docs site
```