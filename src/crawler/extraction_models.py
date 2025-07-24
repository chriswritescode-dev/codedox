"""Pydantic models for LLM extraction schema."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CodeRelationship(BaseModel):
    """Represents a relationship between code blocks."""
    
    related_index: int = Field(description="Index of the related code block in the same page")
    relationship_type: str = Field(
        description="Type of relationship: 'imports', 'extends', 'implements', 'uses', 'example_of', 'configuration_for'"
    )
    description: str = Field(description="Description of how the code blocks are related")


class ExtractedCodeBlock(BaseModel):
    """Model for an extracted code block with all metadata."""
    
    code: str = Field(description="The actual code content")
    language: str = Field(description="Programming language (e.g., python, javascript, typescript)")
    title: str = Field(description="Descriptive title for the code block")
    description: str = Field(description="Comprehensive explanation of what the code does")
    
    # Optional metadata
    filename: Optional[str] = Field(None, description="Filename if mentioned in documentation")
    
    # Categorization
    purpose: str = Field(
        description="Main purpose: 'example', 'configuration', 'api_reference', 'tutorial', 'utility', 'test'"
    )
    frameworks: List[str] = Field(default_factory=list, description="Frameworks or libraries used")
    keywords: List[str] = Field(default_factory=list, description="Keywords for searchability")
    dependencies: List[str] = Field(default_factory=list, description="Required dependencies or imports")
    
    # Context
    section: Optional[str] = Field(None, description="Documentation section this appears in")
    prerequisites: List[str] = Field(default_factory=list, description="Prerequisites or setup required")
    
    # Relationships
    relationships: List[CodeRelationship] = Field(
        default_factory=list, 
        description="Relationships to other code blocks on the same page"
    )
    
    

class PageMetadata(BaseModel):
    """Metadata about the documentation page."""
    
    main_topic: str = Field(description="Main topic or title of the page")
    page_type: str = Field(
        description="Type of documentation: 'tutorial', 'api_reference', 'guide', 'quickstart', 'configuration'"
    )
    technologies: List[str] = Field(default_factory=list, description="Technologies covered on this page")
   

class LLMExtractionResult(BaseModel):
    """Complete extraction result from LLM."""
    
    code_blocks: List[ExtractedCodeBlock] = Field(
        default_factory=list,
        description="All code blocks extracted from the page"
    )
    page_metadata: PageMetadata = Field(description="Metadata about the documentation page")
    
    # Additional context
    key_concepts: List[str] = Field(
        default_factory=list,
        description="Key concepts explained on this page"
    )
    external_links: List[Dict[str, str]] = Field(
        default_factory=list,
        description="External links referenced (url, title, description)"
    )
    
    # Extraction metadata
    extraction_timestamp: Optional[str] = Field(None, description="When extraction occurred")
    extraction_model: Optional[str] = Field(None, description="LLM model used for extraction")


# Helper function to create the JSON schema for Crawl4AI
def get_extraction_schema() -> Dict[str, Any]:
    """Get the JSON schema for LLM extraction."""
    return LLMExtractionResult.model_json_schema()


# Extraction instructions for the LLM
EXTRACTION_INSTRUCTIONS = """
Extract ALL code blocks from this documentation page with comprehensive metadata.

IMPORTANT: A "code block" includes:
- Any code snippet, no matter how small (even single lines)
- Code examples within paragraphs or inline
- JSX/TSX components (e.g., <Component prop="value">)
- Configuration snippets
- Command-line examples
- Import statements
- Function calls
- Variable declarations

For each code block found:
1. Identify the exact code content (preserve ALL formatting, indentation, and characters)
2. Detect the programming language accurately (jsx, tsx, javascript, typescript, css, bash, etc.)
3. Generate a descriptive title based on context
4. Write a detailed description explaining:
   - What the code does
   - How to use it
   - Any important notes or warnings
5. Identify if it's a complete, runnable example
6. Categorize its purpose (example, configuration, etc.)
7. Extract frameworks, keywords, and dependencies
8. Note which section it appears in
9. Identify relationships to other code blocks on the same page

For the page overall:
1. Identify the main topic
2. Categorize the page type (tutorial, API reference, etc.)
3. List all technologies covered
4. Extract key concepts
5. Note any external links with context

CRITICAL INSTRUCTIONS:
- Extract EVERY piece of code, no matter how small
- Include inline code snippets (e.g., `<Pressable onPress={onPressFunction}>`)
- If NO code is found, return an empty code_blocks array
- ALWAYS return the complete schema structure, even with empty arrays
- For JSX/React Native components, use language: "jsx" or "tsx"
- Preserve exact formatting - do not modify the code in any way

IMPORTANT: Your response MUST match this exact JSON structure:
Note: Use "code_blocks" NOT "blocks" as the field name.
{
  "code_blocks": [
    {
      "code": "string (the actual code content)",
      "language": "string (programming language)",
      "title": "string (descriptive title)",
      "description": "string (comprehensive explanation)",
      "filename": "string or null (filename if mentioned)",
      "purpose": "string (one of: example, configuration, api_reference, tutorial, utility, test)",
      "frameworks": ["array of framework names"],
      "keywords": ["array of keywords"],
      "dependencies": ["array of dependencies"],
      "section": "string or null (documentation section)",
      "prerequisites": ["array of prerequisites"],
      "relationships": [
        {
          "related_index": "integer (index of related code block)",
          "relationship_type": "string (imports, extends, implements, uses, example_of, configuration_for)",
          "description": "string (how they are related)"
        }
      ]
    }
  ],
  "page_metadata": {
    "main_topic": "string (main topic of the page)",
    "page_type": "string (tutorial, api_reference, guide, quickstart, configuration)",
    "technologies": ["array of technologies"]
  },
  "key_concepts": ["array of key concepts"],
  "external_links": [
    {
      "url": "string",
      "title": "string",
      "description": "string"
    }
  ],
  "extraction_timestamp": "string or null (ISO timestamp)",
  "extraction_model": "string or null (model used)"
}

Respond with valid JSON only. Do NOT include any text before or after the JSON.


"""