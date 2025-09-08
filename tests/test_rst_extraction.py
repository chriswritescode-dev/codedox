"""Tests for RST code extraction functionality."""

import pytest

from src.api.routes.upload_utils import extract_code_blocks_by_type
from src.crawler.extractors.rst import RSTCodeExtractor
from src.crawler.extractors.models import ExtractedCodeBlock


class TestRSTCodeExtractor:
    """Test RST code extraction."""
    
    @pytest.fixture
    def rst_code_block_python(self):
        """Sample RST content with Python code block."""
        return """
Some text before.

.. code-block:: python

    def hello_world():
        print("Hello, World!")
        return True

Some text after.
        """
    
    @pytest.fixture
    def rst_code_javascript(self):
        """Sample RST content with JavaScript code directive."""
        return """
.. code:: javascript

    const greeting = "Hello";
    console.log(greeting);
        """
    
    @pytest.fixture
    def rst_literal_block(self):
        """Sample RST content with literal block."""
        return """
Here is a literal block::

    This is literal text
    It preserves    spacing
    And line breaks
        """
    
    @pytest.fixture
    def rst_multiple_blocks(self):
        """Sample RST content with multiple code blocks."""
        return """
First block:

.. code-block:: python

    x = 1
    y = 2

Second block::

    literal block
    with text

Third block:

.. code:: sql

    SELECT * FROM users
    WHERE active = true;
        """

    def test_extract_code_block_directive(self, rst_code_block_python):
        """Test extraction of .. code-block:: directive."""
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(rst_code_block_python)
        
        assert len(blocks) == 1
        assert blocks[0].language == 'python'
        assert 'def hello_world():' in blocks[0].code_content
        assert 'print("Hello, World!")' in blocks[0].code_content

    def test_extract_code_directive(self, rst_code_javascript):
        """Test extraction of .. code:: directive."""
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(rst_code_javascript)
        
        assert len(blocks) == 1
        assert blocks[0].language == 'javascript'
        assert 'const greeting = "Hello"' in blocks[0].code_content

    def test_extract_sourcecode_directive(self):
        """Test extraction of .. sourcecode:: directive."""
        content = """
.. sourcecode:: ruby

    puts "Hello from Ruby"
    5.times { puts "Ruby!" }
        """
        
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        assert blocks[0].language == 'ruby'
        assert 'puts "Hello from Ruby"' in blocks[0].code_content

    def test_extract_literal_block(self, rst_literal_block):
        """Test extraction of literal blocks with ::."""
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(rst_literal_block)
        
        assert len(blocks) == 1
        assert blocks[0].language is None
        assert 'This is literal text' in blocks[0].code_content
        assert 'It preserves    spacing' in blocks[0].code_content

    def test_extract_code_block_with_options(self):
        """Test extraction of code block with directive options."""
        content = """
.. code-block:: python
   :linenos:
   :emphasize-lines: 2,3

    def process_data(data):
        cleaned = clean(data)
        validated = validate(cleaned)
        return validated
        """
        
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        assert blocks[0].language == 'python'
        assert 'def process_data(data):' in blocks[0].code_content
        # Options should be skipped, only code extracted

    def test_extract_multiple_blocks(self, rst_multiple_blocks):
        """Test extraction of multiple code blocks."""
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(rst_multiple_blocks)
        
        assert len(blocks) == 3
        
        # First block
        assert blocks[0].language == 'python'
        assert 'x = 1' in blocks[0].code_content
        
        # Second block
        assert blocks[1].language is None
        assert 'literal block' in blocks[1].code_content
        
        # Third block
        assert blocks[2].language == 'sql'
        assert 'SELECT * FROM users' in blocks[2].code_content

    def test_extract_nested_indentation(self):
        """Test extraction with nested indentation."""
        content = """
.. code-block:: python

    class Example:
        def __init__(self):
            self.value = 42
            
        def process(self):
            if self.value > 0:
                return True
            return False
        """
        
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        assert 'class Example:' in blocks[0].code_content
        assert '    def __init__(self):' in blocks[0].code_content
        assert '        self.value = 42' in blocks[0].code_content

    def test_empty_code_block(self):
        """Test handling of empty code blocks."""
        content = """
.. code-block:: python

Some text after.
        """
        
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 0

    def test_extract_blocks_with_simple_code_block(self):
        """Test extract_blocks method returning ExtractedCodeBlock objects."""
        content = """
.. code-block:: python

    def test_function():
        print("test")
        return True
        """
        
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        for block in blocks:
            block.source_url = "test.rst"
        
        assert len(blocks) == 1
        assert isinstance(blocks[0], ExtractedCodeBlock)
        assert blocks[0].code_content == 'def test_function():\n    print("test")\n    return True'
        assert blocks[0].language == 'python'
        assert blocks[0].source_url == "test.rst"

    def test_extract_code_blocks_by_type_rst(self):
        """Test extract_code_blocks_by_type with RST content."""
        content = """
.. code-block:: python

    def test():
        pass
        """
        
        blocks = extract_code_blocks_by_type(content, 'restructuredtext', 'test.rst')
        
        assert len(blocks) == 1
        assert isinstance(blocks[0], ExtractedCodeBlock)
        assert 'def test():' in blocks[0].code_content
        assert blocks[0].language == 'python'

    def test_extract_code_blocks_by_type_markdown(self):
        """Test extract_code_blocks_by_type falls back to markdown."""
        content = """```python
def test():
    pass
```"""
        
        blocks = extract_code_blocks_by_type(content, 'markdown', 'test.md')
        
        assert len(blocks) == 1
        assert isinstance(blocks[0], ExtractedCodeBlock)
        assert 'def test():' in blocks[0].code_content

    def test_extract_code_block_without_language(self):
        """Test extraction of code block without language specification."""
        content = """
.. code-block::

    Some code without language
    Multiple lines
        """
        
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        assert blocks[0].language is None
        assert 'Some code without language' in blocks[0].code_content

    def test_preserve_blank_lines_in_code(self):
        """Test that blank lines within code blocks are preserved."""
        content = """
.. code-block:: python

    def first():
        pass
    
    def second():
        pass
        """
        
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        # Check that blank line is preserved
        assert '\n\ndef second():' in blocks[0].code_content or '\n    \ndef second():' in blocks[0].code_content
