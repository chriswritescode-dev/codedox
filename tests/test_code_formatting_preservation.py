"""Test that code formatting (whitespace, indentation) is preserved through the pipeline."""

import pytest
import uuid
from src.parser.code_extractor import CodeExtractor, CodeBlock
from src.database.models import CodeSnippet, Document, CrawlJob
from src.database.connection import DatabaseManager
from sqlalchemy.orm import Session


class TestCodeFormattingPreservation:
    """Test suite for verifying code formatting preservation."""
    
    @pytest.fixture
    def code_extractor(self):
        """Create a code extractor instance."""
        # Disable tree-sitter for formatting tests to ensure consistent behavior
        return CodeExtractor(use_tree_sitter=False)
    
    @pytest.fixture
    def sample_markdown_with_indented_code(self):
        """Sample markdown content with properly indented code."""
        return '''# Python Example

Here's a function with proper indentation:

```python
def calculate_fibonacci(n):
    """Calculate the nth Fibonacci number."""
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        # Recursive calculation
        return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)
    
    # This comment has leading spaces
```

And here's a class with nested indentation:

```python
class DataProcessor:
    def __init__(self, config):
        self.config = config
        self.data = []
    
    def process(self, items):
        for item in items:
            if item.is_valid():
                # Process valid items
                result = {
                    'id': item.id,
                    'value': item.value,
                    'nested': {
                        'deep': True
                    }
                }
                self.data.append(result)
```
'''
    
    @pytest.fixture
    def expected_code_blocks(self):
        """Expected code blocks with preserved formatting."""
        return [
            '''def calculate_fibonacci(n):
    """Calculate the nth Fibonacci number."""
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        # Recursive calculation
        return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)
    
    # This comment has leading spaces''',
            '''class DataProcessor:
    def __init__(self, config):
        self.config = config
        self.data = []
    
    def process(self, items):
        for item in items:
            if item.is_valid():
                # Process valid items
                result = {
                    'id': item.id,
                    'value': item.value,
                    'nested': {
                        'deep': True
                    }
                }
                self.data.append(result)'''
        ]
    
    def test_markdown_extraction_preserves_indentation(self, code_extractor, sample_markdown_with_indented_code, expected_code_blocks):
        """Test that markdown extraction preserves code indentation."""
        # Extract code blocks
        blocks = code_extractor.extract_from_content(
            sample_markdown_with_indented_code,
            source_url="test://example.com",
            content_type="markdown"
        )
        
        # Verify we found both blocks
        assert len(blocks) == 2
        
        # Check that indentation is preserved in each block
        for i, block in enumerate(blocks):
            assert block.content == expected_code_blocks[i]
            # Verify tabs and spaces are preserved
            assert '    ' in block.content  # 4-space indentation
            assert block.content.count('\n') == expected_code_blocks[i].count('\n')
    
    def test_code_block_whitespace_preservation(self, code_extractor):
        """Test various whitespace scenarios are preserved."""
        test_cases = [
            # Tab indentation
            ("```python\n\tdef test():\n\t\tpass\n```", "\tdef test():\n\t\tpass"),
            # Mixed spaces and tabs
            ("```python\n    def test():\n\t\tpass\n```", "    def test():\n\t\tpass"),
            # Trailing spaces
            ("```python\ndef test():    \n    pass\n```", "def test():    \n    pass"),
            # Empty lines with spaces
            ("```python\ndef test():\n    \n    pass\n```", "def test():\n    \n    pass"),
        ]
        
        for markdown, expected in test_cases:
            blocks = code_extractor.extract_from_content(markdown, content_type="markdown")
            assert len(blocks) == 1
            assert blocks[0].content == expected
    
    def test_database_storage_preserves_formatting(self, db: Session, code_extractor, sample_markdown_with_indented_code):
        """Test that code formatting is preserved when stored in database."""
        # Extract code blocks
        blocks = code_extractor.extract_from_content(
            sample_markdown_with_indented_code,
            source_url="test://example.com",
            content_type="markdown"
        )
        
        # Create a dummy document for testing
        
        # Create a crawl job
        job = CrawlJob(
            id=uuid.uuid4(),
            name="Test Job",
            start_urls=["test://example.com"],
            status="completed"
        )
        db.add(job)
        db.flush()
        
        # Create a document
        doc = Document(
            crawl_job_id=job.id,
            url="test://example.com/page",
            title="Test Page",
            markdown_content=sample_markdown_with_indented_code,
            content_hash="test_hash"
        )
        db.add(doc)
        db.flush()
        
        # Store code snippets
        for block in blocks:
            snippet = CodeSnippet(
                document_id=doc.id,
                title="Test Snippet",
                language="python",
                code_content=block.content,
                code_hash=block.hash,
                source_url="test://example.com/page"
            )
            db.add(snippet)
        
        db.commit()
        
        # Retrieve and verify
        stored_snippets = db.query(CodeSnippet).filter_by(document_id=doc.id).all()
        assert len(stored_snippets) == 2
        
        for i, snippet in enumerate(stored_snippets):
            # Verify formatting is preserved
            assert snippet.code_content == blocks[i].content
            assert '    ' in snippet.code_content  # Indentation preserved
            assert snippet.code_content.count('\n') == blocks[i].content.count('\n')
    
    def test_format_output_preserves_code(self, db: Session):
        """Test that format_output method preserves code formatting."""
        # Create a snippet with indented code
        code_with_indentation = '''def example():
    if True:
        print("Hello")
        # Indented comment
    return None'''
        
        snippet = CodeSnippet(
            title="Test Function",
            description="A test function",
            language="python",
            code_content=code_with_indentation,
            code_hash="test_hash",
            source_url="test://example.com"
        )
        
        # Format output
        output = snippet.format_output()
        
        # Verify the code is preserved in the output
        assert code_with_indentation in output
        assert '```python' in output
        assert '    if True:' in output  # Indentation preserved