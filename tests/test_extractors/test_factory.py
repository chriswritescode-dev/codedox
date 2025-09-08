"""Tests for extractor factory."""

import pytest

from src.crawler.extractors.factory import create_extractor
from src.crawler.extractors.html import HTMLCodeExtractor
from src.crawler.extractors.markdown import MarkdownCodeExtractor
from src.crawler.extractors.rst import RSTCodeExtractor


class TestExtractorFactory:
    """Test the extractor factory."""
    
    def test_create_markdown_extractor_by_type(self):
        """Test creating Markdown extractor by content type."""
        extractor = create_extractor(content_type='markdown')
        assert isinstance(extractor, MarkdownCodeExtractor)
        
        extractor = create_extractor(content_type='md')
        assert isinstance(extractor, MarkdownCodeExtractor)
    
    def test_create_rst_extractor_by_type(self):
        """Test creating RST extractor by content type."""
        extractor = create_extractor(content_type='rst')
        assert isinstance(extractor, RSTCodeExtractor)
        
        extractor = create_extractor(content_type='restructuredtext')
        assert isinstance(extractor, RSTCodeExtractor)
    
    def test_create_html_extractor_by_type(self):
        """Test creating HTML extractor by content type."""
        extractor = create_extractor(content_type='html')
        assert isinstance(extractor, HTMLCodeExtractor)
    
    def test_create_markdown_extractor_by_extension(self):
        """Test creating Markdown extractor by file extension."""
        extractor = create_extractor(file_path='README.md')
        assert isinstance(extractor, MarkdownCodeExtractor)
        
        extractor = create_extractor(file_path='doc.markdown')
        assert isinstance(extractor, MarkdownCodeExtractor)
        
        extractor = create_extractor(file_path='component.mdx')
        assert isinstance(extractor, MarkdownCodeExtractor)
    
    def test_create_rst_extractor_by_extension(self):
        """Test creating RST extractor by file extension."""
        extractor = create_extractor(file_path='index.rst')
        assert isinstance(extractor, RSTCodeExtractor)
        
        extractor = create_extractor(file_path='api.rest')
        assert isinstance(extractor, RSTCodeExtractor)
    
    def test_create_html_extractor_by_extension(self):
        """Test creating HTML extractor by file extension."""
        extractor = create_extractor(file_path='index.html')
        assert isinstance(extractor, HTMLCodeExtractor)
        
        extractor = create_extractor(file_path='page.htm')
        assert isinstance(extractor, HTMLCodeExtractor)
    
    def test_case_insensitive(self):
        """Test that file extensions are case insensitive."""
        extractor = create_extractor(file_path='README.MD')
        assert isinstance(extractor, MarkdownCodeExtractor)
        
        extractor = create_extractor(content_type='HTML')
        assert isinstance(extractor, HTMLCodeExtractor)
    
    def test_unknown_type_returns_none(self):
        """Test that unknown types return None."""
        extractor = create_extractor(content_type='unknown')
        assert extractor is None
        
        extractor = create_extractor(file_path='file.xyz')
        assert extractor is None
    
    def test_content_type_overrides_file_path(self):
        """Test that explicit content_type overrides file extension."""
        # File says .md but content_type says html
        extractor = create_extractor(file_path='README.md', content_type='html')
        assert isinstance(extractor, HTMLCodeExtractor)