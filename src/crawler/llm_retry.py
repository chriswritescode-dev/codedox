"""Async retry mechanism for LLM description generation."""

import asyncio
import json
import logging
import os

import openai

from ..config import get_settings
from .extractors.models import TITLE_AND_DESCRIPTION_PROMPT, ExtractedCodeBlock, ExtractedContext
from .language_mapping import normalize_language

logger = logging.getLogger(__name__)


class LLMDescriptionGenerator:
    """Handles LLM description generation for code blocks."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None
    ):
        """Initialize LLM description generator."""
        self.settings = get_settings()
        self.client = None
        self.custom_model = model
        self._init_client(api_key=api_key, base_url=base_url)

    def _init_client(
        self, api_key: str | None = None, base_url: str | None = None
    ):
        """Initialize OpenAI client if API key is available."""
        if api_key or self.settings.code_extraction.llm_api_key:
            # Use custom api_key if provided, otherwise use from settings
            client_api_key = api_key
            if not client_api_key:
                client_api_key = self.settings.code_extraction.llm_api_key.get_secret_value()

            # Custom api_key takes precedence for base_url
            client_base_url = base_url
            if not client_base_url and hasattr(
                self.settings.code_extraction, "llm_base_url"
            ):
                client_base_url = self.settings.code_extraction.llm_base_url

            self.client = openai.AsyncOpenAI(
                api_key=client_api_key, base_url=client_base_url
            )

    async def generate_titles_and_descriptions_batch(
        self,
        code_blocks: list[ExtractedCodeBlock],
        url: str,
        max_concurrent: int | None = None,
        semaphore: asyncio.Semaphore | None = None
    ) -> list[ExtractedCodeBlock]:
        """
        Generate titles and descriptions for multiple code blocks concurrently.
        
        Args:
            code_blocks: List of code blocks to generate titles and descriptions for
            url: Source URL for context
            max_concurrent: Maximum concurrent requests (defaults to CODE_LLM_NUM_PARALLEL env var or 5)
            semaphore: Optional semaphore for controlling concurrency
            
        Returns:
            List of code blocks with titles and descriptions added
        """

        if semaphore is None:
            if max_concurrent is None:
                max_concurrent = int(os.getenv('CODE_LLM_NUM_PARALLEL', '5'))
                logger.info(f"Using CODE_LLM_NUM_PARALLEL={max_concurrent} for batch title/description generation")

            semaphore = asyncio.Semaphore(max_concurrent)

        async def generate_with_semaphore(block: ExtractedCodeBlock) -> ExtractedCodeBlock:
            async with semaphore:
                if not self.client:
                    logger.error("LLM client not initialized - missing API key")
                    if not block.context:
                        block.context = ExtractedContext()
                    block.context.title = f"Code Block in {block.language or 'Unknown'}"
                    block.context.description = f"Code block in {block.language or 'unknown'} language"
                    return block

                # Build context from description and raw_content
                context_parts = []
                if block.context:
                    if block.context.description:
                        context_parts.append(block.context.description)
                    if block.context.raw_content:
                        context_parts.extend(block.context.raw_content)

                context = " ".join(context_parts) if context_parts else "No additional context available"

                # Create the prompt using string replacement to avoid format string conflicts
                prompt = TITLE_AND_DESCRIPTION_PROMPT.replace(
                    "{url}", url
                ).replace(
                    "{context}", context[:500]  # Limit context length
                ).replace(
                    "{code}", block.code[:2000]  # Limit code length
                )

                max_retries = 2
                for attempt in range(max_retries):
                    try:
                        logger.debug(f"LLM title/description attempt {attempt + 1} for code block from {url}")

                        # Get fresh settings to pick up runtime updates (self.settings is stale after runtime changes)
                        fresh_settings = get_settings()
                        model = (
                            self.custom_model
                            if self.custom_model
                            else fresh_settings.code_extraction.llm_extraction_model
                        )
                        logger.debug(f"Using LLM model: {model}")
                        logger.info(f"Starting LLM call for code block from {url} (attempt {attempt + 1})")
                        
                        # Parse custom parameters from settings
                        extra_params = {}
                        try:
                            extra_params_str = fresh_settings.code_extraction.llm_extra_params
                            if extra_params_str and extra_params_str != "{}":
                                extra_params = json.loads(extra_params_str)
                                logger.info(f"Using custom LLM parameters: {extra_params}")
                        except (json.JSONDecodeError, AttributeError) as e:
                            logger.warning(f"Failed to parse llm_extra_params: {e}")
                        
                        # Build request parameters
                        request_params = {
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.1,
                            "max_tokens": fresh_settings.code_extraction.llm_max_tokens,
                        }
                        
                        # Merge custom parameters
                        if extra_params:
                            logger.info(f"Merging extra_params into request: {extra_params}")
                            request_params.update(extra_params)
                        
                        logger.info(f"Final request params: {request_params}")
                        response = await self.client.chat.completions.create(**request_params)

                        logger.info(f"LLM call completed for code block from {url}")

                        # Extract and parse response
                        raw_content = response.choices[0].message.content
                        
                        # Handle None content - check for alternative response formats
                        if raw_content is None:
                            # Some models might use tool_calls or other fields
                            message = response.choices[0].message
                            
                            # Log detailed error information
                            logger.error(f"LLM returned None content for URL: {url}")
                            logger.error(f"Model: {model}")
                            logger.error(f"Full response: {response.model_dump() if hasattr(response, 'model_dump') else str(response)}")
                            logger.error(f"Message attributes: {dir(message)}")
                            
                            # Check if there's a tool_call or function_call
                            if hasattr(message, 'tool_calls') and message.tool_calls:
                                logger.error(f"Response has tool_calls instead of content: {message.tool_calls}")
                            elif hasattr(message, 'function_call') and message.function_call:
                                logger.error(f"Response has function_call instead of content: {message.function_call}")
                            
                            if extra_params:
                                logger.error(f"Extra params may be causing issues: {extra_params}")
                                logger.error("Hint: Try removing extra_params or ensure they're compatible with your model")
                            
                            raise ValueError(
                                f"LLM returned None content. Model: {model}. "
                                f"This may indicate incompatible model configuration or extra_params."
                            )
                        
                        content = raw_content.strip()

                        # Parse language, title and description
                        language = None
                        title = None
                        description = None

                        for line in content.split('\n'):
                            line = line.strip()
                            if line.startswith("LANGUAGE:"):
                                language = line[9:].strip()
                            elif line.startswith("TITLE:"):
                                title = line[6:].strip()
                            elif line.startswith("DESCRIPTION:"):
                                description = line[12:].strip()

                        if title and description:
                            logger.debug(f"Generated title: {title}")
                            logger.debug(f"Generated description: {description[:100]}...")
                            if not block.context:
                                block.context = ExtractedContext()
                            block.context.title = title
                            block.context.description = description

                            # Update language if LLM provided one
                            if language:
                                original_language = block.language
                                normalized_language = normalize_language(language)
                                block.language = normalized_language
                                if original_language and original_language != normalized_language:
                                    logger.info(f"LLM corrected language from '{original_language}' to '{normalized_language}' (raw: '{language}')")
                                else:
                                    logger.debug(f"LLM confirmed language: {normalized_language}")

                            return block
                        else:
                            logger.warning(f"Failed to parse response from LLM: {content}")

                    except Exception as e:
                        logger.error(f"LLM title/description error on attempt {attempt + 1}: {e}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff

                # Fallback if all attempts failed
                logger.error(f"All {max_retries} title/description attempts failed")
                if not block.context:
                    block.context = ExtractedContext()
                block.context.title = f"Code Block in {block.language or 'Unknown'}"
                block.context.description = f"Code block in {block.language or 'unknown'} language"
                return block

        # Run generation concurrently
        tasks = [generate_with_semaphore(block) for block in code_blocks]

        results = []
        try:
            # Process all tasks without timeout
            for future in asyncio.as_completed(tasks):
                result = await future
                results.append(result)
        except Exception as e:
            logger.error(f"Error during LLM title/description generation: {e}")
            # Return partial results and use fallback for remaining
            completed_count = len(results)
            for i in range(completed_count, len(code_blocks)):
                block = code_blocks[i]
                block.title = f"Code Block in {block.language or 'Unknown'}"
                block.description = f"Code block in {block.language or 'unknown'} language"
                results.append(block)

        return results



# Keep old class name for backward compatibility
LLMRetryExtractor = LLMDescriptionGenerator
