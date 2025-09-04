# Web Crawling

CodeDox uses Crawl4AI for intelligent documentation crawling and supports direct GitHub repository processing.

## Features

### Web Crawling

- **Depth Control**: Crawl up to 3 levels deep
- **Domain Filtering**: Stay within documentation boundaries
- **URL Pattern Matching**: Focus on documentation pages
- **Concurrent Processing**: Speed up large crawls
- **Automatic Retries**: Handle transient failures

### GitHub Repository Processing

- **Direct Repository Clone**: Process documentation without manual download
- **Selective Processing**: Target specific folders within repositories
- **Branch Support**: Process any branch (defaults to main)
- **Private Repository Support**: Token authentication for private repos
- **Pattern Filtering**: Include/exclude files based on patterns

## Starting a Crawl

### Web Interface
Navigate to the Crawl page and click "New Crawl".

### CLI
```bash
python cli.py crawl start "Library Name" https://docs.example.com \
  --depth 2 \
  --domain example.com \
  --url-patterns "*docs*" "*guide*" \
  --concurrent 20
```

### MCP Tool
```json
{
  "name": "init_crawl",
  "arguments": {
    "name": "Next.js",
    "start_urls": ["https://nextjs.org/docs"],
    "max_depth": 2,
    "domain_filter": "nextjs.org"
  }
}
```

## Monitoring Progress

Check crawl status:
```bash
python cli.py crawl status <job-id>
```

List all crawls:
```bash
python cli.py crawl list
```

## Managing Crawls

### Cancel a Running Crawl
```bash
python cli.py crawl cancel <job-id>
```

### Resume a Failed Crawl
```bash
python cli.py crawl resume <job-id>
```

## GitHub Repository Processing

Process markdown documentation directly from GitHub repositories:

### Basic Usage
```bash
# Process entire repository
python cli.py upload-repo https://github.com/user/repo --name "Docs"

# Process specific folder
python cli.py upload-repo https://github.com/user/repo --path docs

# Process specific branch
python cli.py upload-repo https://github.com/user/repo --branch develop
```

### Private Repositories
```bash
# Using environment variable
export GITHUB_TOKEN=ghp_your_token
python cli.py upload-repo https://github.com/user/private-repo

# Using command line
python cli.py upload-repo https://github.com/user/private-repo --token ghp_token
```

### Advanced Options
```bash
# Include/exclude patterns
python cli.py upload-repo https://github.com/user/repo \
  --include "docs/**/*.md" \
  --exclude "**/test/*.md"

# Keep cloned repository
python cli.py upload-repo https://github.com/user/repo --no-cleanup
```

See the [GitHub Processing documentation](github.md) for detailed information.