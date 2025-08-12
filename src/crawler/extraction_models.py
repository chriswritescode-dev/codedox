"""Simple data structures for the new HTML extraction method."""

from dataclasses import dataclass, field


@dataclass
class SimpleCodeBlock:
    """Simplified code block structure for HTML extraction + LLM description."""
    code: str
    language: str | None = None
    title: str | None = None
    description: str | None = None
    source_url: str | None = None

    # Metadata from HTML extraction
    container_type: str | None = None  # example, api-method, tutorial-step, etc.
    context_before: list[str] = field(default_factory=list)
    context_after: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# LLM prompt for getting language, title and description
TITLE_AND_DESCRIPTION_PROMPT = """
Analyze the code snippet below and identify its programming language, then generate a title and description based on what the code actually does.

FORMAT YOUR RESPONSE EXACTLY AS:
LANGUAGE: [programming language name]
TITLE: [5-15 words describing what this specific code does]
DESCRIPTION: [20-60 words explaining what this specific code accomplishes include version if exists in context]

Guidelines:
- Identify the programming language based on syntax, keywords, and context
- Consider the source URL and documentation context when identifying the language
- For React code with JSX syntax, use "jsx" not "javascript"
- For TypeScript React code, use "tsx" not "typescript"
- For Vue components, use "vue" not "javascript"
- For markup/config files, be specific (e.g., "postcss" not just "css")
- TITLE should describe the specific action or purpose of the code
- DESCRIPTION should explain what this code does and how it works including any relevant versions if applicable. 
- DO NOT start description with "The code..." or "This code..."
- Be direct and specific to the actual code provided, provide enough detail for a definition. For a user to understand. 

=== ACTUAL CODE TO ANALYZE ===

Source URL: {url}
Context: {context}

Code to analyze:
{code}

Analyze the above code and respond with LANGUAGE, TITLE and DESCRIPTION for it.
"""




