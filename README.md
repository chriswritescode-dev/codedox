# CodeDox - Documentation Code Extraction & Search

A powerful system for crawling documentation websites, extracting code snippets, and providing fast search capabilities via MCP (Model Context Protocol) integration.

## Features

- **Controlled Web Crawling**: Manual crawling with configurable depth (0-3 levels)
- **Smart Code Extraction**: Extracts code blocks while preserving context
- **Language Detection**: Context-aware language detection using LLM
- **Fast Search**: PostgreSQL full-text search with < 100ms response time
- **MCP Integration**: Expose tools to AI assistants via Model Context Protocol
- **Source Management**: Track multiple documentation sources with statistics
- **Clean Content**: Crawl4AI integration removes navigation, ads, and clutter
- **Modern Web UI**: React-based dashboard for managing crawls, searching code, and monitoring system activity
- **Auto Site Content Deduplication**: only updates or adds content that has changed. 

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Web UI       │────▶│   FastAPI       │────▶│   PostgreSQL    │
│ (React + Vite)  │     │   Server        │     │  (Full-Text)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │
┌─────────────────┐           │
│   MCP Client    │────▶│ MCP Tools │
│  (AI Assistant) │     │           │
└─────────────────┘     └───────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Crawl4AI      │
                       │  (Web Crawler)  │
                       └─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 12+ 
- Playwright (installed automatically with crawl4ai)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/codedox.git
cd codedox
```

2. Create virtual environment:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
uv pip install -r requirements.txt

# Install Playwright browsers (required for web crawling)
crawl4ai-setup
```

4. Set up PostgreSQL:
```bash
# Create database
createdb codedox

# Initialize database schema (first time only)
python cli.py init

# To reset and recreate all tables (WARNING: deletes all data)
python cli.py init --drop
```

5. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

### Running the Application

#### Quick Start

```bash
# Create and activate virtual environment (if not already done)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Initialize database (first time only)
python cli.py init

# Start everything (API + Web UI)
python cli.py all
```

This will:
- ✅ Start the API server at http://localhost:8000
- ✅ Start the web UI at http://localhost:5173
- ✅ Enable MCP tools at http://localhost:8000/mcp
- ✅ Enable hot reloading for both services

> **Note**: The web UI provides a user-friendly interface for all operations including crawling, searching, and monitoring. No need to memorize CLI commands!

#### Running Services Separately

```bash
# Start only API server
python cli.py run

# Start only Web UI (in another terminal)
python cli.py ui

# Start only API server (alternative)
python cli.py api
```

## MCP (Model Context Protocol) Integration

CodeDox supports MCP in two modes:

1. **HTTP Mode** (Recommended) - MCP tools exposed via HTTP endpoints on the main API server
2. **Stdio Mode** - Traditional MCP server for direct AI assistant integration

### HTTP Mode (Built into API Server)

When running the API server (`python cli.py api` or `python cli.py all`), MCP tools are automatically available via HTTP endpoints. No separate MCP server is needed.

**MCP Protocol Endpoints (Recommended for AI Assistants):**
- `POST /mcp` - Streamable HTTP transport (MCP 2025-03-26 spec) - **Newest and recommended**
- `POST /mcp/v1/sse` - Server-Sent Events transport (legacy support)

**Legacy REST Endpoints:**
- `GET /mcp/health` - Health check
- `GET /mcp/tools` - List available tools with schemas
- `POST /mcp/execute/{tool_name}` - Execute a specific tool
- `POST /mcp/stream` - Streaming endpoint for simple integrations

**Example Usage:**

For AI Assistants using MCP Protocol (Streamable HTTP - Recommended):
```bash
# Configure your AI assistant to use the newest streamable transport:
# URL: http://localhost:8000/mcp
# Transport: Streamable HTTP
# Headers: Accept: application/json, text/event-stream
```

For AI Assistants using MCP Protocol (SSE - Legacy):
```bash
# Configure your AI assistant to use the SSE transport:
# URL: http://localhost:8000/mcp/v1/sse
# Transport: Server-Sent Events (SSE)
```

For direct API usage:
```bash
# List available tools
curl http://localhost:8000/mcp/tools

# Get code snippets from a library
curl -X POST http://localhost:8000/mcp/execute/get_content \
  -H "Content-Type: application/json" \
  -d '{"library_id": "library-id", "query": "authentication"}'
```

### Stdio Mode (Standalone MCP Server)

For AI assistants that require traditional stdio-based MCP communication:

```bash
# Run standalone MCP server
python cli.py mcp
```

This mode is only needed for specific AI integrations that don't support HTTP endpoints.

### Available MCP Tools

1. **init_crawl** - Start documentation crawling
   - `name`: Library/framework name (optional - auto-detected if not provided)
   - `start_urls`: List of URLs to crawl
   - `max_depth`: Crawl depth (0-3)
   - `domain_filter`: Optional domain restriction
   - `max_concurrent_crawls`: Maximum concurrent page crawls (default: 20)
   - `metadata`: Additional metadata (optional)

