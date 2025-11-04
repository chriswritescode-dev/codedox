# Installation

## Prerequisites

- Python 3.10+
- PostgreSQL 15+
- Node.js 18+ (for web UI)

## Quick Install

### 1. Clone the repository
```bash
git clone https://github.com/chriswritescode-dev/codedox.git
cd codedox
```

### 2. Set up Python environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Install Playwright browsers (required for crawling)
playwright install
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your settings (optional - can also be configured via WebUI)
```

**Important: LLM Configuration Required for Code Extraction**

CodeDox needs LLM configuration to intelligently extract code snippets. You have two options:

**Option A: Configure via WebUI (Recommended)**
1. Start the application: `docker-compose up` or `python cli.py serve`
2. Navigate to: http://localhost:5173/settings
3. Configure LLM settings:
   - Enable LLM Extraction: `true`
   - API Key: Your OpenAI key or local LLM key
   - Base URL: Optional (for local models like LM Studio/Ollama)
   - Model: `gpt-4o-mini` or your preferred model

**Option B: Configure via .env file**
Set these values in your `.env` file:
```bash
CODE_ENABLE_LLM_EXTRACTION=true
CODE_LLM_API_KEY=sk-your-openai-key-here
CODE_LLM_EXTRACTION_MODEL=gpt-4o-mini

# For local models (LM Studio, Ollama, etc.):
# CODE_LLM_BASE_URL=http://localhost:8001/v1
# CODE_LLM_EXTRACTION_MODEL=Qwen/Qwen3-Coder-30B-A3B-Instruct
```

**Note**: WebUI settings override .env values and are saved to `config.runtime.json`. Changes apply immediately without restart.

### 4. Initialize database
```bash
python cli.py init
```

### 5. Install frontend dependencies
```bash
cd frontend
npm install
cd ..
```

## Docker Installation

```bash
docker-compose up
```

This will start all services including PostgreSQL, API server, web UI, and MCP HTTP endpoints.

## Start Services

After installation, start CodeDox with:

```bash
# Start all services (API, Web UI, MCP endpoints)
python cli.py serve

# Available endpoints:
# - Web UI: http://localhost:5173
# - API: http://localhost:8000  
# - MCP Tools: http://localhost:8000/mcp
```

For AI assistants, connect directly to the MCP endpoint at `http://localhost:8000/mcp` using Streamable HTTP transport.

## Troubleshooting

### WebUI Settings Not Applied (Docker)

If you configure LLM settings in the WebUI but they don't take effect:

1. **Ensure runtime settings volume is mounted**: The `config.runtime.json` file must be mounted in the Docker container. Check that your `docker-compose.override.yml` contains:
   ```yaml
   services:
     api:
       volumes:
         - ./config.runtime.json:/app/config.runtime.json
   ```

2. **Restart containers after adding volume mount**:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

3. **Verify settings are being read**: Check logs for:
   ```
   Added settings observer: reload_runtime_overrides
   Registered settings observer for runtime changes
   ```

### LLM Extraction Not Working

If code extraction fails or returns basic results:

1. Check that LLM extraction is enabled: `CODE_ENABLE_LLM_EXTRACTION=true`
2. Verify your API key is valid and has credits
3. Check logs for authentication errors (401 Unauthorized)
4. For local models, ensure the base URL is accessible and model name matches

### Database Connection Issues

For Docker deployments, ensure:
- Database is healthy: `docker-compose ps` should show `healthy` for postgres
- Use `DB_HOST=postgres` in Docker environment (not localhost)