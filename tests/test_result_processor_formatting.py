"""Tests for result processor code block handling."""

from unittest.mock import Mock

import pytest

from src.crawler.extractors.models import ExtractedCodeBlock, ExtractedContext
from src.crawler.result_processor import ResultProcessor


class TestResultProcessorFormatting:
    """Test code block processing in result processor."""

    @pytest.mark.asyncio
    async def test_code_blocks_are_saved_correctly(self):
        """Test that code blocks are saved to database."""
        processor = ResultProcessor()

        # Mock database session
        mock_session = Mock()
        mock_doc = Mock(id=1, url='https://example.com/test')

        # Create test code blocks
        code_blocks = [
            ExtractedCodeBlock(
                code='const x = 5;\nconst y = 10;',
                language='javascript',
                context=ExtractedContext(
                    title='Variable declarations',
                    description='Declares two constants'
                )
            )
        ]

        # Mock database queries
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        mock_session.add = Mock()
        mock_session.flush = Mock()
        mock_session.commit = Mock()

        snippet_count = await processor._process_code_blocks(
            mock_session, mock_doc, code_blocks, 'https://example.com/test'
        )

        # Verify the code was saved
        saved_snippet = mock_session.add.call_args[0][0]
        assert saved_snippet.code_content == 'const x = 5;\nconst y = 10;'
        assert saved_snippet.language == 'javascript'
        assert snippet_count == 1

    @pytest.mark.asyncio
    async def test_duplicate_detection(self):
        """Test that duplicate code blocks are detected."""
        processor = ResultProcessor()

        # Mock database session
        mock_session = Mock()
        mock_doc = Mock(id=1, url='https://example.com/test')

        # Create test code block
        test_code = 'function test() { return 42; }'
        code_blocks = [
            ExtractedCodeBlock(
                code=test_code,
                language='javascript',
                context=ExtractedContext(
                    title='Test function',
                    description='Returns 42'
                )
            )
        ]

        # Calculate expected hash (MD5 is used in the actual code)
        import hashlib
        expected_hash = hashlib.md5(test_code.encode()).hexdigest()

        # Mock existing snippet with same hash
        existing_snippet = Mock(
            code_hash=expected_hash,
            code_content=test_code
        )
        
        # Setup mock to return existing snippet when checking for duplicates
        mock_query = Mock()
        mock_filter_by = Mock()
        mock_filter_by.first.return_value = existing_snippet
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query
        
        mock_session.add = Mock()
        mock_session.flush = Mock()
        mock_session.commit = Mock()

        snippet_count = await processor._process_code_blocks(
            mock_session, mock_doc, code_blocks, 'https://example.com/test'
        )

        # Should not add duplicate
        assert snippet_count == 0
        # Verify that add was not called since it's a duplicate
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_code_blocks(self):
        """Test processing multiple code blocks."""
        processor = ResultProcessor()

        # Mock database session
        mock_session = Mock()
        mock_doc = Mock(id=1, url='https://example.com/test')

        code_blocks = [
            ExtractedCodeBlock(
                code='function greet(name) {\n  console.log(`Hello, ${name}!`);\n}',
                language='javascript',
                context=ExtractedContext(
                    title='Greeting function',
                    description='Greets a person by name'
                )
            ),
            ExtractedCodeBlock(
                code='def greet(name):\n    print(f"Hello, {name}!")',
                language='python',
                context=ExtractedContext(
                    title='Python greeting',
                    description='Python version'
                )
            )
        ]

        # Mock database queries
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        mock_session.add = Mock()
        mock_session.flush = Mock()
        mock_session.commit = Mock()

        snippet_count = await processor._process_code_blocks(
            mock_session, mock_doc, code_blocks, 'https://example.com/test'
        )

        # Verify both snippets were saved
        assert snippet_count == 2
        assert mock_session.add.call_count == 2
