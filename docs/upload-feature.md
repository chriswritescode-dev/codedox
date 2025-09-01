# Upload Feature Documentation

The CodeDox upload feature allows you to extract code snippets from user-uploaded documentation files (markdown, text, etc.) similar to how web crawls work.

## Features

- **Markdown Code Extraction**: Extracts code blocks from markdown files
  - Fenced code blocks (```language)
  - Indented code blocks (4 spaces/tab)
  - HTML code blocks (<pre><code>)
  
- **LLM-Powered Descriptions**: Automatically generates titles and descriptions for code blocks using AI

- **Multiple File Formats**: Support for:
  - Markdown (.md, .markdown)
  - Plain text (.txt)
  - ReStructuredText (.rst) - future
  - AsciiDoc (.adoc) - future

- **Progress Tracking**: Real-time progress updates via websockets

- **Unified Search**: Uploaded content is searchable through the same MCP tools as crawled content

## Usage

### CLI Upload

```bash
# Upload a single file
python cli.py upload /path/to/file.md

# Upload with custom name
python cli.py upload /path/to/file.md --name "My Documentation"

# Upload with source URL
python cli.py upload /path/to/file.md --source-url "https://github.com/user/repo/docs.md"
```

### API Upload

#### Upload Markdown Content

```bash
curl -X POST http://localhost:8000/upload/markdown \
  -H "Content-Type: application/json" \
  -d '{
    "content": "# Title\n\n```python\nprint(\"Hello\")\n```",
    "source_url": "https://example.com/docs",
    "title": "My Documentation"
  }'
```

#### Upload File

```bash
curl -X POST http://localhost:8000/upload/file \
  -F "file=@/path/to/file.md" \
  -F "source_url=https://example.com/docs"
```

#### Check Upload Status

```bash
curl http://localhost:8000/upload/status/{job_id}
```

## Database Schema

### Upload Jobs Table

```sql
CREATE TABLE upload_jobs (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    source_type VARCHAR(20) DEFAULT 'upload',
    file_count INTEGER DEFAULT 0,
    status VARCHAR(20),
    processed_files INTEGER DEFAULT 0,
    snippets_extracted INTEGER DEFAULT 0,
    -- ... other fields
);
```

### Documents Table Updates

- Added `upload_job_id` column to link documents to upload jobs
- Added `source_type` column to distinguish between crawled and uploaded content
- Constraint ensures documents are linked to either crawl_job or upload_job

## Architecture

### Components

1. **MarkdownCodeExtractor**: Extracts code blocks from markdown content
   - Uses regex patterns for different code block formats
   - Extracts surrounding context for better descriptions

2. **UploadProcessor**: Manages the upload job lifecycle
   - Creates upload jobs in database
   - Processes files asynchronously
   - Tracks progress and updates job status

3. **ResultProcessor**: Stores extracted code in database
   - Reused from crawl pipeline for consistency
   - Handles code formatting and deduplication

### Processing Flow

1. User uploads file via CLI or API
2. UploadProcessor creates job and starts async processing
3. MarkdownCodeExtractor extracts code blocks with context
4. LLMDescriptionGenerator generates titles/descriptions
5. ResultProcessor stores snippets in database
6. Job status updated to completed

## Migration

To add upload support to an existing installation:

```bash
# Run the migration
psql -d codedox -f migrations/add_upload_support.sql

# Or use the init command with --drop (WARNING: drops all data)
python cli.py init --drop
```

## Testing

```bash
# Test markdown extraction
python -c "
from src.crawler import MarkdownCodeExtractor
extractor = MarkdownCodeExtractor()
content = open('tests/fixtures/test_upload.md').read()
blocks = extractor.extract_code_blocks(content, 'test.md')
print(f'Found {len(blocks)} code blocks')
"

# Test upload via CLI
python cli.py upload tests/fixtures/test_upload.md --name "Test Upload"

# Search uploaded content
python cli.py search "hello world"
```