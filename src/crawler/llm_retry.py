"""Async retry mechanism for failed LLM extractions."""

import asyncio
import logging
import json
from typing import Optional, Dict, Any
from datetime import datetime

import openai
from pydantic import ValidationError

from .extraction_models import LLMExtractionResult, EXTRACTION_INSTRUCTIONS, get_extraction_schema
from ..config import get_settings

logger = logging.getLogger(__name__)


class LLMRetryExtractor:
    """Handles retry logic for failed LLM extractions."""
    
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
    
    async def extract_with_retry(
        self, 
        markdown_content: str, 
        url: str,
        title: Optional[str] = None,
        max_retries: int = 2
    ) -> Optional[LLMExtractionResult]:
        """
        Extract code blocks with retry logic.
        
        Args:
            markdown_content: The markdown content to extract from
            url: Source URL for context
            title: Page title for context
            max_retries: Maximum number of retry attempts
            
        Returns:
            LLMExtractionResult or None if all retries fail
        """
        if not self.client:
            logger.error("LLM client not initialized - missing API key")
            return None
        
        # Get the JSON schema
        schema = get_extraction_schema()
        
        # Enhanced system prompt with schema
        system_prompt = """You are a code extraction specialist. Your job is to extract ALL code snippets from documentation.

CRITICAL: You MUST return a response that EXACTLY matches the provided JSON schema. 
The response must be valid JSON with the exact field names specified.
Do NOT use 'blocks' - use 'code_blocks' as specified in the schema."""
        
        # Create user prompt with schema
        user_prompt = f"""{EXTRACTION_INSTRUCTIONS}

Page URL: {url}
Page Title: {title or 'Unknown'}

Content to analyze:
{markdown_content}"""
        
        for attempt in range(max_retries):
            try:
                logger.info(f"LLM extraction attempt {attempt + 1} for {url}")
                
                # Make the API call
                response = await self.client.chat.completions.create(
                    model=self.settings.code_extraction.llm_extraction_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}  # Force JSON response
                )
                
                # Extract and parse response
                llm_content = response.choices[0].message.content.strip()
                
                # Try to parse JSON
                try:
                    extracted_data = json.loads(llm_content)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse LLM JSON response: {e}")
                    continue
                
                # Handle legacy format where LLM returns 'blocks' instead of 'code_blocks'
                if isinstance(extracted_data, dict) and "blocks" in extracted_data and "code_blocks" not in extracted_data:
                    logger.warning("LLM returned 'blocks' instead of 'code_blocks', transforming...")
                    blocks = extracted_data.pop("blocks")
                    
                    # Transform each block to ensure 'code' field exists
                    transformed_blocks = []
                    for block in blocks:
                        if isinstance(block, dict):
                            # If block has 'content' instead of 'code', rename it
                            if "content" in block and "code" not in block:
                                block["code"] = block.pop("content")
                            transformed_blocks.append(block)
                        else:
                            transformed_blocks.append(block)
                    
                    extracted_data["code_blocks"] = transformed_blocks
                
                # Add extraction metadata
                extracted_data["extraction_timestamp"] = datetime.utcnow().isoformat()
                extracted_data["extraction_model"] = self.settings.code_extraction.llm_extraction_model
                
                # Validate with Pydantic
                try:
                    result = LLMExtractionResult(**extracted_data)
                    logger.info(f"Successfully extracted {len(result.code_blocks)} code blocks from {url}")
                    return result
                except ValidationError as e:
                    logger.error(f"Validation error on attempt {attempt + 1}: {e}")
                    # On last attempt, log the data that failed validation
                    if attempt == max_retries - 1:
                        logger.error(f"Failed data structure: {json.dumps(extracted_data, indent=2)}")
                    continue
                    
            except Exception as e:
                logger.error(f"LLM extraction error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        logger.error(f"All {max_retries} extraction attempts failed for {url}")
        return None
    
    async def extract_batch(
        self,
        failed_extractions: list[Dict[str, Any]],
        max_concurrent: int = 5
    ) -> Dict[str, Optional[LLMExtractionResult]]:
        """
        Extract from multiple failed pages concurrently.
        
        Args:
            failed_extractions: List of dicts with 'url', 'markdown_content', 'title'
            max_concurrent: Maximum concurrent extractions
            
        Returns:
            Dict mapping URL to extraction result (or None if failed)
        """
        results = {}
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def extract_with_semaphore(item: Dict[str, Any]) -> tuple[str, Optional[LLMExtractionResult]]:
            async with semaphore:
                result = await self.extract_with_retry(
                    markdown_content=item['markdown_content'],
                    url=item['url'],
                    title=item.get('title')
                )
                return item['url'], result
        
        # Run extractions concurrently
        tasks = [extract_with_semaphore(item) for item in failed_extractions]
        
        for future in asyncio.as_completed(tasks):
            url, result = await future
            results[url] = result
        
        return results