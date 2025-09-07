"""Unified data models for code extraction."""

from dataclasses import dataclass, field


@dataclass
class ExtractedContext:
    """Semantic context for a code block."""
    title: str | None = None          # From nearest heading
    description: str | None = None     # Cleaned paragraphs/lists between heading and code
    raw_content: list[str] = field(default_factory=list)  # Original content lines (for debugging)
    hierarchy: list[str] = field(default_factory=list)    # Heading hierarchy (h1 > h2 > h3)


@dataclass
class ExtractedCodeBlock:
    """Unified code block with context."""
    code: str
    language: str | None = None
    context: ExtractedContext = field(default_factory=ExtractedContext)
    source_url: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    
    @property
    def title(self) -> str | None:
        """Get title from context."""
        return self.context.title if self.context else None
    
    @property
    def description(self) -> str | None:
        """Get description from context."""
        return self.context.description if self.context else None
    
    @property
    def code_content(self) -> str:
        """Alias for code to maintain compatibility."""
        return self.code


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
