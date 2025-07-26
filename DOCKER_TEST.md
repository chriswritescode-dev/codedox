# Docker Installation Test Checklist

## Prerequisites
1. Ensure `.env` is configured with your LLM API key:
   ```bash
   # Copy and edit .env:
   cp .env.example .env
   # Set CODE_LLM_API_KEY=your-actual-api-key
   # For local LLMs, also set CODE_LLM_BASE_URL
   ```

## Quick Test Commands

### 1. Build All Services
```bash
docker-compose build
```

### 2. Start Services
```bash
# Start all services
docker-compose up -d

# Or start specific services
docker-compose up -d postgres
docker-compose up -d api
docker-compose up -d frontend
```

### 3. Check Service Status
```bash
docker-compose ps
```

### 4. Initialize Database
```bash
# Run database initialization
docker-compose exec api python cli.py init
```

### 5. Test API Health
```bash
# Check API is running
curl http://localhost:8000/health

# Check MCP tools endpoint
curl http://localhost:8000/mcp/tools
```

### 6. Test Frontend
```bash
# Open in browser
open http://localhost:5173
```

### 7. Run a Test Crawl
```bash
docker-compose exec api python cli.py crawl "Test Docs" https://example.com --depth 0
```

### 8. Check Logs
```bash
# API logs
docker-compose logs -f api

# Database logs
docker-compose logs -f postgres

# All services
docker-compose logs -f
```

### 9. Access pgAdmin (Optional)
```bash
# Start with debug profile
docker-compose --profile debug up -d pgadmin

# Access at http://localhost:5050
# Login: admin@example.com / admin
# Add server: postgres:5432, user: postgres, password: postgres
```

### 10. Cleanup
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

## Troubleshooting

### If API fails to start:
1. Check `.env` has all required variables (especially CODE_LLM_API_KEY)
2. Ensure ports 8000, 5432, 5173 are not in use
3. Check logs: `docker-compose logs api`

### If database connection fails:
1. Ensure postgres is healthy: `docker-compose ps`
2. Try manual connection: `docker-compose exec postgres psql -U postgres -d codedox`

### If crawling fails:
1. Ensure Playwright browsers installed: Check build logs
2. Verify CODE_LLM_API_KEY is set in `.env`