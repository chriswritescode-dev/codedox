"""Tests for result processor with formatting integration."""

from unittest.mock import Mock, patch

import pytest

from src.crawler.extraction_models import SimpleCodeBlock
from src.crawler.result_processor import ResultProcessor


class TestResultProcessorFormatting:
    """Test formatting integration in result processor."""

    @pytest.mark.asyncio
    async def test_formatting_improves_code(self):
        """Test that improved formatted code is saved."""
        processor = ResultProcessor()
        
        # Mock settings to ensure formatting is enabled
        processor.settings.code_extraction.disable_formatting = False

        # Mock database session
        mock_session = Mock()
        mock_doc = Mock(id=1, url='https://example.com/test')

        # Create test code blocks with poorly formatted code
        code_blocks = [
            SimpleCodeBlock(
                code='const x=5;const y=10;',  # Poorly formatted JS
                language='javascript',
                title='Variable declarations',
                description='Declares two constants'
            )
        ]

        # Mock database queries
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        mock_session.add = Mock()
        mock_session.flush = Mock()
        mock_session.commit = Mock()

        # Process code blocks with mocked formatting
        with patch.object(processor, '_format_blocks_concurrently') as mock_format:
            # Mock the concurrent formatting to return formatted blocks
            mock_format.return_value = [{
                'index': 0,
                'content': 'const x=5;const y=10;',
                'formatted_content': 'const x = 5;\nconst y = 10;',  # Formatted version
                'language': 'javascript',
                'title': 'Variable declarations',
                'description': 'Declares two constants',
                'metadata': {},
                'filename': None
            }]

            snippet_count = await processor._process_code_blocks(
                mock_session, mock_doc, code_blocks, 'https://example.com/test'
            )

        # Verify formatting method was called
        mock_format.assert_called_once()

        # Verify the formatted code was saved
        saved_snippet = mock_session.add.call_args[0][0]
        assert saved_snippet.code_content == 'const x = 5;\nconst y = 10;'
        assert saved_snippet.language == 'javascript'
        assert snippet_count == 1

    @pytest.mark.asyncio
    async def test_formatting_preserves_original_on_error(self):
        """Test that original code is preserved when formatting fails."""
        processor = ResultProcessor()

        # Mock database session
        mock_session = Mock()
        mock_doc = Mock(id=1, url='https://example.com/test')

        # Create test code block
        code_blocks = [
            SimpleCodeBlock(
                code='function test() { return 42; }',
                language='javascript',
                title='Test function',
                description='Returns 42'
            )
        ]

        # Mock database queries
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        mock_session.add = Mock()
        mock_session.flush = Mock()
        mock_session.commit = Mock()

        # Process with formatter that throws error
        with patch.object(processor, 'code_formatter') as mock_formatter:
            mock_formatter.format.side_effect = Exception('Formatting failed')

            snippet_count = await processor._process_code_blocks(
                mock_session, mock_doc, code_blocks, 'https://example.com/test'
            )

        # Verify original code was saved
        saved_snippet = mock_session.add.call_args[0][0]
        assert saved_snippet.code_content == 'function test() { return 42; }'
        assert snippet_count == 1

    @pytest.mark.asyncio
    async def test_formatting_preserves_already_formatted(self):
        """Test that well-formatted code is not changed."""
        processor = ResultProcessor()

        # Mock database session
        mock_session = Mock()
        mock_doc = Mock(id=1, url='https://example.com/test')

        # Create test code block that's already well formatted
        well_formatted = '''function greet(name) {
  console.log(`Hello, ${name}!`);
}'''

        code_blocks = [
            SimpleCodeBlock(
                code=well_formatted,
                language='javascript',
                title='Greeting function',
                description='Greets a person by name'
            )
        ]

        # Mock database queries
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        mock_session.add = Mock()
        mock_session.flush = Mock()
        mock_session.commit = Mock()

        # Process with real formatter (or mock that returns same)
        with patch.object(processor, 'code_formatter') as mock_formatter:
            # Formatter returns the same code (no improvement needed)
            mock_formatter.format.return_value = well_formatted

            snippet_count = await processor._process_code_blocks(
                mock_session, mock_doc, code_blocks, 'https://example.com/test'
            )

        # Verify original code was kept
        saved_snippet = mock_session.add.call_args[0][0]
        assert saved_snippet.code_content == well_formatted
        assert snippet_count == 1
