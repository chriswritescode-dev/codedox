# Search

CodeDox provides lightning-fast code search using PostgreSQL full-text search.

## Search Features

- **Full-Text Search**: PostgreSQL's powerful text search with weighted fields
- **Fuzzy Matching**: Finds similar terms using pg_trgm extension
- **Language Filtering**: Search within specific programming languages
- **Source Filtering**: Limit search to specific documentation sources

## Search Interfaces

### Web UI
Use the search bar on the dashboard or dedicated search page.

### CLI
```bash
python cli.py search "authentication middleware" --limit 10
python cli.py search "useState hook" --source "React"
```

### MCP Tool
```json
{
  "name": "get_content",
  "arguments": {
    "library_id": "library-id",
    "query": "authentication",
    "max_results": 10
  }
}
```

## Search Ranking

Results are ranked by relevance using weighted fields:
1. **Title** (weight: A) - Highest priority
2. **Description** (weight: B) - Medium priority  
3. **Code** (weight: C) - Lower priority

## Performance

- Sub-100ms response times
- Indexes on search_vector for fast queries
- Optimized for code search patterns