2. **search_libraries** - Search for available libraries by name
   - `query`: Search query for library names (e.g., 'react', 'nextjs', 'django')
   - `max_results`: Maximum results to return (1-50, default: 10)

3. **get_content** - Get code snippets from a library
   - `library_id`: Library ID (required) - obtained from search_libraries
   - `query`: Optional search terms to filter results
   - `max_results`: Limit results (1-50, default: 10)

4. **get_snippet_details** - Get detailed information about a specific code snippet
   - `snippet_id`: The ID of the snippet (from get_content results)


## API Endpoints


### Crawling
- `POST /crawl/init` - Start new crawl job
- `GET /crawl/status/{job_id}` - Check crawl status
- `POST /crawl/cancel/{job_id}` - Cancel running job

### Search
- `POST /search` - Search code snippets
- `GET /search/languages` - List available languages
- `GET /search/recent` - Get recent snippets

### Sources
- `GET /sources` - List documentation sources
- `GET /snippets/{id}` - Get specific snippet
- `GET /export/{job_id}` - Export crawl results

### Upload
- `POST /upload/markdown` - Upload markdown content
- `POST /upload/file` - Upload markdown file

## Web UI

CodeDox includes a modern, responsive web interface built with React and TypeScript. Access it at `http://localhost:5173` when running the development server.

### Features

- **Dashboard**: Real-time statistics, system overview, and recent activity monitoring
- **Advanced Search**: Powerful code snippet search with language filters and syntax highlighting
- **Source Management**: Browse and manage documentation sources with detailed statistics
- **Crawl Monitoring**: Track crawl jobs in real-time with progress updates via WebSocket
- **Settings**: Configure application settings through an intuitive interface

### Technologies

- **Frontend Framework**: React 18 with TypeScript
- **Build Tool**: Vite for lightning-fast development
- **Styling**: Tailwind CSS with dark mode support
- **State Management**: React Query for efficient data fetching
- **Real-time Updates**: WebSocket integration for live crawl progress

The web UI provides a user-friendly alternative to the CLI for all major operations, making it easy to manage your documentation pipeline without memorizing commands.


### LLM Configuration for Parallel Requests

For optimal performance with your local LLM server, configure parallel request settings in your `.env` file:

```bash
# LLM Configuration
LLM_ENDPOINT=http://localhost:8080
LLM_MODEL=gpt-4
LLM_API_KEY=your-api-key-here
LLM_MAX_TOKENS=1000
LLM_TEMPERATURE=0.1

# Parallel Request Settings (adjust based on your LLM server capabilities)
LLM_MAX_CONCURRENT_REQUESTS=20    # Max parallel requests to LLM
LLM_REQUEST_TIMEOUT=30.0          # Request timeout in seconds
LLM_RETRY_ATTEMPTS=3              # Number of retry attempts on failure
```

**Finding Optimal Values:**

Use the included configuration test to determine the best settings for your LLM setup:

```bash
# Quick test to find optimal settings (recommended)
python scripts/test_llm_config.py

# Or run comprehensive performance analysis
python tests/performance/test_llm_concurrency_performance.py
python tests/performance/visualize_concurrency_results.py
```

**Configuration Guidelines:**

- **Local LLM (Ollama, etc.)**: Start with `LLM_MAX_CONCURRENT_REQUESTS=5-10`
- **GPU Server**: Can handle `LLM_MAX_CONCURRENT_REQUESTS=15-30` depending on VRAM
- **Cloud APIs (OpenAI, Claude)**: Use `LLM_MAX_CONCURRENT_REQUESTS=20-50` based on rate limits
- **CPU-only**: Keep `LLM_MAX_CONCURRENT_REQUESTS=2-5` to avoid overwhelming the system

Monitor your LLM server's resource usage and adjust accordingly. Higher concurrency improves crawling speed but may increase latency or cause timeouts.

## Language Support

Automatic detection for:
- Python, JavaScript, TypeScript
- Java, Go, Rust, C/C++, C#
- Ruby, PHP, SQL, Bash
- HTML, CSS, YAML, JSON, XML

## Development

### Project Structure
```
codedox/
├── src/
│   ├── api/          # FastAPI endpoints
│   ├── crawler/      # Web crawling logic
│   ├── database/     # Models and search
│   ├── language/     # Language detection
│   ├── mcp_server/   # MCP server implementation
│   └── parser/       # Code extraction
├── tests/            # Test suite
├── config.yaml       # Configuration
└── requirements.txt  # Dependencies
```

### Running Tests
```bash
pytest tests/
```


## Performance

- **Search Speed**: < 100ms for full-text search
- **Storage**: ~50KB per code snippet with context

## Troubleshooting

### Common Issues

**Database connection failed**

   - Check PostgreSQL is running
   - Verify credentials in `.env`


## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push branch (`git push origin feature/amazing`)
5. Open Pull Request

## Author

**Chris Scott** - Initial work and development

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

