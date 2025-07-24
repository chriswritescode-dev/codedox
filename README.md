# CodeDox - Documentation Code Extraction & Search

A powerful system for crawling documentation websites, extracting code snippets, and providing fast search capabilities via MCP (Model Context Protocol) integration.

## Features

- **Controlled Web Crawling**: Manual crawling with configurable depth (0-3 levels)
- **Smart Code Extraction**: LLM-powered extraction during crawling for intelligent code understanding
- **Language Detection**: Context-aware language detection using LLM
- **Fast Search**: PostgreSQL full-text search with < 100ms response time
- **MCP Integration**: Expose tools to AI assistants via Model Context Protocol
- **Source Management**: Track multiple documentation sources with statistics
- **Clean Content**: Crawl4AI integration removes navigation, ads, and clutter
- **Modern Web UI**: React-based dashboard for managing crawls, searching code, and monitoring system activity
- **Auto Site Content Deduplication**: Only updates or adds content that has changed


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
git clone https://github.com/chriswritescode-dev/codedox.git
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

# Get code snippets from a library (using library name)
curl -X POST http://localhost:8000/mcp/execute/get_content \
  -H "Content-Type: application/json" \
  -d '{"library_id": "nextjs", "query": "authentication"}'

# Or using a UUID
curl -X POST http://localhost:8000/mcp/execute/get_content \
  -H "Content-Type: application/json" \
  -d '{"library_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "query": "authentication"}'
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
   - `url_patterns`: Optional list of URL patterns to include (e.g., ["*docs*", "*guide*"])
   - `max_concurrent_crawls`: Maximum concurrent page crawls (default: 20)
   - `metadata`: Additional metadata (optional)

2. **search_libraries** - Search for available libraries by name
   - `query`: Search query for library names (e.g., 'react', 'nextjs', 'django')
   - `max_results`: Maximum results to return (1-50, default: 10)

3. **get_content** - Get code snippets from a library
   - `library_id`: Library ID (UUID) or library name (e.g., 'nextjs', 'react')
   - `query`: Optional search terms to filter results
   - `max_results`: Limit results (1-50, default: 10)

4. **get_snippet_details** - Get detailed information about a specific code snippet
   - `snippet_id`: The ID of the snippet (from get_content results)


## API Endpoints


### Crawling
- `POST /crawl/init` - Start new crawl job with optional URL pattern filtering
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

## Language Support

The LLM automatically detects and understands all programming languages, including:
- Python, JavaScript, TypeScript
- Java, Go, Rust, C/C++, C#
- Ruby, PHP, SQL, Bash
- HTML, CSS, YAML, JSON, XML
- And many more...

## LLM-Powered Code Extraction

CodeDox uses advanced Large Language Models to intelligently extract code from documentation:

### Features
- **Intelligent Understanding**: LLM comprehends context, purpose, and relationships
- **Rich Metadata**: Automatically extracts titles, descriptions, dependencies, and frameworks
- **Code Relationships**: Identifies imports, extends, implements, and usage patterns
- **Language Detection**: Automatically detects programming languages with high accuracy
- **Complete Examples**: Recognizes whether code blocks are complete or partial

### Configuration

**Environment Setup:**
```bash
# Required: Set your API key
export CODE_LLM_API_KEY="sk-your-api-key-here"

# Optional: Choose provider and model
export CODE_LLM_PROVIDER="openai"  # Options: openai, anthropic, ollama, groq, gemini, deepseek
export CODE_LLM_EXTRACTION_MODEL="gpt-4o-mini"  # Model name without provider prefix

# Example configurations for different providers:
# OpenAI (default)
export CODE_LLM_PROVIDER="openai"
export CODE_LLM_EXTRACTION_MODEL="gpt-4o-mini"  # or gpt-4o, o1-mini, o1-preview

# Anthropic Claude
export CODE_LLM_PROVIDER="anthropic"
export CODE_LLM_EXTRACTION_MODEL="claude-3-5-sonnet-20240620"  # or claude-3-opus-20240229

# Local Ollama
export CODE_LLM_PROVIDER="ollama"
export CODE_LLM_EXTRACTION_MODEL="llama3"
export CODE_LLM_BASE_URL="http://localhost:11434/v1"

# Groq
export CODE_LLM_PROVIDER="groq"
export CODE_LLM_EXTRACTION_MODEL="llama3-70b-8192"

# Optional: Custom LLM endpoint (for proxies or custom deployments)
export CODE_LLM_BASE_URL="https://your-custom-endpoint.com/v1"
```

