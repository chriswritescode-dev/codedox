"""Simple data structures for the new HTML extraction method."""

from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class SimpleCodeBlock:
    """Simplified code block structure for HTML extraction + LLM description."""
    code: str
    language: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    
    # Metadata from HTML extraction
    container_type: Optional[str] = None  # example, api-method, tutorial-step, etc.
    context_before: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)


# Simple LLM prompt for getting descriptions
DESCRIPTION_PROMPT = """
Provide a concise, direct description (10-15 words max) of what this code does. Focus on the main action or purpose.

DO NOT start with "The code..." or "This code...". Be direct and specific.

Examples:
- "Tests page title contains 'Playwright' text"  
- "Clicks Get started link and verifies Installation heading"
- "Creates isolated browser context for each test"
- "Navigates to Playwright homepage"

Context: {context}

Code:
{code}

Description:"""