# GitHub Repository Processing

CodeDox can directly process markdown documentation from GitHub repositories without manual downloading. This feature allows you to extract code snippets from entire repositories or specific folders.

## Overview

The GitHub processor:

- Clones repositories efficiently using shallow cloning
- Processes all markdown files in the repository
- Extracts code blocks with intelligent context
- Generates source URLs for each file
- Supports both public and private repositories
- Automatically cleans up temporary files

## Key Features

### Repository Cloning

- **Shallow Cloning**: Only fetches the latest commit for efficiency
- **Sparse Checkout**: Can clone specific folders to save bandwidth
- **Branch Selection**: Process any branch (defaults to main)
- **Token Authentication**: Support for private repositories

### File Processing

- **Markdown Detection**: Automatically finds all markdown files (.md, .markdown, .mdx, .mdown, .mkd, .mdwn)
- **Pattern Filtering**: Include or exclude files based on glob patterns
- **Smart Exclusion**: Automatically skips common non-documentation folders (node_modules, .git, vendor, etc.)
- **Source URL Generation**: Creates GitHub blob URLs for each processed file

### Integration

- **Unified Search**: GitHub-sourced content is searchable alongside crawled documentation
- **Progress Tracking**: Real-time updates during processing
- **LLM Enhancement**: Optional AI-powered code understanding

## Usage

### Command Line Interface

#### Basic Usage

```bash
# Process entire repository
python cli.py upload-repo https://github.com/user/repo

# Process with custom name
python cli.py upload-repo https://github.com/user/repo --name "Project Docs"

# Process specific branch
python cli.py upload-repo https://github.com/user/repo --branch develop
```

#### Advanced Options

```bash
# Process specific folder
python cli.py upload-repo https://github.com/user/repo --path docs

# Include specific patterns
python cli.py upload-repo https://github.com/user/repo \
  --include "docs/**/*.md" \
  --include "examples/**/*.md"

# Exclude patterns
python cli.py upload-repo https://github.com/user/repo \
  --exclude "**/test/*.md" \
  --exclude "**/node_modules/**"

# Keep cloned repository (don't cleanup)
python cli.py upload-repo https://github.com/user/repo --no-cleanup
```

#### Private Repositories

```bash
# Using environment variable
export GITHUB_TOKEN=ghp_your_token_here
python cli.py upload-repo https://github.com/user/private-repo

# Using command line option
python cli.py upload-repo https://github.com/user/private-repo \
  --token ghp_your_token_here
```

### API Endpoint

The GitHub processor is integrated with the upload system and uses the same job tracking:

```bash
# Check job status
curl http://localhost:8000/crawl/status/<job-id>

# List all jobs
curl http://localhost:8000/crawl/list
```

### Web Interface

GitHub repository processing is integrated into the Upload page:

1. Navigate to the Upload section
2. Select "GitHub Repository" tab
3. Enter repository URL
4. Configure options (branch, path, patterns)
5. Click "Process Repository"

## Configuration

### Environment Variables

```bash
# GitHub personal access token for private repos
GITHUB_TOKEN=ghp_your_token_here

# LLM settings for code extraction
CODE_LLM_API_KEY=your-api-key
CODE_LLM_EXTRACTION_MODEL=gpt-4o-mini
```

### Default Exclusions

The following directories are automatically excluded:

- `node_modules`
- `.git`
- `.github`
- `vendor`
- `dist`
- `build`
- `target`
- `.tox`
- `.pytest_cache`
- `__pycache__`

## Examples

### Process Documentation Repository

```bash
# Process React documentation
python cli.py upload-repo https://github.com/facebook/react \
  --path docs \
  --name "React Documentation"

# Process Next.js examples
python cli.py upload-repo https://github.com/vercel/next.js \
  --path examples \
  --include "**/*.md" \
  --name "Next.js Examples"
```

### Process Private Company Docs

```bash
# With token authentication
export GITHUB_TOKEN=ghp_your_token
python cli.py upload-repo https://github.com/company/internal-docs \
  --name "Internal Documentation" \
  --branch main
```

### Process Multiple Versions

