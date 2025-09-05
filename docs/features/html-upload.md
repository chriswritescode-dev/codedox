# HTML File Upload Support

CodeDox now supports uploading and processing HTML documentation files in addition to Markdown files. This feature allows you to extract code snippets from HTML documentation, making it useful for processing generated documentation or HTML-based API references.

## Features

### 1. HTML File Upload

- Upload single or multiple HTML files via the API
- Automatic detection of `.html` and `.htm` file extensions
- HTML content is converted to Markdown for storage
- Code blocks are extracted from `<pre><code>` tags

### 2. GitHub Repository Support

- GitHub processor now discovers and processes HTML files
- Supports mixed repositories with both Markdown and HTML documentation
- Preserves source URLs for GitHub-hosted HTML files

### 3. Code Extraction

- Extracts code blocks from HTML `<pre><code>` elements
- Preserves language information from `class="language-*"` attributes
- Maintains code formatting and indentation
- Supports both LLM-enhanced and basic extraction modes

## API Usage

### Upload Single HTML File

```bash
curl -X POST http://localhost:8000/upload/file \
  -F "file=@documentation.html" \
  -F "name=MyProject Docs"
```

### Upload Multiple Files (HTML + Markdown)

```bash
curl -X POST http://localhost:8000/upload/files \
  -F "files=@api.html" \
  -F "files=@readme.md" \
  -F "files=@guide.html" \
  -F "name=Project Documentation"
```

### Process GitHub Repository with HTML

```bash
curl -X POST http://localhost:8000/github/process \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/user/repo",
    "name": "My Project",
    "branch": "main"
  }'
```

## Supported HTML Structure

CodeDox extracts code from standard HTML code block structures:

```html
<pre><code class="language-python">
def example():
    return "Hello, World!"
</code></pre>
```

### Processing Pipeline

1. **File Upload**: HTML file is uploaded via API
2. **Content Type Detection**: System identifies HTML files by extension
3. **HTML Parsing**: BeautifulSoup parses the HTML structure
4. **Metadata Extraction**: Title and meta tags are extracted
5. **Markdown Conversion**: HTML content is converted to Markdown
6. **Code Extraction**: Code blocks are extracted from `<pre><code>` tags
7. **Storage**: Document and code snippets are stored in PostgreSQL

