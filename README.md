# CodeDox - Documentation Code Extraction & Search

A powerful system for crawling documentation websites, extracting code snippets, and providing fast search capabilities via MCP (Model Context Protocol) integration.

## Features

- **Controlled Web Crawling**: Manual crawling with configurable depth (0-3 levels)
- **Smart Code Extraction**: HTML-based extraction with VS Code language detection
- **LLM Descriptions**: AI-generated concise descriptions for extracted code
- **Fast Search**: PostgreSQL full-text search with < 100ms response time
- **MCP Integration**: Expose tools to AI assistants via Model Context Protocol
- **Source Management**: Track multiple documentation sources with statistics
- **Modern Web UI**: React-based dashboard for managing crawls, searching code, and monitoring system activity
- **Auto Site Content Deduplication**: Only updates or adds content that has changed


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
        VSD[VS Code<br/>Language Detection]
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
    HTML --> VSD
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
   - Detects language using VS Code's language detection model
   - Extracts filename hints from HTML attributes and context
   - Removes UI elements and clutter from code blocks

2. **LLM Description Generation**: Uses AI to generate concise descriptions
   - Analyzes each code block with its context
   - Generates 10-30 word descriptions focusing on the code's purpose
   - Uses context to understand the code's role in documentation
   - Only requires LLM for descriptions, not extraction

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 12+ 
- Node.js 14+ (for VS Code language detection)
- Playwright (installed automatically with crawl4ai)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/chriswritescode-dev/codedox.git
cd codedox
```

2. Run setup script:
```bash
./setup.sh
```

3. Set up PostgreSQL:
```bash
# Create database
createdb codedox

# Initialize database schema
python cli.py init
```

4. Configure environment:
```bash
# Edit .env with your settings (created by setup script)
```

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

**Direct API Usage:**
```bash
# List tools
curl http://localhost:8000/mcp/tools

# Get code snippets
curl -X POST http://localhost:8000/mcp/execute/get_content \
  -H "Content-Type: application/json" \
  -d '{"library_id": "nextjs", "query": "authentication"}'
```

### Available MCP Tools

1. **init_crawl** - Start documentation crawling
2. **search_libraries** - Search for available libraries  
3. **get_content** - Get code snippets from a library

See full tool documentation at `/mcp/tools` endpoint.


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
- **Language Detection**: Uses VS Code's language detection model for accurate results
- **Filename Hints**: Extracts filenames from HTML to improve language detection
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
│   │   ├── vscode_language_detector.py # VS Code language detection client
│   │   ├── llm_description_generator.py # AI description generation
│   │   ├── page_crawler.py            # Page crawling orchestration
│   │   ├── extraction_models.py       # Data models
│   │   └── code_formatter.py          # Code formatting utilities
│   ├── language_detector/      # VS Code language detection (Node.js)
│   │   ├── detect.js          # Language detection CLI
│   │   └── package.json       # Node dependencies
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
  - VS Code model for complex cases (~50ms per detection)
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
- Verify Node.js installed: `node --version`
- Reinstall VS Code detector: `cd src/language_detector && npm install`

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

