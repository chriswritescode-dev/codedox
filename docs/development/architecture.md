# Architecture

## System Overview

CodeDox is built with a modular architecture focusing on scalability and maintainability.

## Core Components

### Crawler System
- **Crawl4AI Integration**: Headless browser automation
- **Job Manager**: Async job queue and state management
- **Page Crawler**: Individual page processing
- **URL Management**: Deduplication and pattern filtering

### Extraction Pipeline
- **HTML Parser**: BeautifulSoup-based code block detection
- **LLM Processor**: Optional AI enhancement for metadata
- **Content Hasher**: Change detection and deduplication
- **Language Detector**: Automatic language identification

### Database Layer
- **PostgreSQL**: Primary data store
- **Full-Text Search**: pg_trgm and tsvector indexing
- **Schema Migrations**: Version-controlled schema changes
- **Connection Pooling**: Efficient connection management

### API Server
- **FastAPI**: High-performance async API
- **MCP Endpoints**: Model Context Protocol integration
- **WebSocket Support**: Real-time crawl updates
- **CORS Middleware**: Cross-origin resource sharing

### Frontend
- **React + TypeScript**: Type-safe UI components
- **Vite**: Fast development and building
- **TailwindCSS**: Utility-first styling
- **React Query**: Server state management

## Data Flow

```
Documentation Site
       ↓
   Crawl4AI
       ↓
  HTML Parser
       ↓
  LLM Extractor (optional)
       ↓
   PostgreSQL
       ↓
  Search Index
       ↓
   API/MCP
       ↓
  AI Assistant
```

## Directory Structure

```
codedox/
├── src/
│   ├── api/           # FastAPI routes
│   ├── crawler/       # Crawling logic
│   ├── database/      # DB models and queries
│   ├── extraction/    # Code extraction
│   └── mcp_server/    # MCP implementation
├── frontend/          # React application
├── tests/            # Test suites
└── docs/             # Documentation
```

## Key Design Decisions

### PostgreSQL over Vector DB
- Simpler infrastructure
- Better for keyword search
- Lower operational overhead
- Built-in full-text search

### LLM-Optional Design
- Works without API keys
- HTML extraction as fallback
- Cost-effective for testing
- Progressive enhancement

### MCP Integration
- Direct AI assistant access
- Standardized protocol
- HTTP and stdio support
- Tool-based interface

## Performance Optimizations

### Crawling
- Concurrent page processing
- Domain-based rate limiting
- Content hash caching
- Incremental updates

### Search
- Indexed search vectors
- Weighted field ranking
- Query result caching
- Pagination support

### API
- Async request handling
- Connection pooling
- Response compression
- Static file caching

## Security Considerations

- Input validation
- SQL injection prevention
- Rate limiting
- Optional authentication
- Environment variable secrets

## Monitoring

- Structured logging
- Crawl job tracking
- Performance metrics
- Error reporting
- Health endpoints