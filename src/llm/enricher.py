"""Enrich code snippets with LLM-generated metadata."""

import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .client import LLMClient, LLMError
from ..parser.code_extractor import CodeBlock
from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class EnrichedCodeBlock:
    """Code block with LLM-enriched metadata."""
    original: CodeBlock
    detected_language: Optional[str] = None
    enriched_title: Optional[str] = None
    enriched_description: Optional[str] = None
    keywords: List[str] = None
    frameworks: List[str] = None
    purpose: Optional[str] = None
    dependencies: List[str] = None

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.frameworks is None:
            self.frameworks = []
        if self.dependencies is None:
            self.dependencies = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        base_dict = self.original.to_dict()

        # Add enriched fields
        if self.enriched_title:
            base_dict['title'] = self.enriched_title
        if self.enriched_description:
            base_dict['description'] = self.enriched_description

        # Add metadata
        base_dict["metadata"].update(
            {
                "keywords": self.keywords,
                "frameworks": self.frameworks,
                "purpose": self.purpose,
                "dependencies": self.dependencies,
                "llm_enriched": True,
            }
        )

        return base_dict


class MetadataEnricher:
    """Enrich code snippets with LLM-generated metadata."""

    # System prompt for code analysis
    SYSTEM_PROMPT = settings.llm.system_prompt

    def __init__(self, llm_client: Optional[LLMClient] = None, 
                 skip_small_snippets: bool = True,
                 min_lines: int = 5,
                 debug: bool = False):
        """Initialize metadata enricher.
        
        Args:
            llm_client: LLM client instance (creates one if not provided)
            skip_small_snippets: Skip enriching very small code snippets
            min_lines: Minimum lines to consider for enrichment
            debug: Enable debug logging
        """
        self.llm_client = llm_client
        self.skip_small_snippets = skip_small_snippets
        self.min_lines = min_lines
        self.debug = debug

        if debug:
            logger.setLevel(logging.DEBUG)

    async def enrich_code_block(self, code_block: CodeBlock) -> EnrichedCodeBlock:
        """Enrich a single code block with metadata.
        
        Args:
            code_block: Code block to enrich
            
        Returns:
            EnrichedCodeBlock with additional metadata
        """
        # Skip small snippets if configured
        if self.skip_small_snippets and code_block.lines_of_code < self.min_lines:
            logger.debug(f"Skipping small snippet: {code_block.lines_of_code} lines")
            return EnrichedCodeBlock(original=code_block)

        # Create prompt
        prompt = self._create_analysis_prompt(code_block)

        try:
            # Ensure we have an LLM client
            if not self.llm_client:
                self.llm_client = LLMClient(debug=self.debug)

            # Generate metadata
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.1  # Low temperature for consistent metadata
            )

            # Parse response
            metadata = self._parse_llm_response(response.content)

            # Create enriched block
            enriched = EnrichedCodeBlock(
                original=code_block,
                detected_language=metadata.get("language", code_block.language),
                enriched_title=metadata.get("title", code_block.title),
                enriched_description=metadata.get("description", code_block.description),
                keywords=metadata.get("keywords", []),
                frameworks=metadata.get("frameworks", []),
                purpose=metadata.get("purpose"),
                dependencies=metadata.get("dependencies", []),
            )

            logger.info(f"Enriched code block: {enriched.enriched_title}")
            return enriched

        except Exception as e:
            logger.error(f"Failed to enrich code block: {e}")
            # Return original block on error
            return EnrichedCodeBlock(original=code_block)

    async def enrich_batch(self, code_blocks: List[CodeBlock]) -> List[EnrichedCodeBlock]:
        """Enrich a batch of code blocks.
        
        Args:
            code_blocks: List of code blocks to enrich
            
        Returns:
            List of enriched code blocks
        """
        import asyncio

        if not code_blocks:
            return []

        logger.info(f"Processing {len(code_blocks)} code blocks in parallel")

        # Create all enrichment tasks - let semaphore in LLMClient control concurrency
        tasks = [self.enrich_code_block(block) for block in code_blocks]

        # Process all blocks in parallel (semaphore will limit actual concurrency)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle results
        enriched_blocks = []
        for block, result in zip(code_blocks, results):
            if isinstance(result, Exception):
                logger.error(f"Error enriching block: {result}")
                enriched_blocks.append(EnrichedCodeBlock(original=block))
            else:
                enriched_blocks.append(result)

        successful_count = sum(1 for r in results if not isinstance(r, Exception))
        logger.info(f"Completed enrichment: {successful_count}/{len(code_blocks)} successful")

        return enriched_blocks

    def _create_analysis_prompt(self, code_block: CodeBlock) -> str:
        """Create analysis prompt for LLM."""
        # Include context if available
        context_info = ""

        # Prefer section content, then full page content, then context before/after
        if hasattr(code_block, 'extraction_metadata') and code_block.extraction_metadata.get('full_section_content'):
            section_content = code_block.extraction_metadata['full_section_content']
            section_title = code_block.extraction_metadata.get('section_title', 'Unknown Section')
            context_info = f"\n\nThis code appears in the section titled: {section_title}\n"
            context_info += f"Full section context:\n{section_content[:3000]}"
            if len(section_content) > 3000:
                context_info += "..."
        elif hasattr(code_block, 'extraction_metadata') and code_block.extraction_metadata.get('full_page_content'):
            full_page_content = code_block.extraction_metadata['full_page_content']
            context_info = f"\n\nFull page context (showing relevant portion):\n{full_page_content[:4000]}"
            if len(full_page_content) > 4000:
                context_info += "..."
        elif code_block.context_before or code_block.context_after:
            context_info = "\n\nContext information:"
            if code_block.context_before:
                # Include full context for better understanding
                context_info += f"\nBefore code:\n{code_block.context_before[:1500]}"
                if len(code_block.context_before) > 1500:
                    context_info += "..."
            if code_block.context_after:
                context_info += f"\n\nAfter code:\n{code_block.context_after[:1500]}"
                if len(code_block.context_after) > 1500:
                    context_info += "..."

        # Handle unknown language
        language_hint = code_block.language if code_block.language != 'unknown' else 'unknown language'

        prompt = f"""Analyze this code snippet (current language tag: {language_hint}):

```
{code_block.content}
```{context_info}

Source URL: {code_block.source_url}

Important: Detect the actual programming language based on the code syntax and context. 

Provide structured metadata in the specified JSON format."""

        return prompt

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response to extract metadata."""
        try:
            # Try to extract JSON from response
            # Handle cases where LLM adds extra text
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                metadata = json.loads(json_str)

                # Validate structure
                self._validate_metadata(metadata)

                return metadata
            else:
                logger.error(f"No JSON found in response: {response}")
                return {}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {response}")
            return {}
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return {}

    def _validate_metadata(self, metadata: Dict[str, Any]):
        """Validate and clean metadata structure."""
        # Ensure lists are lists
        for field in ['keywords', 'frameworks', 'dependencies']:
            if field in metadata and not isinstance(metadata[field], list):
                metadata[field] = []

        # Truncate if needed
        if 'title' in metadata and len(metadata['title']) > 100:
            metadata['title'] = metadata['title'][:97] + '...'

        if 'description' in metadata and len(metadata['description']) > 500:
            metadata['description'] = metadata['description'][:497] + '...'

    async def test_enrichment(self, sample_code: Optional[str] = None) -> Dict[str, Any]:
        """Test enrichment with sample code."""
        if not sample_code:
            sample_code = '''def calculate_fibonacci(n):
    """Calculate nth Fibonacci number using dynamic programming."""
    if n <= 1:
        return n
    
    fib = [0] * (n + 1)
    fib[1] = 1
    
    for i in range(2, n + 1):
        fib[i] = fib[i-1] + fib[i-2]
    
    return fib[n]'''

        # Create test code block
        test_block = CodeBlock(
            language="python",
            content=sample_code,
            source_url="test://sample",
            title="Test Code",
            description="Sample code for testing"
        )

        logger.info("Testing enrichment with sample code...")

        try:
            # Test LLM connection first
            if not self.llm_client:
                self.llm_client = LLMClient(debug=self.debug)

            connection_status = await self.llm_client.test_connection()

            if connection_status["status"] != "connected":
                return {
                    "status": "error",
                    "error": "LLM not connected",
                    "connection_status": connection_status
                }

            # Enrich the test block
            enriched = await self.enrich_code_block(test_block)

            return {
                "status": "success",
                "original": test_block.to_dict(),
                "enriched": enriched.to_dict(),
                "connection_status": connection_status
            }

        except Exception as e:
            logger.error(f"Test enrichment failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "traceback": True
            }
