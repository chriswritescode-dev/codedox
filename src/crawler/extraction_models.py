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


# LLM prompt for getting both title and description
TITLE_AND_DESCRIPTION_PROMPT = """
Analyze the code snippet below and generate a title and description based on what the code actually does.

FORMAT YOUR RESPONSE EXACTLY AS:
TITLE: [5-10 words describing what this specific code does]
DESCRIPTION: [10-30 words explaining what this specific code accomplishes]

Guidelines:
- Focus ONLY on the code provided below, not the examples
- TITLE should describe the specific action or purpose of the code
- DESCRIPTION should explain what this code does and how it works
- DO NOT start description with "The code..." or "This code..."
- Be direct and specific to the actual code provided

=== ACTUAL CODE TO ANALYZE ===

Context: {context}

Code to analyze:
{code}

Analyze the above code and respond with TITLE and DESCRIPTION for it.
"""