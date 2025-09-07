"""Factory for creating appropriate code extractors."""

import os

from .base import BaseCodeExtractor
from .html import HTMLCodeExtractor
from .markdown import MarkdownCodeExtractor
from .rst import RSTCodeExtractor


def create_extractor(file_path: str | None = None, content_type: str | None = None) -> BaseCodeExtractor | None:
    """
    Create appropriate extractor based on file extension or content type.
    
    Args:
        file_path: Optional file path to determine type from extension
        content_type: Optional explicit content type ('markdown', 'rst', 'html')
        
    Returns:
        Appropriate code extractor or None if type not supported
    """
    # Determine type from explicit content_type
    if content_type:
        content_type = content_type.lower()
        if content_type in ['markdown', 'md']:
            return MarkdownCodeExtractor()
        elif content_type in ['rst', 'restructuredtext']:
            return RSTCodeExtractor()
        elif content_type == 'html':
            return HTMLCodeExtractor()
    
    # Determine type from file extension
    if file_path:
        _, ext = os.path.splitext(file_path.lower())
        
        if ext in ['.md', '.markdown', '.mdx']:
            return MarkdownCodeExtractor()
        elif ext in ['.rst', '.rest']:
            return RSTCodeExtractor()
        elif ext in ['.html', '.htm']:
            return HTMLCodeExtractor()
    
    return None
