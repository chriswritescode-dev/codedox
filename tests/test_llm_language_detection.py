"""Tests for LLM language detection in code extraction."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.crawler.extractors.models import ExtractedCodeBlock, ExtractedContext
from src.crawler.llm_retry import LLMDescriptionGenerator


class TestLLMLanguageDetection:
    """Test LLM language detection functionality."""

    @pytest.mark.asyncio
    async def test_llm_language_correction(self):
        """Test that LLM can correct misidentified languages."""
        # Create test blocks with wrong initial language
        test_blocks = [
            ExtractedCodeBlock(
                code='export default { plugins: { "@tailwindcss/postcss": {} } }',
                language='css',  # Wrong - should be javascript
                context=ExtractedContext(
                    title='PostCSS configuration',
                    description='This configures PostCSS plugins'
                )
            ),
            ExtractedCodeBlock(
                code='<div class="container"><h1>Title</h1></div>',
                language='ruby',  # Wrong - should be html
                context=ExtractedContext(
                    title='HTML template example',
                    description='Basic HTML structure'
                )
            ),
            ExtractedCodeBlock(
                code='<div class="container"><h1>Title</h1></div>',
                language='ruby',  # Wrong - should be html
                context=ExtractedContext(
                    description='HTML template example. Basic HTML structure'
                )
            )
        ]

        # Mock the OpenAI client
        with patch('src.crawler.llm_retry.openai.AsyncOpenAI') as mock_openai:
            # Create mock response
            mock_response = Mock()
            mock_response.choices = [Mock()]

            # First call returns JavaScript detection
            mock_response.choices[0].message.content = """
LANGUAGE: javascript
TITLE: PostCSS configuration with Tailwind plugin
DESCRIPTION: Exports PostCSS configuration object with Tailwind CSS plugin
"""

            # Set up the mock client
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            # Create generator with mock settings
            with patch('src.crawler.llm_retry.get_settings') as mock_settings:
                mock_settings.return_value.code_extraction.llm_api_key.get_secret_value.return_value = 'test-key'
                mock_settings.return_value.code_extraction.llm_extraction_model = 'gpt-4'

                generator = LLMDescriptionGenerator()
                generator.client = mock_client

                # Test language correction
                results = await generator.generate_titles_and_descriptions_batch(
                    test_blocks[:1],
                    'https://postcss.org/docs/config'
                )

                # Verify language was corrected
                assert len(results) == 1
                assert results[0].language == 'javascript'
                assert results[0].title == 'PostCSS configuration with Tailwind plugin'

    @pytest.mark.asyncio
    async def test_llm_preserves_correct_language(self):
        """Test that LLM preserves correctly identified languages."""
        test_block = ExtractedCodeBlock(
            code='def hello():\n    print("Hello, World!")',
            language='python',  # Correct
            context=ExtractedContext(
                title='Python function example',
                description='Simple greeting function'
            )
        )

        with patch('src.crawler.llm_retry.openai.AsyncOpenAI') as mock_openai:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = """
LANGUAGE: python
TITLE: Simple hello world function
DESCRIPTION: Defines a function that prints Hello World greeting
"""

            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            with patch('src.crawler.llm_retry.get_settings') as mock_settings:
                mock_settings.return_value.code_extraction.llm_api_key.get_secret_value.return_value = 'test-key'
                mock_settings.return_value.code_extraction.llm_extraction_model = 'gpt-4'

                generator = LLMDescriptionGenerator()
                generator.client = mock_client

                results = await generator.generate_titles_and_descriptions_batch(
                    [test_block],
                    'https://python.org/examples'
                )

                assert results[0].language == 'python'

    def test_prompt_includes_url(self):
        """Test that the prompt includes the source URL."""
        from src.crawler.extractors.models import TITLE_AND_DESCRIPTION_PROMPT

        assert '{url}' in TITLE_AND_DESCRIPTION_PROMPT
        assert 'Source URL:' in TITLE_AND_DESCRIPTION_PROMPT
        assert 'LANGUAGE:' in TITLE_AND_DESCRIPTION_PROMPT
