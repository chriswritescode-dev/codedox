# Docker Setup for CodeDox

## Overview

CodeDox provides a complete Docker setup for running all services in containers. This includes PostgreSQL, the API server, and the MCP server.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB+ available RAM
- 10GB+ available disk space

## Quick Start

```bash
# 1. Copy and configure environment file
cp .env.example .env
# Edit .env to add your CODE_LLM_API_KEY

# 2. Build and start all services
docker-compose up -d

# 3. Database is automatically initialized on first start

# 4. Access the services
# Web UI: http://localhost:5173
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# MCP tools: http://localhost:8000/mcp/*
```

## Services

### 1. PostgreSQL Database
- Image: `pgvector/pgvector:pg15`
- Port: `5432`
- Database: `codedox`
- User: `postgres`
- Password: `postgres`

### 2. API Server
- Port: `8000`
- Includes REST API and MCP HTTP endpoints
- Auto-restarts on failure
- MCP tools available at `/mcp/*` endpoints

### 3. Frontend (React)
- Port: `5173`
- Web UI for searching and managing documentation
- Connects to API server at `http://localhost:8000`

### 4. pgAdmin (Optional)
- Port: `5050`
- Email: `admin@example.com`
- Password: `admin`
- Enable with: `docker-compose --profile debug up -d pgadmin`

**Note:** The standalone MCP stdio server is commented out in docker-compose.yml since MCP tools are exposed via the API server's HTTP endpoints. Uncomment if you need stdio-based MCP for specific AI assistant integrations.

## Configuration

### Environment Variables

A single `.env` file is used for both local and Docker deployments:

1. Copy `.env.example` to `.env`
2. Configure your settings (especially `CODE_LLM_API_KEY`)
3. Docker Compose automatically overrides `DB_HOST=postgres` for container networking

Key settings:
```env
# For local development
DB_HOST=localhost

# Docker automatically overrides to:
# DB_HOST=postgres  # Uses Docker service name

# Required for code extraction
CODE_LLM_API_KEY=your-api-key
CODE_LLM_EXTRACTION_MODEL=gpt-4o-mini  # or Jan, claude-3, etc.
# CODE_LLM_BASE_URL=http://localhost:8001/v1  # For local LLMs
```

### Volumes

- `postgres_data` - PostgreSQL data persistence
- `./logs:/app/logs` - Application logs

## Common Operations

### Build Images
```bash
# Build without cache
docker-compose build --no-cache

# Build specific service
docker-compose build api
```

### Start Services
```bash
# Start all services
docker-compose up -d

# Start specific services
docker-compose up -d postgres api

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
```

### Stop Services
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

### Database Operations
```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U postgres -d codedox

# Run SQL file
docker-compose exec -T postgres psql -U postgres -d codedox < script.sql

# Backup database
docker-compose exec postgres pg_dump -U postgres codedox > backup.sql
```

### Debugging
```bash
# View running containers
docker-compose ps

# Check service health
docker-compose exec api curl http://localhost:8000/health

# Shell into container
docker-compose exec api /bin/bash

# View real-time logs
docker-compose logs -f --tail=100
```

## Testing

Run the automated test script:
```bash
./test_docker.sh
```

This script will:
1. Clean up existing containers
2. Build fresh images
3. Start services in order
4. Test API and MCP endpoints
5. Show running containers and logs

## Troubleshooting

### Build Failures

1. **Playwright/Crawl4AI issues**
   - The Dockerfile runs `crawl4ai-setup` to install browsers
   - If this fails, the build continues (non-critical for API)

2. **Memory issues**
   - Increase Docker memory allocation to 4GB+
   - Reduce concurrent build jobs: `docker-compose build --parallel 1`

### Connection Issues

1. **Database connection refused**
   - Ensure PostgreSQL is healthy: `docker-compose ps`
   - Check logs: `docker-compose logs postgres`
   - Verify credentials match between services

2. **API not responding**
   - Check if port 8000 is already in use
   - View logs: `docker-compose logs api`
   - Ensure database is initialized

### Performance Issues

1. **Slow builds**
   - Use `.dockerignore` to exclude unnecessary files
   - Enable BuildKit: `export DOCKER_BUILDKIT=1`
   - Use build cache when possible

2. **Slow startup**
   - PostgreSQL needs time to initialize
   - Wait for health checks before starting dependent services

## Production Considerations

1. **Security**
   - Change default PostgreSQL password
   - Use secrets management for API keys
   - Enable HTTPS with reverse proxy

2. **Persistence**
   - Back up `postgres_data` volume regularly
   - Consider external PostgreSQL for production

3. **Scaling**
   - Use Docker Swarm or Kubernetes for multi-node
   - Implement proper load balancing
   - Consider connection pooling for PostgreSQL

## Development Workflow

1. **Local + Docker PostgreSQL**
   ```bash
   # Start only PostgreSQL in Docker
   docker-compose up -d postgres
   
   # Run API locally (uses same .env file)
   python cli.py api
   ```

2. **Full Docker Development**
   ```bash
   # Mount source code for hot reload
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
   ```

3. **Testing Changes**
   ```bash
   # Rebuild and restart specific service
   docker-compose up -d --build api
   ```