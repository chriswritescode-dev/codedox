# Code Extraction

CodeDox supports both LLM-powered and traditional extraction methods to identify and extract code snippets from documentation.

## How It Works

### LLM Extraction (Recommended)
1. **Content Cleaning**: Crawl4AI removes navigation, ads, and irrelevant content
2. **LLM Analysis**: AI analyzes the content for code blocks
3. **Metadata Extraction**: Automatically detects:
   - Programming language
   - Code purpose and description
   - Related dependencies
   - Framework context

### Traditional Extraction (Non-LLM)
CodeDox also supports basic extraction without LLMs:
1. **Content Cleaning**: Crawl4AI removes navigation, ads, and irrelevant content
2. **Pattern Matching**: Uses syntax highlighting and code block detection
3. **Basic Metadata**: Extracts language and basic structure information

**Note**: While traditional extraction works without LLMs, LLM extraction provides significantly more detailed titles, descriptions, and contextual understanding of the code.

## Configuration

### Local Models (Free - Recommended)
For cost-free extraction, use local models via Ollama or LM Studio:

```bash
# Using Ollama
# Configure in .env
CODE_LLM_API_KEY=ollama
CODE_LLM_PROVIDER=ollama
CODE_LLM_EXTRACTION_MODEL=Qwen3-Coder-30B-A3B-Instruct
CODE_LLM_BASE_URL=http://localhost:11434/v1
```

### Recommended Local Models
- **Qwen3-Coder-30B-A3B-Instruct**: Excellent code understanding (best results)
- **Qwen3-4B-Instruct-2507**: Lightweight but effective

### Cloud Models
For OpenAI or other cloud providers:
```bash
CODE_LLM_API_KEY=sk-...
CODE_LLM_PROVIDER=openai  # or anthropic, groq
CODE_LLM_EXTRACTION_MODEL=gpt-4o-mini  # Fast and affordable
```


## Cost Optimization

- **Content Hash Deduplication**: Skips LLM calls for unchanged content during re-crawls
- **Local Models**: Zero API costs with excellent results using Qwen3 2507 non thinking models

## Manual Upload

You can also upload markdown files directly:
```bash
python cli.py upload ./docs.md --name "My Library"
```
