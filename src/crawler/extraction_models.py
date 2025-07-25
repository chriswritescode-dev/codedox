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
Provide a concise, direct description (10-30 words max) of what this code does. Focus on the main action or purpose. Use the context provided to help you understand the purpose of the code.

DO NOT start with "The code..." or "This code...". Be direct and specific.

Examples:
- "Tests page title contains 'Playwright' text"  
- "Clicks Get started link and verifies Installation heading"
- "Creates isolated browser context for each test"
- "Demonstrates how to use implement Next.js Route Handlers"

Context: {context}

Code:
{code}

Description:"""