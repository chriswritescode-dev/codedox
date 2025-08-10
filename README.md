# CodeDox - Documentation Code Extraction & Search

A powerful system for crawling documentation websites, extracting code snippets, and providing fast search capabilities via MCP (Model Context Protocol) integration.

## Features

- **Controlled Web Crawling**: Manual crawling with configurable depth (0-3 levels)
- **Smart Code Extraction**: HTML-based extraction with LLM language detection
- **LLM Descriptions**: AI-generated concise descriptions for extracted code
- **Fast Search**: PostgreSQL full-text search 
- **MCP Integration**: Expose tools to AI assistants via Model Context Protocol
- **Modern Web UI**: React-based dashboard for managing crawls, searching code, and monitoring system activity
- **Auto Site Content Deduplication**: Only updates or adds content that has changed
- **Flexible Recrawl**: Choose to skip unchanged content or force regenerate all descriptions and titles

## Screenshots

### Dashboard
<img src="screenshots/WebUI-Dashboard.png" alt="CodeDox Dashboard" width="800">

*The dashboard provides an overview of your documentation sources, crawl jobs, and system statistics.*

### Source Detail View
<img src="screenshots/WebUI-Source-Detail.png" alt="CodeDox Source Detail" width="800">

*View detailed information about each documentation source, including extracted code snippets and search capabilities.*


## Architecture

```mermaid
graph TB
    subgraph "Frontend"
        UI[Web UI<br/>React + Vite + TypeScript]
    end
    
    subgraph "API Layer"
        API[FastAPI Server]
        MCP[MCP Tools]
    end
    
    subgraph "Processing Pipeline"
        Crawl[Crawl4AI<br/>Web Crawler]
        HTML[HTML Extraction<br/>BeautifulSoup]
        LLM[LLM Description<br/>Generator]
        Lang[LLM Language<br/>Detection]
    end
    
    subgraph "Storage"
        PG[(PostgreSQL<br/>Full-Text Search)]
    end
    
    subgraph "External"
        AI[AI Assistant<br/>MCP Client]
        WEB[Documentation<br/>Websites]
    end
    
    UI --> API
    AI --> MCP
    MCP --> API
    API --> PG
    API --> Crawl
    Crawl --> WEB
    Crawl --> HTML
    HTML --> Lang
    HTML --> LLM
    LLM --> PG
    
    style UI fill:#3b82f6,color:#fff
    style API fill:#10b981,color:#fff
    style PG fill:#f59e0b,color:#fff
    style AI fill:#8b5cf6,color:#fff
    style WEB fill:#6b7280,color:#fff
```

### Two-Step Code Extraction Process

CodeDox uses a sophisticated two-step approach for code extraction:

1. **HTML-Based Extraction**: Uses BeautifulSoup to extract code blocks from HTML with high accuracy
   - Identifies code blocks using multiple CSS selectors (pre, code, syntax highlighters)
   - Extracts surrounding context (titles, descriptions, container types)
   - Detects language using LLM analysis with source URL context
   - Extracts filename hints from HTML attributes and context
   - Removes UI elements and clutter from code blocks

2. **LLM Description Generation**: Uses AI to generate concise descriptions
   - Analyzes each code block with its context
   - Generates 10-30 word descriptions focusing on the code's purpose
   - Uses context to understand the code's role in documentation
   - Only requires LLM for descriptions, not extraction

## Quick Start

### 🐳 Docker Setup (Recommended - Easiest!)

Docker is the **preferred and easiest** way to get CodeDox running. Everything is automatically configured and managed for you - no manual database setup, no dependency issues, just one command to get started.

```bash
# Clone the repository
git clone https://github.com/chriswritescode-dev/codedox.git
cd codedox

# Configure environment
cp .env.example .env
# Edit .env to add your CODE_LLM_API_KEY

# Run the automated setup - this does everything!
./docker-setup.sh

# That's it! Access the web UI at:
# http://localhost:5173
```

**Why Docker is the best choice:**
- ✅ **Zero configuration** - Database, API, and frontend all set up automatically
- ✅ **No dependency conflicts** - Everything runs in isolated containers
- ✅ **One command setup** - Just run the setup script
- ✅ **Consistent environment** - Works the same on Mac, Linux, and Windows
- ✅ **Easy updates** - Pull latest changes and rebuild

The setup script automatically:
- Creates configuration from template
- Builds all Docker images
- Starts PostgreSQL, API, and Frontend services
- Initializes the database with proper schema
- Guides you through adding your OpenAI API key

### Alternative: Manual Installation

⚠️ **Note:** Manual installation requires more setup and configuration. We strongly recommend using Docker above for a smoother experience.

#### Prerequisites

- Python 3.10+
- PostgreSQL 12+ (must be installed and configured separately)
- Playwright (installed automatically with crawl4ai)

