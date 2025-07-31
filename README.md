# CodeDox - Documentation Code Extraction & Search

A powerful system for crawling documentation websites, extracting code snippets, and providing fast search capabilities via MCP (Model Context Protocol) integration.

## Features

- **Controlled Web Crawling**: Manual crawling with configurable depth (0-3 levels)
- **Smart Code Extraction**: HTML-based extraction with LLM language detection
- **LLM Descriptions**: AI-generated concise descriptions for extracted code
- **Fast Search**: PostgreSQL full-text search with < 100ms response time
- **MCP Integration**: Expose tools to AI assistants via Model Context Protocol
- **Source Management**: Track multiple documentation sources with statistics
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

### Option 1: Using Docker (Recommended)

The easiest way to get started is with Docker. Everything is automatically set up for you.

```bash
# Clone the repository
git clone https://github.com/chriswritescode-dev/codedox.git
cd codedox

# Configure environment
cp .env.example .env
# Edit .env to add your CODE_LLM_API_KEY

# Run the automated setup
./docker-setup.sh

# That's it! Access the web UI at:
# http://localhost:5173
```

The setup script will:
- Create configuration from template
- Build all Docker images
- Start PostgreSQL, API, and Frontend services
- Initialize the database automatically
- Guide you through adding your OpenAI API key

### Option 2: Manual Installation

#### Prerequisites

- Python 3.10+
- PostgreSQL 12+ 
- Playwright (installed automatically with crawl4ai)

#### Installation

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
python cli.py all
```

This starts:
- API server at http://localhost:8000
- Web UI at http://localhost:5173
- MCP tools at http://localhost:8000/mcp

For running services separately, see `python cli.py --help`

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
CODE_LLM_EXTRACTION_MODEL="gpt-4o-mini"
```

### Usage

```bash
# Crawl documentation
python cli.py crawl "Next.js" https://nextjs.org/docs --depth 2

# Search code
python cli.py search "authentication" --limit 10
```

## Development

### Project Structure

```
codedox/
├── src/
│   ├── api/                    # FastAPI server & endpoints
│   ├── crawler/                # Web crawling & extraction
│   │   ├── html_code_extractor.py     # HTML-based code extraction
│   │   # VS Code language detection removed - using LLM detection
│   │   ├── llm_description_generator.py # AI description generation
│   │   ├── page_crawler.py            # Page crawling orchestration
│   │   ├── extraction_models.py       # Data models
│   │   └── code_formatter.py          # Code formatting utilities
│   # Language detection now handled by LLM
# Language detector files removed
│   ├── database/              # PostgreSQL models & search
│   ├── mcp_server/            # MCP tools implementation
│   └── utils/                 # Shared utilities
├── frontend/                  # React web UI
├── tests/                     # Test suite
├── setup.sh                   # Automated setup script
├── docker-compose.yml         # Docker services
└── .env.example              # Environment template
```

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
- **Storage**: ~50KB per code snippet with context
- **HTML Extraction**: Processes 100+ code blocks per second
  - No API calls needed for code extraction
  - Parallel processing of multiple code blocks
  - Efficient CSS selector matching
- **Language Detection**: 
  - Instant detection from HTML classes and filenames
  - LLM language detection with source URL context
  - Smart caching of detection results
- **LLM Description Generation**: 
  - Only used for descriptions (10-30 words each)
  - Batch processing reduces API calls
  - ~1-2 seconds per code block with descriptions
- **Content Hash Optimization**: Automatically skips processing for unchanged content during re-crawls
  - Saves significant time and API costs when updating documentation sources
  - Only processes pages with changed content
  - Tracks efficiency metrics (pages skipped vs processed)

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

**Chris Scott** - Initial work and development

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