```bash
# Process different versions from branches
python cli.py upload-repo https://github.com/user/project \
  --branch v1.0 \
  --name "Project v1.0 Docs"

python cli.py upload-repo https://github.com/user/project \
  --branch v2.0 \
  --name "Project v2.0 Docs"
```

## How It Works

### Processing Pipeline

1. **Repository Cloning**
   - Creates temporary directory
   - Performs shallow clone with depth=1
   - Optionally checks out specific branch
   - Applies sparse checkout if path specified

2. **File Discovery**
   - Walks repository directory tree
   - Identifies markdown files by extension
   - Applies include/exclude patterns
   - Skips default excluded directories

3. **Content Extraction**
   - Reads each markdown file
   - Generates GitHub blob URL for source tracking
   - Extracts code blocks using markdown parser
   - Optionally enhances with LLM analysis

4. **Storage**
   - Creates source record in database
   - Stores extracted code snippets
   - Maintains source URLs for reference
   - Updates search indexes

5. **Cleanup**
   - Removes temporary clone directory
   - Reports processing statistics
   - Returns job ID for tracking

### Source URL Generation

For each file, CodeDox generates the appropriate GitHub URL:

```
https://github.com/{owner}/{repo}/blob/{branch}/{path}
```

This allows users to navigate back to the original documentation.

## Performance Considerations

### Optimization Tips

- **Use Specific Paths**: Clone only the documentation folder instead of the entire repository
- **Apply Patterns**: Use include/exclude patterns to process only relevant files
- **Shallow Cloning**: Default shallow clone reduces download time
- **Concurrent Processing**: Multiple files are processed in parallel

### Resource Usage

- **Disk Space**: Temporary clone requires space (automatically cleaned up)
- **Network**: Initial clone bandwidth depends on repository size
- **Processing Time**: Depends on number of markdown files and LLM usage

## Limitations

### Current Limitations

- Only processes markdown files (not source code files directly)
- Requires git to be installed on the system
- Maximum repository size limited by available disk space
- Rate limiting applies when using GitHub API

### Planned Enhancements

- Support for other version control systems (GitLab, Bitbucket)
- Direct source code file processing
- Incremental updates (only process changes)
- Webhook integration for automatic updates

## Troubleshooting

### Common Issues

#### Authentication Failed

```
Error: Failed to clone repository: authentication failed
```

**Solution**: Ensure your GitHub token has the necessary permissions:

- For public repos: No token needed
- For private repos: Token needs `repo` scope

#### Path Not Found

```
Error: Path 'docs' not found in repository
```

**Solution**: Verify the path exists in the repository and matches the branch

#### No Markdown Files Found

```
Error: No markdown files found in repository
```

**Solution**: Check that the repository contains markdown files and adjust include patterns

### Debug Mode

Enable debug logging to see detailed processing information:

```bash
# Set log level
export LOG_LEVEL=DEBUG
python cli.py upload-repo https://github.com/user/repo
```

## Best Practices

### Repository Selection

- **Documentation-First Repos**: Best results with dedicated documentation repositories
- **Monorepos**: Use `--path` to target documentation folders
- **Version Control**: Process specific branches for version-specific documentation

### Pattern Usage

- **Be Specific**: Use precise patterns to avoid processing irrelevant files
- **Test Patterns**: Use `--no-cleanup` to inspect which files would be processed
- **Combine Patterns**: Use multiple include/exclude patterns for fine control

### Performance

- **Batch Processing**: Process multiple repositories in sequence rather than parallel
- **Off-Peak Hours**: Run large processing jobs during low-usage periods
- **Monitor Progress**: Use job status endpoint to track processing

## Integration with MCP Tools

Once processed, GitHub repository content is accessible through MCP tools:

```python
# Search for content from GitHub sources
{
  "tool": "get_content",
  "arguments": {
    "library_id": "project-docs",
    "query": "authentication"
  }
}

# Get full markdown from GitHub source
{
  "tool": "get_page_markdown",
  "arguments": {
    "url": "https://github.com/user/repo/blob/main/docs/guide.md"
  }
}
```

## See Also

- [Upload Feature Documentation](../upload-feature.md) - General upload functionality
- [Code Extraction](extraction.md) - How code blocks are processed
- [Search Features](search.md) - Finding processed content
- [MCP Integration](mcp.md) - Using content with AI assistants