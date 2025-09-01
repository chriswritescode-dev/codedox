# CodeDox Documentation

**Transform any documentation site into a searchable code database**

CodeDox is an AI-powered documentation extraction and search system that crawls documentation websites, intelligently extracts code snippets with context, and provides lightning-fast search capabilities through PostgreSQL full-text search and Model Context Protocol (MCP) integration.

## Quick Links

- [GitHub Repository](https://github.com/chriswritescode-dev/codedox)
- [Features Documentation](FEATURES.md)
- [Upload Feature Guide](upload-feature.md)
- [Installation Guide](#installation)
- [API Reference](#api-reference)

## Why CodeDox?

### The Problem

Developers spend countless hours searching through documentation sites for code examples. Documentation is scattered across different sites, formats, and versions, making it difficult to find relevant code quickly.

### The Solution

CodeDox solves this by:

- **Centralizing** all your documentation sources in one searchable database
- **Extracting** code with intelligent context understanding
- **Providing** instant search across all your documentation
- **Integrating** directly with AI assistants via MCP

## Key Features

### Intelligent Code Extraction

- **AI-Enhanced Processing**: LLM-powered language detection, title generation, and intelligent descriptions
- **Multi-Format Support**: Extracts from Markdown, HTML, text files, and 20+ documentation frameworks
- **Smart Context Preservation**: Maintains relationships and surrounding context for better code understanding
- **Batch Processing**: Efficient parallel processing with configurable concurrency

### Lightning-Fast Search

- **Full-Text Search**: PostgreSQL-powered search with weighted fields (title > description > code)
- **Advanced Filtering**: Filter by language, source, date range, snippet count, and content type
- **Fuzzy Matching**: Built-in typo tolerance and similarity scoring
- **Document-Level Search**: Search within specific documentation pages with highlighting

### File Upload System

- **Batch File Upload**: Upload multiple markdown/text files simultaneously
- **Directory Processing**: Recursive directory scanning with progress tracking
- **Smart Deduplication**: Content-hash based duplicate detection across uploads and crawls
- **Mixed Sources**: Seamlessly search across crawled and uploaded content

### Advanced Crawl Management

- **Health Monitoring**: Real-time job health tracking with stall detection
- **Resume Capability**: Automatically resume failed crawls from last checkpoint
- **Depth Control**: Configurable crawl depth (0-3) with URL pattern filtering  
- **Domain Intelligence**: Smart domain detection and restriction
- **Recrawl Support**: Update existing sources with content-hash optimization

### MCP Integration

- **Multiple Transport Modes**: HTTP (recommended), Server-Sent Events, and Stdio
- **4 Core Tools**: `init_crawl`, `search_libraries`, `get_content`, `get_page_markdown`
- **Token Authentication**: Secure remote deployments with multiple token support
- **Pagination Support**: Built-in pagination for large result sets

### Modern Web Dashboard

- **Real-Time Monitoring**: Live crawl progress with WebSocket updates
- **Source Management**: Edit names, bulk operations, filtered deletion
- **Advanced Search UI**: Multi-criteria filtering with instant results
- **Document Browser**: Full markdown viewing with syntax highlighting
- **Performance Analytics**: Detailed statistics and crawl health metrics

## What's New in Latest Version

### Advanced File Upload System
- **Batch Upload**: Upload multiple markdown files simultaneously with progress tracking
- **Directory Processing**: Recursive directory scanning with automatic file type detection  
- **Smart Deduplication**: Content-hash based duplicate detection across all sources

### Enhanced Crawl Management
- **Health Monitoring**: Real-time job health tracking with automatic stall detection
- **Resume Capability**: Automatically resume failed crawls from the last successful checkpoint
- **Bulk Operations**: Manage multiple crawl jobs with bulk cancel, delete, and status operations

### Powerful Search & Filtering
- **Document-Level Search**: Search within specific documentation pages with highlighted results
- **Advanced Filtering**: Filter sources by snippet count, date range, content type, and more
- **Pagination Support**: Navigate through large result sets efficiently across all endpoints

### MCP Tool Enhancements
- **get_page_markdown**: New tool to retrieve full documentation pages with search and chunking
- **Improved get_content**: Enhanced with pagination and better library name resolution
- **Token Chunking**: Intelligent content chunking for large documents with overlap support

## Installation

### Docker Setup (Recommended)

The easiest way to get started with CodeDox:

```bash
# Clone the repository
git clone https://github.com/chriswritescode-dev/codedox.git
cd codedox

# Configure environment
cp .env.example .env
# Edit .env to add your CODE_LLM_API_KEY (optional)

# Run automated setup
./docker-setup.sh

# Access the web UI at http://localhost:5173
```

### Manual Installation

For detailed manual installation instructions, see the [README](https://github.com/chriswritescode-dev/codedox#manual-installation).

## Quick Start Guide

### 1. Start Your First Crawl

```bash
# Crawl React documentation with pattern filtering
python cli.py crawl start "React" https://react.dev/docs --depth 2 \
  --url-patterns "*docs*" "*guide*" --concurrent 10

# Check crawl status and health
python cli.py crawl status <job-id>
python cli.py crawl health
```

### 2. Upload Local Documentation

```bash
# Upload single markdown file
python cli.py upload /path/to/docs.md --name "My Docs"

# Process entire documentation directory
python cli.py upload ./docs-directory --name "Local Documentation"
```

### 3. Search and Explore Content

```bash
# Search across all sources
python cli.py search "authentication middleware"

# Search within specific source
python cli.py search "useState hook" --source "React"

# Use the advanced web UI at http://localhost:5173
```

### 4. Integrate with AI Assistants

Configure your AI assistant to use CodeDox:

```json
{
  "mcpServers": {
    "codedox": {
      "url": "http://localhost:8000/mcp",
      "transport": "http"
    }
  }
}
```

### 5. Manage and Monitor

```bash
# List all crawl jobs
python cli.py crawl list

# Resume failed crawl
python cli.py crawl resume <job-id>

# Cancel running jobs
python cli.py crawl cancel <job-id>
```

## Documentation Structure

### Core Documentation

- [Features](FEATURES.md) - Detailed feature documentation
- [Upload Guide](upload-feature.md) - Directory and file upload instructions
- [API Reference](#api-reference) - Complete API documentation

### Guides

- [Installation Guide](https://github.com/chriswritescode-dev/codedox#installation)
- [Configuration Guide](https://github.com/chriswritescode-dev/codedox#configuration)
- [MCP Integration](https://github.com/chriswritescode-dev/codedox#mcp-model-context-protocol-integration)

## API Reference

### Search Endpoints

**GET /search** - Advanced code search

```json
{
  "query": "authentication middleware",
  "source_name": "Express",
  "language": "javascript",
  "limit": 20,
  "offset": 0
}
```

### Source Management

**GET /sources** - List all documentation sources
**GET /sources/search** - Advanced source filtering
**GET /sources/{id}/documents** - Browse source documents  
**GET /sources/{id}/snippets** - Get source code snippets
**DELETE /sources/bulk** - Bulk source deletion
**POST /sources/bulk/delete-filtered** - Delete by criteria
**PATCH /sources/{id}** - Update source names
**POST /sources/{id}/recrawl** - Recrawl existing sources

### Document Access

**GET /documents/markdown?url={url}** - Get full page markdown
**GET /documents/{id}/markdown** - Get document by ID
**GET /documents/search** - Search documents by title/URL
**GET /documents/{id}/snippets** - Get document code snippets

### Crawl Management

**POST /crawl/init** - Advanced crawl configuration

```json
{
  "name": "Vue.js Documentation",
  "start_urls": ["https://vuejs.org/docs"],
  "max_depth": 2,
  "domain_filter": "vuejs.org",
  "url_patterns": ["*docs*", "*guide*", "*api*"],
  "max_concurrent_crawls": 15,
  "max_pages": 1000
}
```

**GET /crawl/status/{job_id}** - Detailed progress tracking
**POST /crawl/cancel/{job_id}** - Cancel running jobs
**POST /crawl-jobs/bulk/cancel** - Bulk job cancellation
**DELETE /crawl-jobs/bulk** - Bulk job deletion

### Upload System

**POST /upload/file** - Single file upload

```json
{
  "file": "documentation.md",
  "name": "Project Documentation",
  "title": "Custom Title"
}
```

**POST /upload/files** - Batch file upload

```json
{
  "files": ["doc1.md", "doc2.md", "doc3.md"],
  "name": "Documentation Set"
}
```

**POST /upload/markdown** - Direct content upload

```json
{
  "content": "# Title\n\n```python\nprint('hello')\n```",
  "name": "Code Examples"
}
```

### MCP Tools

**init_crawl** - Start documentation crawling with advanced options

```json
{
  "name": "Next.js",
  "start_urls": ["https://nextjs.org/docs"],
  "max_depth": 2,
  "domain_filter": "nextjs.org",
  "url_patterns": ["*docs*", "*guide*", "*api*"],
  "max_concurrent_crawls": 20
}
```

**search_libraries** - Find available libraries with pagination

```json
{
  "query": "javascript",
  "limit": 20,
  "page": 1
}
```

**get_content** - Retrieve code snippets with search within library

```json
{
  "library_id": "nextjs-docs",
  "query": "routing middleware",
  "limit": 10,
  "page": 1
}
```

**get_page_markdown** - Get full documentation page with search and chunking

```json
{
  "url": "https://nextjs.org/docs/app/building-your-application/routing",
  "query": "middleware",
  "max_tokens": 2048,
  "chunk_index": 0
}
```

## Architecture Overview

CodeDox uses a modular architecture designed for scalability and extensibility:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Web UI    │────▶│   FastAPI   │────▶│ PostgreSQL  │
│   (React)   │     │   Server    │     │  Database   │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │     MCP     │
                    │   Server    │
                    └─────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              ┌─────────┐   ┌─────────┐
              │   AI    │   │   AI    │
              │Assistant│   │Assistant│
              └─────────┘   └─────────┘
```

### Components

- **Web UI**: React-based dashboard for visual management
- **API Server**: FastAPI backend handling requests and crawls
- **PostgreSQL**: Full-text search and data storage
- **MCP Server**: Protocol bridge for AI assistants
- **Crawler**: Crawl4AI-based web scraping engine
- **Extractor**: HTML and LLM-based code extraction

### Performance & Optimization Features

**Smart Content Management**
- Content-hash based deduplication saves 60-90% on re-crawl costs
- Intelligent caching at multiple levels (database, search, content)
- Batch processing with configurable concurrency limits
- Progressive crawling with depth and pattern controls

**Advanced Database Features** 
- PostgreSQL full-text search with custom ranking
- Optimized indexes on search vectors and metadata
- Efficient pagination with cursor-based navigation
- Bulk operations for source and job management

**Health & Monitoring**
- Real-time crawl health monitoring with stall detection
- WebSocket-based progress updates
- Failed page tracking and retry mechanisms
- Performance analytics and crawl statistics

**Scalability Features**
- Configurable concurrent crawl sessions (up to 20)
- Batch upload processing with size limits
- Memory-efficient chunk processing for large documents
- Rate limiting and polite crawling with configurable delays

## Use Cases

### Development Teams

- **Centralized Documentation**: Aggregate all framework docs, internal guides, and code examples in one searchable database
- **Rapid Development**: Find relevant code patterns instantly without browsing multiple documentation sites
- **Team Onboarding**: Create searchable knowledge bases combining public docs with internal documentation
- **Code Discovery**: Use advanced filtering to find examples by language, framework version, or specific patterns

### AI Assistant Enhancement

- **Smart Code Context**: Provide AI assistants with up-to-date, relevant code examples from actual documentation
- **Documentation-Aware Responses**: Enable AI to reference specific documentation pages and code snippets
- **Custom Knowledge Bases**: Build domain-specific AI tools with curated documentation sets
- **Real-Time Updates**: Keep AI assistants current with latest framework changes through automated recrawling

### Documentation Management

- **Batch Operations**: Process large documentation sets efficiently with concurrent crawling and batch uploads
- **Content Deduplication**: Automatically detect and handle duplicate content across multiple sources
- **Performance Optimization**: Use intelligent caching and content-hash tracking to minimize re-processing costs

## Contributing

We welcome contributions! CodeDox is open source and accepts pull requests for:

- New documentation framework support
- Additional extraction patterns
- Performance improvements
- Bug fixes and enhancements

See our [GitHub repository](https://github.com/chriswritescode-dev/codedox) for contribution guidelines.

## Support

- **Issues**: [GitHub Issues](https://github.com/chriswritescode-dev/codedox/issues)
- **Author**: Chris Scott - [chriswritescode.dev](https://chriswritescode.dev)
- **License**: MIT

## Getting Help

### Common Questions

**Q: Do I need an API key to use CodeDox?**
A: No, CodeDox works without API keys in standalone mode. API keys enable enhanced AI features for better extraction quality.

**Q: What documentation sites are supported?**
A: CodeDox works with any HTML-based documentation site, including Docusaurus, VitePress, MkDocs, Sphinx, and custom sites.

**Q: How much does it cost to run?**
A: CodeDox itself is free and open source. Optional AI enhancement costs depend on your LLM provider (OpenAI, Anthropic, or local models). Smart deduplication reduces API costs by 60-90% on re-crawls.

**Q: Can I use local LLMs?**
A: Yes! CodeDox supports Ollama and any OpenAI-compatible API endpoint. Configure `CODE_LLM_BASE_URL` to point to your local model server.

**Q: What file types can I upload?**
A: Currently supports Markdown (.md), MDX (.mdx), and plain text files (.txt). Batch upload supports multiple files simultaneously with automatic duplicate detection.

**Q: How does health monitoring work?**
A: CodeDox automatically monitors crawl jobs for stalls, tracks progress via heartbeats, and can resume failed jobs. Use `python cli.py crawl health` to check job status or use the web UI to view active jobs.

**Q: Can I recrawl existing sources?**
A: Yes! Use the recrawl feature to update existing documentation sources. Content-hash tracking ensures only changed pages are reprocessed, saving time and API costs.

### Troubleshooting

For detailed troubleshooting, see:

- [Features Documentation](FEATURES.md#troubleshooting)
- [GitHub Issues](https://github.com/chriswritescode-dev/codedox/issues)

---

**Ready to transform your documentation into a searchable knowledge base?**

[Get Started with CodeDox →](https://github.com/chriswritescode-dev/codedox)