#### Manual Installation Steps

1. Clone the repository:
```bash
git clone https://github.com/chriswritescode-dev/codedox.git
cd codedox
```

2. Run setup script:
```bash
./setup.sh
```

3. Configure environment:
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and configure your settings
# At minimum, set CODE_LLM_API_KEY for code extraction
nano .env  # or use your preferred editor
```

4. Set up PostgreSQL:
```bash
# Create database
createdb codedox

# Initialize database schema
python cli.py init
```

5. Start the application:
```bash
# Activate virtual environment
source .venv/bin/activate

# Start all services (API + Web UI)
python cli.py serve
```

### Configuration

The system uses environment variables for configuration. Key settings in `.env`:

```bash
# Required: LLM API Configuration
CODE_LLM_API_KEY=your-api-key-here
CODE_LLM_EXTRACTION_MODEL=gpt-4o-mini  # or gpt-4, claude-3, etc.

# Optional: For local LLMs (Jan, Ollama, etc.)
CODE_LLM_BASE_URL=http://localhost:8001/v1

# Database (defaults work for local development)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=codedox
DB_USER=postgres
DB_PASSWORD=postgres
```

See `.env.example` for all available options including crawling, search, and API settings.

### Running the Application

```bash
# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Start everything (API + Web UI)
python cli.py serve
```

This starts:
- API server at http://localhost:8000
- Web UI at http://localhost:5173
- MCP tools at http://localhost:8000/mcp

For API-only mode: `python cli.py serve --api`
For MCP stdio server: `python cli.py serve --mcp`

## CLI Commands

CodeDox provides a streamlined CLI with 6 main commands:

### Core Commands

```bash
# Initialize database
python cli.py init [--drop]

# Start services (default: API + Web UI)
python cli.py serve              # Start both API and Web UI
python cli.py serve --api        # API server only
python cli.py serve --mcp        # MCP stdio server only

# Search for code snippets
python cli.py search <query> [--source NAME] [--limit 10]

# Upload markdown files
python cli.py upload <file> [--source-url URL] [--name NAME]

# Run tests
python cli.py test [--coverage] [--verbose]
```

### Crawl Management

The `crawl` command has several subcommands for managing documentation crawls:

```bash
# Start a new crawl
python cli.py crawl start <name> <urls...> [options]
  --depth N           # Max crawl depth (0-3, default: 1)
  --domain PATTERN    # Domain restriction pattern
  --url-patterns      # URL patterns to filter (e.g., "*docs*") will keep only URLs matching these patterns
  --concurrent N      # Max concurrent crawl sessions

# Check crawl status
python cli.py crawl status <job-id>

# List all crawl jobs
python cli.py crawl list

# Cancel a running crawl
python cli.py crawl cancel <job-id>

# Resume a failed crawl
python cli.py crawl resume <job-id>

# Check health of running crawls
python cli.py crawl health
```

### Examples

```bash
# Initialize a fresh database
python cli.py init --drop

# Start a documentation crawl
python cli.py crawl start "React" https://react.dev/reference --depth 2

# Check crawl progress
python cli.py crawl status abc-123-def

# Search for authentication code
python cli.py search "authentication middleware" --source "Next.js"

# Start the application
python cli.py serve
```

## MCP (Model Context Protocol) Integration

MCP tools are automatically available when running the API server at `http://localhost:8000/mcp`.

**For AI Assistants:**
- URL: `http://localhost:8000/mcp`
- Transport: Streamable HTTP

### MCP Authentication (for remote deployments)

CodeDox supports token-based authentication for MCP endpoints to secure remote deployments:

```bash
# Enable authentication in .env
MCP_AUTH_ENABLED=true
MCP_AUTH_TOKEN=your-secure-token-here

# Generate a secure token
openssl rand -hex 32
```

When authentication is enabled, include the token in all MCP requests:

```bash
# With authentication
curl -H "Authorization: Bearer your-secure-token-here" \
  http://localhost:8000/mcp/tools

# Multiple tokens supported
MCP_AUTH_TOKENS=token1,token2,token3
```

**Direct API Usage:**
```bash
# List tools (no auth)
curl http://localhost:8000/mcp/tools

# List tools (with auth)
curl -H "Authorization: Bearer your-token" \
  http://localhost:8000/mcp/tools

# Search for libraries
curl -X POST http://localhost:8000/mcp/execute/search_libraries \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{"query": "nextjs"}'

# Get code snippets
curl -X POST http://localhost:8000/mcp/execute/get_content \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{"library_id": "library-id-here", "query": "authentication"}'
```

### Available MCP Tools

1. **init_crawl** - Start documentation crawling
2. **search_libraries** - Search for available libraries  
3. **get_content** - Get code snippets from a library

See full tool documentation at `/mcp/tools` endpoint.


