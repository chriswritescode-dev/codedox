# CodeDox Features

## Overview

CodeDox is a comprehensive documentation extraction and search system that transforms any documentation website into a searchable code database. This document provides detailed information about each feature, configuration options, and best practices.

## Table of Contents

- [Web Crawling](#web-crawling)
- [Code Extraction](#code-extraction)
- [Search Capabilities](#search-capabilities)
- [MCP Integration](#mcp-integration)
- [Web Dashboard](#web-dashboard)
- [Performance Optimization](#performance-optimization)
- [Upload Features](#upload-features)
- [API Features](#api-features)

## Web Crawling

### Depth-Controlled Crawling

CodeDox implements intelligent crawling with configurable depth levels (0-3) to control how deep into a documentation site the crawler explores.

**Depth Levels:**

- **Level 0**: Only crawl the provided URLs (no following links)
- **Level 1**: Crawl provided URLs and their direct links
- **Level 2**: Crawl two levels deep from starting URLs
- **Level 3**: Maximum depth for comprehensive documentation capture

**Usage Example:**

```bash
python cli.py crawl start "React" https://react.dev/docs --depth 2
```

### URL Pattern Filtering

Control which pages are crawled using glob patterns to focus on relevant documentation.

**Configuration Options:**

- `--url-patterns`: Include only URLs matching these patterns
- `--domain`: Restrict crawling to specific domains

**Examples:**

```bash
# Only crawl documentation pages
python cli.py crawl start "Next.js" https://nextjs.org \
  --url-patterns "*docs*" "*guide*" "*api*"

# Restrict to specific domain
python cli.py crawl start "Vue" https://vuejs.org \
  --domain "vuejs.org"
```

### Concurrent Crawling

Optimize crawl speed with configurable concurrent sessions while respecting server resources.

**Configuration:**

- Default: 3 concurrent pages
- Maximum: 20 concurrent pages
- Automatic rate limiting: 1 second delay between requests

### Crawl Management

**Available Commands:**

- `crawl start`: Initiate new crawl job
- `crawl status`: Check progress of specific job
- `crawl list`: View all crawl jobs
- `crawl cancel`: Stop running crawl
- `crawl resume`: Continue failed crawl
- `crawl health`: Monitor crawler health

## Code Extraction

### HTML-Based Extraction

**Extraction Process:**

1. Identifies code blocks 
2. Extracts surrounding context and titles
3. Captures filename hints from attributes
4. Removes UI elements (copy buttons, line numbers)
5. Preserves original formatting

### AI Enhancement

Optional LLM integration enhances extracted code with intelligent metadata.

**AI Features:**

- **Language Detection**: Identifies programming language from syntax
- **Title Generation**: Creates descriptive titles for code blocks
- **Description Generation**: Produces 20-60 word summaries
- **Relationship Mapping**: Identifies related code blocks

**Configuration:**

```bash
# Enable AI enhancement for better Title and snippet generation
CODE_ENABLE_LLM_EXTRACTION=true
CODE_LLM_API_KEY=your-api-key
CODE_LLM_EXTRACTION_MODEL=gpt-4o-mini

# Use local LLM (Ollama, etc.)
CODE_LLM_BASE_URL=http://localhost:11434/v1
CODE_LLM_EXTRACTION_MODEL=qwen2.5-coder:32b
```

## Search Capabilities

### PostgreSQL Full-Text Search

Lightning-fast search powered by PostgreSQL's native full-text search with weighted fields.

**Search Features:**

- **Weighted Fields**: Title (A) > Description (B) > Code (C)
- **Fuzzy Matching**: Handles typos and variations
- **Language Filters**: Search within specific languages
- **Source Filters**: Limit search to specific documentation sources

**Search Syntax:**

```bash
# Basic search
python cli.py search "authentication"

# With source filter
python cli.py search "middleware" --source "Express"

# Limit results
python cli.py search "database connection" --limit 20
```

### Advanced Search Options

**Web UI Search Features:**

- Real-time search as you type
- Full Markdown Results for more detailed information
- Syntax highlighting in results
- Filter by language, source, or date
- Sort by relevance or recency
- Pagination for large result sets

## MCP Integration

### Model Context Protocol Support

Native integration with MCP allows AI assistants to access CodeDox directly.

**Available Tools:**

1. **init_crawl**: Start documentation crawling

   ```json
   {
     "name": "React",
     "start_urls": ["https://react.dev/docs"],
     "max_depth": 2,
     "domain_filter": "react.dev"
   }
   ```

2. **search_libraries**: Find available documentation sources

   ```json
   {
     "query": "javascript frameworks",
     "limit": 10
   }
   ```

3. **get_content**: Retrieve code snippets

   ```json
   {
     "library_id": "react-docs",
     "query": "useState hook",
     "limit": 5
   }
   ```

4. **get_page_markdown**: Get full markdown content of a documentation page
   ```json
   {
     "url": "https://react.dev/docs/hooks"
   }
   ```

### MCP Transport Modes

**HTTP Mode** (Recommended):

- Endpoint: `http://localhost:8000/mcp`
- Transport: Streamable HTTP
- Authentication: Optional token-based

**SSE Mode** (Legacy):

- Endpoint: `http://localhost:8000/mcp/v1/sse`
- Transport: Server-Sent Events

**Stdio Mode** (Standalone):

- Command: `python cli.py serve --mcp`
- Transport: Standard input/output

### Authentication

Secure remote deployments with token-based authentication.

**Configuration:**

```bash
# Single token
MCP_AUTH_ENABLED=true
MCP_AUTH_TOKEN=your-secure-token

# Multiple tokens
MCP_AUTH_TOKENS=token1,token2,token3
```

**Usage:**

```bash
curl -H "Authorization: Bearer your-token" \
  http://localhost:8000/mcp/tools
```

## Web Dashboard

### Dashboard Features

**Real-time Statistics:**

- Total snippets extracted
- Active documentation sources
- Running crawl jobs
- Recent activity tracking

**Source Management:**

- View all documentation sources
- Browse extracted snippets
- Re-crawl with updated settings
- Delete sources and associated data
- Edit source names

**Crawl Monitoring:**

- Live progress tracking
- Success/failure rates
- Pages crawled counter
- Error logs

### User Interface

**Technology Stack:**

- React 18 with TypeScript
- Tailwind CSS for styling
- Vite for fast development
- ShadcnUI components

**Key Components:**

- Quick search bar
- Source explorer with tabs (Documents/Snippets)
- Snippet viewer with syntax highlighting
- Crawl job manager
- Pagination controls
- Dialog components for actions

## Performance Optimization

### Content Deduplication

Intelligent hash-based system prevents duplicate processing.

**How It Works:**

1. Generates MD5 hash of page content
2. Compares with stored hashes
3. Skips unchanged content
4. Only processes modified pages

**Benefits:**

- Reduces API costs by 60-90% on re-crawls
- Faster update cycles
- Lower database storage

### Caching Strategy

**Implementation:**

- Database query result caching
- Content hash caching
- Search result optimization

### Database Optimization

**Performance Features:**

- Indexes on search vectors
- Optimized full-text search
- Connection pooling
- Efficient pagination

## Upload Features

### Markdown Upload

Process local documentation files directly. Useful for downloading git hub docs and fast processing without hitting the website.

**Supported Formats:**

- Markdown (.md)
- MDX (.mdx)
- Plain text with code blocks

**Directory Upload:**

```bash
# Upload entire directory
python cli.py upload ./docs --name "Local Documentation"
```

### Batch Processing

**Features:**

- Recursive directory scanning
- Automatic language detection
- Progress tracking
- Bulk file processing

## API Features

### RESTful Endpoints

**Core Endpoints:**

- `GET /health`: System health check
- `POST /search`: Search code snippets
- `GET /snippets/{id}`: Get specific snippet

**Source Management:**

- `GET /api/sources`: List documentation sources
- `GET /api/sources/{source_id}`: Get source details
- `GET /api/sources/{source_id}/snippets`: Get snippets for source
- `DELETE /api/sources/{source_id}`: Delete source
- `POST /api/sources/{source_id}/recrawl`: Re-crawl source
- `PUT /api/sources/{source_id}`: Update source details

**Crawl Management:**

- `POST /crawl/init`: Start new crawl
- `GET /crawl/status/{job_id}`: Check crawl status
- `POST /crawl/cancel/{job_id}`: Cancel running job
- `GET /crawl/jobs`: List all crawl jobs

**Statistics:**

- `GET /api/statistics/dashboard`: Dashboard statistics

### WebSocket Support

Real-time updates for crawl progress and system events.

**Events:**

- `crawl_progress`: Live crawl status updates
- `job_complete`: Crawl completion notifications

## Configuration

### Environment Variables

**Essential Settings:**

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=codedox
DB_USER=postgres
DB_PASSWORD=postgres

# Code Extraction
CODE_ENABLE_LLM_EXTRACTION=true
CODE_LLM_API_KEY=your-key
CODE_LLM_EXTRACTION_MODEL=gpt-4o-mini
CODE_LLM_BASE_URL=https://api.openai.com/v1

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_CORS_ORIGINS=http://localhost:5173

# MCP Settings
MCP_AUTH_ENABLED=false
MCP_AUTH_TOKEN=your-token

# Crawling
CRAWL_DELAY=1.0
MAX_CONCURRENT_CRAWLS=20
```

### Docker Configuration

**Docker Compose Services:**

- PostgreSQL database
- API server
- Frontend development server

**Setup:**

```bash
# Use automated setup script
./docker-setup.sh

# Or manual setup
docker-compose up -d
```

## Best Practices

### Crawling Guidelines

1. **Start Small**: Begin with depth 1 for initial crawls
2. **Use Patterns**: Filter URLs to relevant documentation
3. **Monitor Progress**: Check crawl health regularly
4. **Respect Servers**: Keep default rate limiting

### Search Optimization

1. **Use Specific Queries**: More descriptive searches yield better results
2. **Filter by Source**: Narrow searches when possible
3. **Leverage Language Filters**: Specify programming language
4. **Use Pagination**: Navigate through large result sets

### API Usage

1. **Handle Errors**: Implement proper error handling
2. **Use Pagination**: Don't request all results at once
3. **Monitor Health**: Check `/health` endpoint

## Troubleshooting

### Common Issues

**No Code Extracted:**

- Verify crawl completed successfully
- Check HTML structure compatibility
- Review crawler logs for errors
- Ensure LLM API key is valid (if using AI mode)

**Poor Search Results:**

- Enable LLM extraction for better quality
- Re-crawl with different depth settings
- Check search query syntax

**Database Connection Issues:**

- Verify PostgreSQL is running
- Check database credentials in `.env`
- Ensure database exists and is initialized

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
# View API logs
docker-compose logs -f api

# View crawler logs
tail -f logs/codedox.log

# Check database
psql -U postgres -d codedox
```

## Integration Examples

### With Claude Desktop

Configure MCP server in Claude Desktop settings:

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

### With Custom AI Applications

```python
import requests

# Search for code
response = requests.post(
    "http://localhost:8000/mcp/execute/get_content",
    json={
        "library_id": "react-docs",
        "query": "component lifecycle"
    }
)

snippets = response.json()
```

## Support

For issues, questions, or feature requests:

- GitHub Issues: [github.com/chriswritescode-dev/codedox/issues](https://github.com/chriswritescode-dev/codedox/issues)
- Author: Chris Scott - [chriswritescode.dev](https://chriswritescode.dev)

