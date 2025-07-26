# Migration Guide: Unified Environment Configuration

## Overview

CodeDox now uses a single `.env` file for both local and Docker deployments, simplifying configuration management.

## Migration Steps

If you have an existing `.env.docker` file:

1. **Backup your current configuration:**
   ```bash
   cp .env.docker .env.docker.backup
   ```

2. **Create new .env from example:**
   ```bash
   cp .env.example .env
   ```

3. **Copy your API key from the old file:**
   - Old: `OPENAI_API_KEY` or `LLM_API_KEY` in `.env.docker`
   - New: `CODE_LLM_API_KEY` in `.env`

4. **Update model configuration if needed:**
   - Old: `LLM_MODEL` 
   - New: `CODE_LLM_EXTRACTION_MODEL`

5. **For local LLMs (Jan, Ollama, etc.):**
   - Old: `LLM_ENDPOINT`
   - New: `CODE_LLM_BASE_URL`

6. **Remove old files:**
   ```bash
   rm .env.docker .env.docker.backup
   ```

## Key Changes

### Environment Variable Names

| Old Variable | New Variable | Notes |
|--------------|--------------|-------|
| `OPENAI_API_KEY` | `CODE_LLM_API_KEY` | Works with any OpenAI-compatible API |
| `LLM_API_KEY` | `CODE_LLM_API_KEY` | Unified API key variable |
| `LLM_MODEL` | `CODE_LLM_EXTRACTION_MODEL` | Model name for extraction |
| `LLM_ENDPOINT` | `CODE_LLM_BASE_URL` | Base URL for custom endpoints |

### Docker Configuration

- Docker Compose now reads from `.env` instead of `.env.docker`
- `DB_HOST` is automatically overridden to `postgres` for containers
- No need to maintain separate environment files

## Example Configuration

For OpenAI:
```env
CODE_LLM_API_KEY=sk-...
CODE_LLM_EXTRACTION_MODEL=gpt-4o-mini
```

For Jan (local LLM):
```env
CODE_LLM_API_KEY=any-value
CODE_LLM_EXTRACTION_MODEL=Jan
CODE_LLM_BASE_URL=http://192.168.1.243:8001/v1
```

For Ollama:
```env
CODE_LLM_API_KEY=ollama
CODE_LLM_EXTRACTION_MODEL=llama2
CODE_LLM_BASE_URL=http://localhost:11434/v1
```