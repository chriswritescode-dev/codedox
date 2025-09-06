"""Comprehensive test for code extraction from both markdown and HTML."""

import pytest

from src.api.routes.upload_utils import MarkdownCodeExtractor
from src.crawler.html_code_extractor import HTMLCodeExtractor


class TestComprehensiveCodeExtraction:
    """Test comprehensive code extraction for both markdown and HTML."""

    def test_markdown_extraction_all_formats(self):
        """Test markdown extraction handles all CommonMark code block formats."""
        markdown_content = """
# Test Document

## Fenced Code Block with Language
```python
def hello():
    print("Hello, World!")
```

## Fenced Code Block without Language
```
plain text code
without language
```

## Indented Code Block (4 spaces)
Here's an indented code block:

    function greet() {
        console.log("Hello!");
    }

## Indented Code Block (tabs)
Using tabs for indentation:

	def tabbed_function():
	    return "Using tabs"

## Indented Code Block with Blank Lines
Code with blank lines preserved:

    #include <stdio.h>
    
    int main() {
        printf("Hello\\n");
        return 0;
    }

## Mixed Content
Regular paragraph before code.

    indented_code()
    more_code()

Regular paragraph after code.
"""
        extractor = MarkdownCodeExtractor()
        blocks = extractor.extract_code_blocks(markdown_content)
        
        # Should find all 6 code blocks
        assert len(blocks) == 6
        
        # Check fenced blocks have language info
        python_block = next(b for b in blocks if 'def hello' in b['content'])
        assert python_block['language'] == 'python'
        assert python_block['type'] == 'fenced'
        
        # Check indented blocks have no language
        indent_blocks = [b for b in blocks if b['type'] == 'indented']
        assert len(indent_blocks) == 4
        for block in indent_blocks:
            assert block['language'] is None
        

        
        # Check blank lines preserved in indented block
        c_block = next(b for b in blocks if '#include' in b['content'])
        assert '\n\n' in c_block['content']  # Blank line preserved (actual newlines, not escaped)

    def test_html_extraction_no_duplicates(self):
        """Test HTML extraction doesn't produce duplicates from nested pre/code."""
        html_content = """
        <html>
        <body>
            <!-- Common pattern: pre > code -->
            <pre><code class="language-python">
def example1():
    return "first"
            </code></pre>
            
            <!-- Standalone pre -->
            <pre>
function example2() {
    return "second";
}
            </pre>
            
            <!-- Standalone code block (multi-line) -->
            <code>// Multi-line code block
const inline = "code";
return inline;</code>
            
            <!-- Another pre > code -->
            <pre><code>
// No language class
void example3() {}
            </code></pre>
        </body>
        </html>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_code_blocks(html_content, "test.html")
        
        # Should find exactly 4 blocks, no duplicates
        assert len(blocks) == 4
        
        # Verify each block is unique
        contents = [block.code.strip() for block in blocks]
        assert len(contents) == len(set(contents))  # No duplicate content
        
        # Check we got the expected blocks
        assert any('example1' in c for c in contents)
        assert any('example2' in c for c in contents)
        assert any('const inline' in c for c in contents)
        assert any('example3' in c for c in contents)

    def test_markdown_edge_cases(self):
        """Test edge cases in markdown extraction."""
        # Test empty code blocks
        content_empty = """
```
```

    
    """
        extractor = MarkdownCodeExtractor()
        blocks = extractor.extract_code_blocks(content_empty)
        assert len(blocks) == 0  # Empty blocks are filtered out
        
        # Test unclosed fence (extracts until end of content)
        content_unclosed = """
```python
def unclosed():
    pass
"""
        blocks = extractor.extract_code_blocks(content_unclosed)
        assert len(blocks) == 1  # Unclosed fence extracted until EOF
        assert 'unclosed' in blocks[0]['content']
        
        # Test insufficient indentation (not valid indented block)
        content_mixed = """
  def mixed():  # Only 2 spaces
  pass         # Only 2 spaces
"""
        blocks = extractor.extract_code_blocks(content_mixed)
        assert len(blocks) == 0  # Less than 4 spaces/tab not extracted