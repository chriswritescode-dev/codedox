# Upload Feature Documentation

The CodeDox upload feature allows you to extract code snippets from user-uploaded documentation files (markdown, text, etc.) and GitHub repositories, similar to how web crawls work. This includes both local file uploads and direct processing of GitHub repositories.

## Features

### Markdown Code Extraction

Extracts code blocks from markdown files:

- Fenced code blocks (```language)
- Indented code blocks (4 spaces/tab)
- HTML code blocks (`<pre><code>`)

### GitHub Repository Support

Clone and process markdown documentation from GitHub repos:

- Clone entire repositories or specific folders
- Support for private repositories with token authentication
- Automatic cleanup after processing
- Include/exclude file patterns

### LLM-Powered Descriptions

Automatically generates titles and descriptions for code blocks using AI.

### Multiple File Formats

Support for:

- Markdown (.md, .markdown)
- Plain text (.txt)
- ReStructuredText (.rst) - future
- AsciiDoc (.adoc) - future

### Progress Tracking

Real-time progress updates via websockets.

### Unified Search

Uploaded content is searchable through the same MCP tools as crawled content.

## Usage

### CLI Upload

#### Upload Single File

```bash
# Upload a single file
python cli.py upload /path/to/file.md

# Upload with custom name
python cli.py upload /path/to/file.md --name "My Documentation"

# Upload with source URL
python cli.py upload /path/to/file.md --source-url "https://github.com/user/repo/docs.md"
```

#### Upload GitHub Repository

```bash
# Upload entire repository
python cli.py upload-repo https://github.com/user/repo

# Upload specific folder in repository
python cli.py upload-repo https://github.com/user/repo --path docs

# Upload with custom name
python cli.py upload-repo https://github.com/user/repo --name "My Project Docs"

# Upload specific branch
python cli.py upload-repo https://github.com/user/repo --branch develop

# Upload private repository with token
export GITHUB_TOKEN=ghp_your_token_here
python cli.py upload-repo https://github.com/user/private-repo

# Or pass token directly
python cli.py upload-repo https://github.com/user/private-repo --token ghp_your_token

# Include/exclude patterns
python cli.py upload-repo https://github.com/user/repo \
  --include "docs/**/*.md" \
  --include "examples/**/*.md" \
  --exclude "**/test/*.md"

# Keep cloned repository after processing
python cli.py upload-repo https://github.com/user/repo --no-cleanup
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

#### Upload GitHub Repository

```bash
# Upload entire repository
curl -X POST http://localhost:8000/upload/github \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/user/repo",
    "name": "My Project Documentation"
  }'

# Upload specific folder with authentication
curl -X POST http://localhost:8000/upload/github \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/user/repo",
    "path": "docs",
    "branch": "main",
    "token": "ghp_your_token_here",
    "include_patterns": ["**/*.md"],
    "exclude_patterns": ["**/test/*.md"]
  }'
```

#### Check Upload Status

```bash
# Check regular upload status
curl http://localhost:8000/upload/status/{job_id}

# Check GitHub repository upload status
curl http://localhost:8000/upload/github/status/{job_id}
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

3. **GitHubProcessor**: Handles GitHub repository cloning and processing
   - Clones repositories to temporary directories
   - Supports sparse checkout for specific paths
   - Handles authentication for private repositories
   - Automatic cleanup after processing
   - File pattern filtering (include/exclude)

4. **ResultProcessor**: Stores extracted code in database
   - Reused from crawl pipeline for consistency
   - Handles code formatting and deduplication

### Processing Flow

#### File Upload Flow
1. User uploads file via CLI or API
2. UploadProcessor creates job and starts async processing
3. MarkdownCodeExtractor extracts code blocks with context
4. LLMDescriptionGenerator generates titles/descriptions
5. ResultProcessor stores snippets in database
6. Job status updated to completed

#### GitHub Repository Flow
1. User provides repository URL and optional path
2. GitHubProcessor clones repository to temporary directory
3. Searches for markdown files based on patterns
4. Processes each markdown file through UploadProcessor
5. Generates source URLs pointing to GitHub blob URLs
6. Cleans up temporary directory after completion

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