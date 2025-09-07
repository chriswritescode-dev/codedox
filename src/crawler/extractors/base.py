"""Abstract base class for all code extractors."""

from abc import ABC, abstractmethod

from .models import ExtractedCodeBlock, ExtractedContext
from .utils import filter_noise


class BaseCodeExtractor(ABC):
    """Abstract base class for all code extractors."""
    
    @abstractmethod
    def extract_blocks(self, content: str, source_url: str | None = None) -> list[ExtractedCodeBlock]:
        """
        Extract code blocks with semantic context.
        
        Args:
            content: The source content (markdown, rst, html, etc.)
            source_url: Optional URL of the source
            
        Returns:
            List of extracted code blocks with context
        """
        pass
    
    @abstractmethod
    def find_preceding_heading(self, content: str | list[str], position: int) -> tuple[str | None, int]:
        """
        Find the nearest preceding heading.
        
        Args:
            content: The content (string or lines)
            position: Current position (line number or character index)
            
        Returns:
            Tuple of (heading_text, heading_position)
        """
        pass
    
    @abstractmethod
    def extract_context_between(self, content: str | list[str], start: int, end: int) -> ExtractedContext:
        """
        Extract and clean context between two positions.
        
        Args:
            content: The content (string or lines)
            start: Start position
            end: End position
            
        Returns:
            Extracted context with title, description, etc.
        """
        pass
    
    def filter_noise(self, text: str, format_type: str) -> str:
        """
        Remove links, badges, navigation elements.
        
        Args:
            text: Text to clean
            format_type: Type of format ('markdown', 'rst', 'html')
            
        Returns:
            Cleaned text
        """
        return filter_noise(text, format_type)
    
    def should_extract_code_block(self, code_text: str) -> bool:
        """
        Determine if a code block should be extracted.
        
        Rules:
        - Always extract multi-line code blocks
        - Extract single-line code if it has 3+ words with each word being 3+ chars
        - Skip other single-line code blocks (they belong in descriptions)
        
        Args:
            code_text: The code text to evaluate
            
        Returns:
            True if should extract, False otherwise
        """
        if not code_text or not code_text.strip():
            return False
        
        # Multi-line code blocks are always extracted
        if '\n' in code_text:
            return True
        
        # Check for 3+ words of 3+ chars each in single-line code
        import re
        words = re.findall(r'\b\w+\b', code_text)
        
        # Count words that are 3+ chars
        significant_words = [w for w in words if len(w) >= 3]
        
        # Extract if we have 3+ significant words
        return len(significant_words) >= 3
