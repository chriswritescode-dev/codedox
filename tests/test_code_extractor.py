"""Tests for the enhanced code extractor."""

import pytest
from pathlib import Path
from src.parser.code_extractor import CodeExtractor, CodeBlock


class TestCodeExtractor:
    """Test the code extractor with various formats."""
    
    @pytest.fixture
    def extractor(self):
        """Create a code extractor instance."""
        return CodeExtractor(
            context_chars=200,
            min_code_lines=1,  # Allow single-line code
            use_tree_sitter=False  # Disable for basic tests
        )
    
    @pytest.fixture
    def markdown_content(self):
        """Load markdown test fixture."""
        fixture_path = Path(__file__).parent / "fixtures" / "code_blocks.md"
        return fixture_path.read_text()
    
    @pytest.fixture
    def html_content(self):
        """Load HTML test fixture."""
        fixture_path = Path(__file__).parent / "fixtures" / "code_blocks.html"
        return fixture_path.read_text()
    
    def test_standard_markdown_fence(self, extractor):
        """Test extraction of standard markdown fenced code blocks."""
        content = '''
# Example
```python
def hello_world():
    print("Hello, World!")
    return 42
```
'''
        blocks = extractor.extract_from_content(content, "test.md", "markdown")
        
        assert len(blocks) == 1
        block = blocks[0]
        assert block.language == "python"
        assert block.content == 'def hello_world():\n    print("Hello, World!")\n    return 42'
        assert "    " in block.content  # Verify indentation preserved
    
    def test_fence_with_trailing_copy(self, extractor):
        """Test that trailing 'Copy' button text is ignored."""
        content = '''
```javascript
const greeting = (name) => {
    console.log(`Hello, ${name}!`);
};
```Copy
'''
        blocks = extractor.extract_from_content(content, "test.md", "markdown")
        
        assert len(blocks) == 1
        assert blocks[0].content == 'const greeting = (name) => {\n    console.log(`Hello, ${name}!`);\n};'
        assert "Copy" not in blocks[0].content
    
    def test_alternative_fence_tildes(self, extractor):
        """Test extraction with tilde fences."""
        content = '''
~~~ruby
class Person
  def initialize(name)
    @name = name
  end
end
~~~
'''
        blocks = extractor.extract_from_content(content, "test.md", "markdown")
        
        assert len(blocks) == 1
        assert blocks[0].language == "ruby"
        assert "  def initialize" in blocks[0].content  # Ruby typically uses 2-space indent
    
    def test_fence_with_metadata(self, extractor):
        """Test extraction of code blocks with metadata."""
        content = '''
```typescript title="src/utils/helper.ts"
export function debounce<T>(func: T): T {
  return func;
}
```
'''
        blocks = extractor.extract_from_content(content, "test.md", "markdown")
        
        assert len(blocks) == 1
        block = blocks[0]
        assert block.language == "typescript"
        assert block.title == "src/utils/helper.ts"
        assert "export function" in block.content
    
    def test_docusaurus_format(self, extractor):
        """Test Docusaurus-style code blocks."""
        content = '''
:::code python
def greet(name):
    return f"Hello, {name}!"
:::
'''
        blocks = extractor.extract_from_content(content, "test.md", "markdown")
        
        assert len(blocks) == 1
        assert blocks[0].language == "python"
        assert blocks[0].content == 'def greet(name):\n    return f"Hello, {name}!"'
    
    def test_whitespace_preservation(self, extractor):
        """Test that whitespace is preserved exactly."""
        content = '''
```python

def has_empty_lines():
    """This function has empty lines above and below"""
    pass

```
'''
        blocks = extractor.extract_from_content(content, "test.md", "markdown")
        
        assert len(blocks) == 1
        # Should start and end with newlines
        assert blocks[0].content.startswith('\n')
        assert blocks[0].content.endswith('\n')
        assert '"""This function has empty lines above and below"""' in blocks[0].content
    
    def test_mixed_indentation(self, extractor):
        """Test preservation of mixed tabs and spaces."""
        content = '''
```python
def mixed_indent():
	if True:  # This line uses a tab
        print("This uses spaces")  # This line uses spaces
	    print("Mixed!")  # This has tab + spaces
```
'''
        blocks = extractor.extract_from_content(content, "test.md", "markdown")
        
        assert len(blocks) == 1
        # Verify tabs are preserved
        assert '\t' in blocks[0].content
        assert '\tif True:' in blocks[0].content
        assert '        print("This uses spaces")' in blocks[0].content
    
    def test_single_line_code(self, extractor):
        """Test that valid single-line code is accepted."""
        content = '''
```python
print("This is valid single-line code")
```

```javascript
import { useState, useEffect } from 'react';
```
'''
        blocks = extractor.extract_from_content(content, "test.md", "markdown")
        
        assert len(blocks) == 2
        assert blocks[0].content == 'print("This is valid single-line code")'
        assert blocks[1].content == "import { useState, useEffect } from 'react';"
    
    def test_empty_code_block(self, extractor):
        """Test handling of empty code blocks."""
        content = '''
```python
```

```

```
'''
        blocks = extractor.extract_from_content(content, "test.md", "markdown")
        
        # Empty blocks should be filtered out
        assert len(blocks) == 0
    
    def test_html_pre_code(self, extractor):
        """Test extraction from HTML pre/code tags."""
        content = '''
<pre><code class="language-python">def standard_format():
    """This is the most common format"""
    return "pre > code"</code></pre>
'''
        blocks = extractor.extract_from_content(content, "test.html", "html")
        
        assert len(blocks) == 1
        assert blocks[0].language == "python"
        assert blocks[0].content == 'def standard_format():\n    """This is the most common format"""\n    return "pre > code"'
    
    def test_html_pre_only(self, extractor):
        """Test extraction from pre tag without nested code."""
        content = '''
<pre class="language-javascript">
function preOnly() {
    // Some docs use pre without nested code
    console.log("No code tag");
}</pre>
'''
        blocks = extractor.extract_from_content(content, "test.html", "html")
        
        assert len(blocks) == 1
        assert blocks[0].language == "javascript"
        assert "// Some docs use pre without nested code" in blocks[0].content
    
    def test_html_entities(self, extractor):
        """Test that HTML entities are properly decoded."""
        content = '''
<pre><code class="language-html">&lt;div class="container"&gt;
    &lt;p&gt;HTML entities: &amp;amp; &amp;lt; &amp;gt; &amp;quot; &amp;apos;&lt;/p&gt;
&lt;/div&gt;</code></pre>
'''
        blocks = extractor.extract_from_content(content, "test.html", "html")
        
        assert len(blocks) == 1
        # Entities should be decoded
        assert '<div class="container">' in blocks[0].content
        assert '<p>HTML entities: &amp; &lt; &gt; &quot; &apos;</p>' in blocks[0].content
    
    def test_custom_components(self, extractor):
        """Test extraction from custom HTML components."""
        content = '''
<CodeBlock language="jsx">
function Component() {
    return <div>Custom component</div>;
}
</CodeBlock>
'''
        blocks = extractor.extract_from_content(content, "test.html", "html")
        
        assert len(blocks) == 1
        assert blocks[0].language == "jsx"
        # HTML entities are decoded during extraction
        assert "return Custom component;" in blocks[0].content or "return <div>Custom component</div>;" in blocks[0].content
    
    def test_unicode_and_emoji(self, extractor):
        """Test preservation of Unicode and emojis."""
        content = '''
```python
def print_emoji():
    print("Hello 👋 World 🌍!")
    japanese = "こんにちは"
    return "🚀"
```
'''
        blocks = extractor.extract_from_content(content, "test.md", "markdown")
        
        assert len(blocks) == 1
        assert "👋" in blocks[0].content
        assert "🌍" in blocks[0].content
        assert "こんにちは" in blocks[0].content
        assert "🚀" in blocks[0].content
    
    def test_language_detection_unknown(self, extractor):
        """Test that unknown language doesn't prevent extraction."""
        content = '''
```
plain text code block
with multiple lines
```
'''
        blocks = extractor.extract_from_content(content, "test.md", "markdown")
        
        assert len(blocks) == 1
        assert blocks[0].language == "unknown"
        assert blocks[0].content == "plain text code block\nwith multiple lines"
    
    def test_no_duplicate_extraction(self, extractor):
        """Test that the same code block isn't extracted multiple times."""
        content = '''
```python
def duplicate_test():
    return "same"
```

```python
def duplicate_test():
    return "same"
```

```python
def different():
    return "different"
```
'''
        blocks = extractor.extract_from_content(content, "test.md", "markdown")
        
        # Should have 2 blocks (duplicates removed based on hash)
        assert len(blocks) == 2
        contents = [b.content for b in blocks]
        assert 'def duplicate_test():\n    return "same"' in contents
        assert 'def different():\n    return "different"' in contents
    
    def test_context_extraction(self, extractor):
        """Test that context is extracted correctly."""
        content = '''
This is the context before the code block.
It explains what the code does.

```python
def example():
    pass
```

This is the context after.
It provides additional information.
'''
        blocks = extractor.extract_from_content(content, "test.md", "markdown")
        
        assert len(blocks) == 1
        block = blocks[0]
        assert "explains what the code does" in block.context_before
        assert "provides additional information" in block.context_after
        
    def test_extraction_metadata(self, extractor):
        """Test that extraction metadata is properly set."""
        content = '''
```python {highlight: [2]}
def test():
    return True  # highlighted
```
'''
        blocks = extractor.extract_from_content(content, "test.md", "markdown")
        
        assert len(blocks) == 1
        assert blocks[0].extraction_metadata['format'] == 'markdown_fenced'
        assert '{highlight: [2]}' in blocks[0].extraction_metadata['metadata']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])