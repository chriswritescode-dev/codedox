# Quick Start

## Start the Application

```bash
# Activate virtual environment
source .venv/bin/activate

# Start API and Web UI
python cli.py serve
```

Visit http://localhost:5173 for the web interface.

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

MCP tools are available when the API server is running:

```bash
curl http://localhost:8000/mcp/tools
```