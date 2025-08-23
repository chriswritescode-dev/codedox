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

- Extracts code blocks from any documentation website
- AI-powered language detection and description generation
- Preserves context and relationships between code blocks
- Works with all major documentation frameworks

### Lightning-Fast Search

- PostgreSQL full-text search with sub-100ms response times
- Fuzzy matching for typos and variations
- Filter by language, source, or documentation type
- Export and save search results

### MCP Integration

- Native Model Context Protocol support
- Direct integration with Claude, GPT, and other AI assistants
- Secure token-based authentication for remote deployments
- Multiple transport modes (HTTP, SSE, Stdio)

### Modern Web Dashboard

- Real-time crawl monitoring
- Visual search interface with syntax highlighting
- Source management and statistics
- Built with React, TypeScript, and Tailwind CSS

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
# Crawl React documentation
python cli.py crawl start "React" https://react.dev/docs --depth 2

# Check crawl status
python cli.py crawl status <job-id>
```

### 2. Search for Code

```bash
# Search via CLI
python cli.py search "useState hook" --source "React"

# Or use the web UI at http://localhost:5173
```

### 3. Integrate with AI Assistants

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

**POST /search**

```json
{
  "query": "authentication middleware",
  "source": "Express",
  "language": "javascript",
  "limit": 20
}
```

### Crawl Management

**POST /crawl/init**

```json
{
  "name": "Vue.js Documentation",
  "start_urls": ["https://vuejs.org/docs"],
  "max_depth": 2,
  "domain_filter": "vuejs.org",
  "url_patterns": ["*docs*", "*guide*"]
}
```

**GET /crawl/status/{job_id}**
Returns current crawl progress and statistics.

### MCP Tools

**init_crawl** - Start documentation crawling

```json
{
  "name": "Next.js",
  "start_urls": ["https://nextjs.org/docs"],
  "max_depth": 2
}
```

**search_libraries** - Find available documentation sources

```json
{
  "query": "javascript",
  "limit": 10
}
```

**get_content** - Retrieve code snippets

```json
{
  "library_id": "nextjs-docs",
  "query": "routing",
  "limit": 5
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

### Optimization Features

- Content deduplication saves 60-90% on re-crawl costs
- Intelligent caching at multiple levels
- Database query optimization with indexes
- Concurrent crawling with configurable limits

## Use Cases

### Development Teams

- Centralize all documentation for your tech stack
- Quick code example discovery during development
- Onboard new developers with searchable knowledge base

### AI Assistant Enhancement

- Provide AI assistants with up-to-date documentation
- Enable code-aware responses with real examples
- Build custom AI tools with documentation context

### Documentation Management

- Monitor documentation coverage
- Track code example quality
- Identify documentation gaps

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
A: CodeDox itself is free and open source. Optional AI enhancement costs depend on your LLM provider (OpenAI, Anthropic, or local models).

**Q: Can I use local LLMs?**
A: Yes! CodeDox supports Ollama and any OpenAI-compatible API endpoint.

### Troubleshooting

For detailed troubleshooting, see:

- [Features Documentation](FEATURES.md#troubleshooting)
- [GitHub Issues](https://github.com/chriswritescode-dev/codedox/issues)

---

**Ready to transform your documentation into a searchable knowledge base?**

[Get Started with CodeDox →](https://github.com/chriswritescode-dev/codedox)
