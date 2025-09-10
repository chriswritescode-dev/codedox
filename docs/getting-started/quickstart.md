# Quick Start

## Start the Application

```bash
# Activate virtual environment
source .venv/bin/activate

# Start API, Web UI, and MCP HTTP endpoints
python cli.py serve
```

**Available Services:**
- Web UI: http://localhost:5173 
- API: http://localhost:8000
- MCP Tools: http://localhost:8000/mcp

**Alternative Server Modes:**
```bash
# API + MCP only (no Web UI)
python cli.py serve --api

# MCP stdio mode only (for legacy integrations)
python cli.py serve --mcp
```

## Your First Crawl

### Via Web UI

1. Navigate to the "Crawl" page
2. Click "New Crawl"
3. Enter documentation name and URL
4. Click "Start Crawl"

### Via CLI

```bash
python cli.py crawl start "React" https://react.dev/reference --depth 2
```

## Upload Documentation

### Upload Local Files

```bash
# Upload single file
python cli.py upload /path/to/docs.md --name "My Docs"

# Upload directory
python cli.py upload ./docs-folder --name "Documentation"
```

### Process GitHub Repository

```bash
# Clone and process entire repository
python cli.py upload-repo https://github.com/user/repo --name "Project Docs"

# Process specific folder
python cli.py upload-repo https://github.com/user/repo --path docs

# Private repository with token
export GITHUB_TOKEN=ghp_your_token
python cli.py upload-repo https://github.com/user/private-repo
```

## Search for Code

### Via Web UI

Use the search bar on the dashboard or search page.

### Via CLI

```bash
python cli.py search "authentication middleware"
```

### Via MCP

MCP tools are automatically available when the API server is running:

```bash
# List available MCP tools
curl http://localhost:8000/mcp/tools

# Execute a tool directly
curl -X POST http://localhost:8000/mcp/execute/get_content \
  -H "Content-Type: application/json" \
  -d '{"library_id": "library-name", "query": "search term"}'
```

**For AI Assistants**: Connect directly to `http://localhost:8000/mcp` using Streamable HTTP transport (MCP 2025-03-26 spec).