# Web Crawling

CodeDox uses Crawl4AI for intelligent documentation crawling.

## Features

- **Depth Control**: Crawl up to 3 levels deep
- **Domain Filtering**: Stay within documentation boundaries
- **URL Pattern Matching**: Focus on documentation pages
- **Concurrent Processing**: Speed up large crawls
- **Automatic Retries**: Handle transient failures

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