## API Endpoints

### Core Endpoints
- `GET /health` - Health check
- `POST /search` - Search code snippets
- `GET /snippets/{id}` - Get specific snippet

### Crawling
- `POST /crawl/init` - Start new crawl job with optional URL pattern filtering
- `GET /crawl/status/{job_id}` - Check crawl status
- `POST /crawl/cancel/{job_id}` - Cancel running job
- `GET /export/{job_id}` - Export crawl results

### Search
- `GET /api/search/languages` - List available languages
- `GET /api/search/recent` - Get recent snippets

### Sources
- `GET /api/sources` - List documentation sources
- `GET /api/sources/{source_id}` - Get specific source details
- `GET /api/sources/{source_id}/snippets` - Get snippets for a source
- `DELETE /api/sources/{source_id}` - Delete a source
- `POST /api/sources/{source_id}/recrawl` - Re-crawl a source

### Statistics
- `GET /api/statistics/dashboard` - Get dashboard statistics

### Upload
- `POST /upload/markdown` - Upload markdown content (currently disabled)
- `POST /upload/file` - Upload markdown file (currently disabled)

### MCP (Model Context Protocol)
- `POST /mcp` - MCP streamable HTTP endpoint
- `GET /mcp/tools` - List available MCP tools
- `POST /mcp/execute/{tool_name}` - Execute a specific MCP tool

## Web UI

Access the web interface at `http://localhost:5173` for:
- Dashboard with real-time statistics
- Advanced code search with syntax highlighting
- Documentation source management
- Live crawl monitoring
- Visual settings configuration

Built with React, TypeScript, and Tailwind CSS.

## Code Extraction & Description Generation

CodeDox uses a powerful two-phase approach to extract and understand code:

### Phase 1: HTML-Based Code Extraction
- **Smart Detection**: Identifies code blocks using 20+ CSS selector patterns
- **Language Detection**: Uses LLM for intelligent language detection with context
- **Filename Hints**: Extracts filenames from HTML to provide context to LLM
- **Context Extraction**: Captures surrounding documentation for better understanding
- **Clean Output**: Removes UI elements, line numbers, and other artifacts

### Phase 2: LLM Description Generation
- **Concise Descriptions**: Generates 10-30 word summaries of code purpose
- **Context-Aware**: Uses extracted context to understand code's role
- **Minimal LLM Usage**: Only uses AI for descriptions, not extraction
- **Fast & Efficient**: Processes hundreds of code blocks per minute

### Configuration

Set your API key in `.env` for description generation:
```bash
CODE_LLM_API_KEY="sk-your-api-key-here"
CODE_LLM_PROVIDER="openai"  # or anthropic, ollama, groq, etc.
CODE_LLM_EXTRACTION_MODEL="Qwen3-Coder-30B-A3B-Instruct"
```

### Usage

```bash
# Start a crawl
python cli.py crawl start "Next.js" https://nextjs.org/docs --depth 2

# Check crawl status
python cli.py crawl status <job-id>

# List all crawl jobs
python cli.py crawl list

# Search code
python cli.py search "authentication" --limit 10
```

## Development

### Project Structure

<details>
<summary>Click to expand project structure</summary>

