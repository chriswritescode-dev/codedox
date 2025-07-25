"""Async retry mechanism for LLM description generation."""

import asyncio
import logging
import os
from typing import Optional, List

import openai

from .extraction_models import SimpleCodeBlock, DESCRIPTION_PROMPT
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
    
    async def generate_description(
        self,
        code_block: SimpleCodeBlock,
        url: str,
        max_retries: int = 2
    ) -> Optional[str]:
        """
        Generate a description for a code block using LLM.
        
        Args:
            code_block: Code block to describe
            url: Source URL for context
            max_retries: Maximum number of retry attempts
            
        Returns:
            Description string or None if all retries fail
        """
        if not self.client:
            logger.error("LLM client not initialized - missing API key")
            return None
        
        # Build context from before/after context
        context_parts = []
        if code_block.context_before:
            context_parts.extend(code_block.context_before)
        if code_block.context_after:
            context_parts.extend(code_block.context_after)
        
        context = " ".join(context_parts) if context_parts else "No additional context available"
        
        # Create the prompt
        prompt = DESCRIPTION_PROMPT.format(
            url=url,
            context=context[:500],  # Limit context length
            code=code_block.code[:2000]  # Limit code length
        )
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"LLM description attempt {attempt + 1} for code block from {url}")
                
                # Make simple completion call
                response = await self.client.chat.completions.create(
                    model=self.settings.code_extraction.llm_extraction_model,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=150  # Keep descriptions concise
                )
                
                # Extract and clean response
                description = response.choices[0].message.content.strip()
                
                # Remove any "Description:" prefix if LLM added it
                if description.lower().startswith("description:"):
                    description = description[12:].strip()
                
                logger.debug(f"Generated description: {description[:100]}...")
                return description
                    
            except Exception as e:
                logger.error(f"LLM description error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        logger.error(f"All {max_retries} description attempts failed")
        return None
    
    async def generate_descriptions_batch(
        self,
        code_blocks: List[SimpleCodeBlock],
        url: str,
        max_concurrent: Optional[int] = None,
        semaphore: Optional[asyncio.Semaphore] = None
    ) -> List[SimpleCodeBlock]:
        """
        Generate descriptions for multiple code blocks concurrently.
        
        Args:
            code_blocks: List of code blocks to generate descriptions for
            url: Source URL for context
            max_concurrent: Maximum concurrent requests (defaults to CODE_LLM_NUM_PARALLEL env var or 5)
            semaphore: Optional semaphore for controlling concurrency
            
        Returns:
            List of code blocks with descriptions added
        """
        # Use provided semaphore or create one
        if semaphore is None:
            # Use environment variable if max_concurrent not provided
            if max_concurrent is None:
                max_concurrent = int(os.getenv('CODE_LLM_NUM_PARALLEL', '5'))
                logger.info(f"Using CODE_LLM_NUM_PARALLEL={max_concurrent} for batch description generation")
            
            # Create semaphore for concurrency control
            semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(block: SimpleCodeBlock) -> SimpleCodeBlock:
            async with semaphore:
                description = await self.generate_description(block, url)
                if description:
                    block.description = description
                else:
                    # Fallback description
                    block.description = f"Code block in {block.language or 'unknown'} language"
                return block
        
        # Run description generation concurrently
        tasks = [generate_with_semaphore(block) for block in code_blocks]
        
        results = []
        for future in asyncio.as_completed(tasks):
            result = await future
            results.append(result)
        
        return results


# Keep old class name for backward compatibility
LLMRetryExtractor = LLMDescriptionGenerator