"""Tests for MarkdownCodeExtractor."""

import pytest

from src.crawler.extractors.markdown import MarkdownCodeExtractor


class TestMarkdownCodeExtractor:
    """Test the MarkdownCodeExtractor."""
    
    def test_extract_fenced_code_block(self):
        """Test extraction of fenced code blocks."""
        content = """
# Setting Up

To set up your project, run:

```python
import os
import sys

def setup():
    print("Setting up...")
```

This will initialize everything.
"""
        extractor = MarkdownCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        assert blocks[0].code.strip() == 'import os\nimport sys\n\ndef setup():\n    print("Setting up...")'
        assert blocks[0].language == 'python'
        assert blocks[0].context.title == 'Setting Up'
        assert 'To set up your project, run:' in blocks[0].context.description
    
    def test_skip_single_line_code(self):
        """Test that single-line code blocks are skipped."""
        content = """
# Configuration

Use the `config.json` file or run `npm install`.

```bash
echo "hello"
```

The inline code `useState()` is not extracted.
"""
        extractor = MarkdownCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        # Only the bash block should be extracted (it's multi-line internally)
        assert len(blocks) == 0  # Single line "echo hello" should be skipped
    
    def test_extract_multi_line_code(self):
        """Test extraction of multi-line code blocks."""
        content = """
# Database Setup

Initialize your database:

```sql
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(100)
);
```

This creates the users table.
"""
        extractor = MarkdownCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        assert 'CREATE TABLE users' in blocks[0].code
        assert blocks[0].language == 'sql'
        assert blocks[0].context.title == 'Database Setup'
    
    def test_indented_code_blocks(self):
        """Test extraction of indented code blocks."""
        content = """
# Example

Here's an indented code block:

    def hello():
        return "world"
    
    print(hello())

That was the example.
"""
        extractor = MarkdownCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        assert 'def hello():' in blocks[0].code
        assert blocks[0].language is None  # Indented blocks don't have language
    
    def test_multiple_code_blocks_under_same_heading(self):
        """Test multiple code blocks under the same heading."""
        content = """
# Setup Guide

First, install dependencies:

```bash
npm install express
npm install mongoose
```

Then, create your server:

```javascript
const express = require('express');
const app = express();

app.listen(3000);
```

Finally, run it.
"""
        extractor = MarkdownCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 2
        assert blocks[0].language == 'bash'
        assert blocks[1].language == 'javascript'
        
        # First block should have description about installing
        assert 'install dependencies' in blocks[0].context.description
        
        # Second block should have description about creating server
        assert 'create your server' in blocks[1].context.description
    
    def test_filter_markdown_noise(self):
        """Test that markdown links and images are filtered."""
        content = """
# Documentation

Check the [API docs](https://example.com) and ![logo](logo.png).

```python
def api_call():
    return "result"
```

See more at [GitHub](https://github.com).
"""
        extractor = MarkdownCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        desc = blocks[0].context.description
        
        # Links should be removed but text preserved
        assert 'API docs' in desc
        assert 'https://example.com' not in desc
        assert 'logo.png' not in desc
    
    def test_setext_headings(self):
        """Test Setext-style headings (underlined)."""
        content = """
Main Title
==========

This is under the main title.

```python
def code_here():
    return "test"
```

Subtitle
--------

More content here.
"""
        extractor = MarkdownCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        assert blocks[0].context.title == 'Main Title'
        assert 'under the main title' in blocks[0].context.description
    
    def test_frontmatter_removal(self):
        """Test that frontmatter is removed."""
        content = """---
title: My Page
author: John
---

# Actual Content

Here's the code:

```python
print("hello")
print("world")
```
"""
        extractor = MarkdownCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        assert blocks[0].context.title == 'Actual Content'