```
codedox/
├── src/
│   ├── api/                    # FastAPI server & endpoints
│   │   ├── routes/            # API route handlers
│   │   │   ├── crawl_jobs.py # Crawl job management endpoints
│   │   │   ├── health.py     # Health check endpoints
│   │   │   ├── search.py     # Search endpoints
│   │   │   ├── snippets.py   # Code snippet endpoints
│   │   │   ├── sources.py    # Documentation source endpoints
│   │   │   ├── statistics.py # Dashboard statistics
│   │   │   └── upload.py     # File upload endpoints
│   │   ├── auth.py           # Authentication middleware
│   │   ├── main.py           # FastAPI app initialization
│   │   ├── mcp_routes.py     # MCP protocol routes
│   │   ├── mcp_server.py     # MCP server implementation
│   │   ├── mcp_streamable.py # Streamable HTTP MCP transport
│   │   └── websocket.py      # WebSocket for real-time updates
│   ├── crawler/               # Web crawling & extraction
│   │   ├── html_code_extractor.py     # HTML-based code extraction
│   │   ├── markdown_code_extractor.py # Markdown file extraction
│   │   ├── page_crawler.py            # Page crawling orchestration
│   │   ├── crawl_manager.py           # Crawl job management
│   │   ├── job_manager.py             # Job queue management
│   │   ├── result_processor.py        # Process crawl results
│   │   ├── progress_tracker.py        # Track crawl progress
│   │   ├── health_monitor.py          # Monitor crawl health
│   │   ├── failed_page_utils.py       # Handle failed pages
│   │   ├── llm_retry.py               # LLM retry logic
│   │   ├── llm_regenerate.py          # Regenerate descriptions
│   │   ├── upload_processor.py        # Process uploaded files
│   │   ├── code_formatter.py          # Code formatting utilities
│   │   ├── extraction_models.py       # Data models
│   │   ├── language_mapping.py        # Language detection mapping
│   │   ├── domain_utils.py            # Domain filtering utilities
│   │   ├── config.py                  # Crawler configuration
│   │   └── utils.py                   # Utility functions
│   ├── database/              # PostgreSQL models & search
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── connection.py      # Database connection
│   │   ├── search.py          # Full-text search implementation
│   │   └── content_check.py   # Content deduplication
│   ├── mcp_server/            # MCP tools implementation
│   │   ├── server.py          # MCP server core
│   │   └── tools.py           # MCP tool definitions
│   └── config.py              # Application configuration
├── frontend/                  # React web UI
│   ├── src/
│   │   ├── components/        # React components
│   │   │   ├── Layout.tsx             # App layout wrapper
│   │   │   ├── QuickSearch.tsx        # Search component
│   │   │   ├── SnippetList.tsx        # Code snippet list
│   │   │   ├── CrawlProgress.tsx      # Crawl progress display
│   │   │   ├── SourceActions.tsx      # Source action buttons
│   │   │   ├── SourceDocumentsTab.tsx # Source documents tab
│   │   │   ├── SourceSnippetsTab.tsx  # Source snippets tab
│   │   │   ├── EditableSourceName.tsx # Editable source name
│   │   │   ├── PaginationControls.tsx # Pagination controls
│   │   │   ├── NewCrawlDialog.tsx     # New crawl dialog
│   │   │   ├── RecrawlDialog.tsx      # Recrawl dialog
│   │   │   ├── ConfirmationDialog.tsx # Confirmation dialog
│   │   │   └── ui/                    # UI components
│   │   ├── pages/            # Page components
│   │   │   ├── Dashboard.tsx # Main dashboard
│   │   │   ├── Search.tsx    # Search page
│   │   │   ├── Sources.tsx   # Sources list
│   │   │   ├── SourceDetail.tsx       # Source details
│   │   │   ├── DocumentDetail.tsx     # Document details
│   │   │   ├── SnippetDetail.tsx      # Snippet details
│   │   │   ├── CrawlJobs.tsx          # Crawl job management
│   │   │   ├── CrawlDetail.tsx        # Crawl job details
│   │   │   └── Upload.tsx             # File upload
│   │   ├── hooks/            # Custom React hooks
│   │   ├── lib/              # Utilities and API client
│   │   └── App.tsx           # Main app component
│   └── vite.config.ts        # Vite configuration
├── tests/                     # Test suite
├── cli.py                     # Command-line interface
├── setup.sh                   # Automated setup script
├── docker-compose.yml         # Docker services
├── docker-setup.sh           # Docker setup script
└── .env.example              # Environment template
```

</details>

### Running Tests
```bash
pytest tests/
```

Test content hash optimization:
```bash
# This tests that unchanged content skips re-processing on re-crawls
python test_hash_optimization.py
```


## Performance

- **Search Speed**: < 100ms for full-text search
- **HTML Extraction**: Processes 100+ code blocks per second
  - No API calls needed for code extraction
  - Parallel processing of multiple code blocks
- **LLM Description Generation**: 
  - Only used for descriptions (10-30 words each)
  - Batch processing reduces API calls
  - Recommend using free local models if possible (Great results with Qwen3-Coder-30B-A3B-Instruct & Qwen3-4B-Instruct-2507)
- **Content Hash Optimization**: Automatically skips llm calls for unchanged content during re-crawls
  - Saves significant time and API costs when updating documentation sources
  - Only processes pages with changed content

## Troubleshooting

**Database Issues**
- Ensure PostgreSQL is running and credentials in `.env` are correct

**No Descriptions Generated**
- Check API key: `echo $CODE_LLM_API_KEY`
- Verify API credits available
- System works without descriptions (extraction always succeeds)

**Language Detection Issues**
- Ensure CODE_LLM_API_KEY is set in .env
- Check LLM API connectivity and credits

For detailed troubleshooting, see the [documentation wiki](https://github.com/chriswritescode-dev/codedox/wiki).


## Upgrading

For existing installations:
```bash
# Backup database first
pg_dump -U postgres -d codedox > backup.sql

# Apply migrations
psql -U postgres -d codedox -f src/database/migrations/001_upgrade_to_latest.sql

# Remove markdown_content column (saves storage)
psql -U postgres -d codedox -f src/database/migrations/003_remove_markdown_content.sql
```

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push branch (`git push origin feature/amazing`)
5. Open Pull Request

## Author

**Chris Scott** - [chriswritescode.dev](https://chriswritescode.dev)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

