"""Async retry mechanism for LLM description generation."""

import asyncio
import logging
import os
from typing import Optional, List

import openai

from .extraction_models import SimpleCodeBlock, TITLE_AND_DESCRIPTION_PROMPT
from ..config import get_settings

logger = logging.getLogger(__name__)


class LLMDescriptionGenerator:
    """Handles LLM description generation for code blocks."""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize OpenAI client if API key is available."""
        if self.settings.code_extraction.llm_api_key:
            api_key = self.settings.code_extraction.llm_api_key.get_secret_value()
            base_url = None
            if hasattr(self.settings.code_extraction, 'llm_base_url'):
                base_url = self.settings.code_extraction.llm_base_url
            
            self.client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
    
    async def generate_titles_and_descriptions_batch(
        self,
        code_blocks: List[SimpleCodeBlock],
        url: str,
        max_concurrent: Optional[int] = None,
        semaphore: Optional[asyncio.Semaphore] = None
    ) -> List[SimpleCodeBlock]:
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
        # Use provided semaphore or create one
        if semaphore is None:
            # Use environment variable if max_concurrent not provided
            if max_concurrent is None:
                max_concurrent = int(os.getenv('CODE_LLM_NUM_PARALLEL', '5'))
                logger.info(f"Using CODE_LLM_NUM_PARALLEL={max_concurrent} for batch title/description generation")
            
            # Create semaphore for concurrency control
            semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(block: SimpleCodeBlock) -> SimpleCodeBlock:
            async with semaphore:
                if not self.client:
                    logger.error("LLM client not initialized - missing API key")
                    block.title = f"Code Block in {block.language or 'Unknown'}"
                    block.description = f"Code block in {block.language or 'unknown'} language"
                    return block
                
                # Build context from before/after context
                context_parts = []
                if block.context_before:
                    context_parts.extend(block.context_before)
                if block.context_after:
                    context_parts.extend(block.context_after)
                
                context = " ".join(context_parts) if context_parts else "No additional context available"
                
                # Create the prompt using string replacement to avoid format string conflicts
                prompt = TITLE_AND_DESCRIPTION_PROMPT.replace(
                    "{context}", context[:500]  # Limit context length
                ).replace(
                    "{code}", block.code[:2000]  # Limit code length
                )
                
                max_retries = 2
                for attempt in range(max_retries):
                    try:
                        logger.debug(f"LLM title/description attempt {attempt + 1} for code block from {url}")
                        
                        # Make completion call
                        response = await self.client.chat.completions.create(
                            model=self.settings.code_extraction.llm_extraction_model,
                            messages=[
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.1,
                            max_tokens=200  # Slightly more tokens for both title and description
                        )
                        
                        # Extract and parse response
                        content = response.choices[0].message.content.strip()
                        
                        # Parse title and description
                        title = None
                        description = None
                        
                        for line in content.split('\n'):
                            line = line.strip()
                            if line.startswith("TITLE:"):
                                title = line[6:].strip()
                            elif line.startswith("DESCRIPTION:"):
                                description = line[12:].strip()
                        
                        if title and description:
                            logger.debug(f"Generated title: {title}")
                            logger.debug(f"Generated description: {description[:100]}...")
                            block.title = title
                            block.description = description
                            return block
                        else:
                            logger.warning(f"Failed to parse title and description from response: {content}")
                            
                    except Exception as e:
                        logger.error(f"LLM title/description error on attempt {attempt + 1}: {e}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
                # Fallback if all attempts failed
                logger.error(f"All {max_retries} title/description attempts failed")
                block.title = f"Code Block in {block.language or 'Unknown'}"
                block.description = f"Code block in {block.language or 'unknown'} language"
                return block
        
        # Run generation concurrently
        tasks = [generate_with_semaphore(block) for block in code_blocks]
        
        results = []
        for future in asyncio.as_completed(tasks):
            result = await future
            results.append(result)
        
        return results



# Keep old class name for backward compatibility
LLMRetryExtractor = LLMDescriptionGenerator