**CLI Usage:**
```bash
# Crawl with LLM extraction (API key must be set in environment)
python cli.py crawl "Next.js" https://nextjs.org/docs

# Crawl with specific depth
python cli.py crawl "React" https://react.dev/learn --depth 2

# Crawl with URL patterns
python cli.py crawl "Django" https://docs.djangoproject.com \
  --url-patterns "*tutorial*" --url-patterns "*guide*"
```

**MCP Tool Usage:**
```json
{
  "name": "Next.js",
  "start_urls": ["https://nextjs.org/docs"],
  "max_depth": 2,
  "domain_filter": "nextjs.org"
}
```

## Development

### Project Structure
```
codedox/
├── src/
│   ├── api/          # FastAPI endpoints
│   ├── crawler/      # Web crawling logic
│   │   ├── extraction_models.py     # Pydantic models for LLM extraction
│   │   ├── config.py                # Crawler configuration
│   │   └── page_crawler.py          # Page crawling with LLM extraction
│   ├── database/     # Models and search
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

Test content hash optimization:
```bash
# This tests that unchanged content skips LLM extraction on re-crawls
python test_hash_optimization.py
```


## Performance

- **Search Speed**: < 100ms for full-text search
- **Storage**: ~50KB per code snippet with context
- **Content Hash Optimization**: Automatically skips LLM extraction for unchanged content during re-crawls
  - Saves significant time and API costs when updating documentation sources
  - Only processes pages with changed content
  - Tracks efficiency metrics (pages skipped vs processed)

## Troubleshooting

### Common Issues

**Database connection failed**
   - Check PostgreSQL is running
   - Verify credentials in `.env`

**LLM Extraction Issues**

Common problems and solutions:

1. **"'str' object has no attribute 'choices'" error**
   - This typically occurs with non-OpenAI compatible LLMs
   - The system will automatically fall back to markdown extraction
   - Check that your LLM endpoint returns OpenAI-compatible responses

2. **No code blocks extracted**
   - Verify your API key is set correctly: `echo $CODE_LLM_API_KEY`
   - Check you have API credits available
   - Review logs for specific extraction errors
   - The system will fall back to markdown-based extraction

3. **Local LLM compatibility (Ollama, Jan, etc.)**
   - Ensure your local LLM supports the OpenAI API format
   - Verify the base URL is correct (e.g., `http://localhost:11434/v1`)
   - Test with curl first:
     ```bash
     curl -X POST http://localhost:11434/v1/chat/completions \
       -H "Content-Type: application/json" \
       -d '{"model": "llama3", "messages": [{"role": "user", "content": "Hello"}]}'
     ```

**Note:** When LLM extraction fails, the page is marked as failed and can be retried later using the API:
```bash
# Retry failed pages from a previous job
curl -X POST http://localhost:8000/api/crawl-jobs/{job-id}/retry-failed
```

This will create a new crawl job that attempts to re-crawl only the failed pages.


## Upgrading

If you're upgrading from an older version of CodeDox, you may need to apply database migrations:

### Checking Your Current Schema

First, check if you need to run migrations:

```bash
# Connect to your database
psql -U postgres -d codedox

# Check if you have the old schema elements
\d crawl_jobs
\d documents
\d page_links
```

### Applying the Migration

There's a single migration file that will upgrade your database to the latest schema:

```bash
# Apply the migration (this combines all updates)
psql -U postgres -d codedox -f src/database/migrations/001_upgrade_to_latest.sql
```

This migration is safe to run multiple times - it checks for existing changes before applying them.

### What Changes

The migrations will:
- Remove the enrichment phase (now handled during crawling)
- Remove the `page_links` table (Crawl4AI handles navigation)
- Add proper relationship tracking between code snippets
- Update views to use crawl job metadata instead of document metadata
- Change default content type from 'html' to 'markdown'

### Backup First

Always backup your database before applying migrations:
```bash
pg_dump -U postgres -d codedox > codedox_backup_$(date +%Y%m%d).sql
```

### Fresh Installation

If you're starting fresh, just use:
```bash
python cli.py init
```

This will create all tables with the latest schema.

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

