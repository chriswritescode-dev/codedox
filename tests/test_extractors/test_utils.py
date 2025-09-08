"""Tests for extractor utilities."""

import pytest

from src.crawler.extractors.utils import (
    extract_frontmatter,
    filter_noise,
    is_navigation_text,
    remove_badges,
    remove_html_comments,
    remove_markdown_images,
    remove_markdown_links,
    remove_rst_references,
)


class TestExtractorUtils:
    """Test utility functions for extractors."""
    
    def test_remove_markdown_links(self):
        """Test removal of markdown links."""
        text = "Check the [documentation](https://docs.com) and [API guide](https://api.com)."
        result = remove_markdown_links(text)
        assert result == "Check the documentation and API guide."
        
        # Test reference-style links
        text = "See [this][ref1] and [that][ref2]."
        result = remove_markdown_links(text)
        assert result == "See this and that."
    
    def test_remove_markdown_images(self):
        """Test removal of markdown images."""
        text = "Here's a ![logo](logo.png) and ![](banner.jpg) image."
        result = remove_markdown_images(text)
        assert result == "Here's a  and  image."
    
    def test_remove_html_comments(self):
        """Test removal of HTML comments."""
        text = "Text <!-- comment --> more <!-- another\nmultiline\ncomment --> text."
        result = remove_html_comments(text)
        assert result == "Text  more  text."
    
    def test_remove_badges(self):
        """Test removal of badge URLs."""
        text = "[![Build](https://shields.io/badge/build-passing.svg)](link)"
        result = remove_badges(text)
        # Should remove shield.io URLs
        assert "shields.io" not in result
    
    def test_remove_rst_references(self):
        """Test removal of RST references."""
        text = "See the `documentation <https://docs.com>`_ for details."
        result = remove_rst_references(text)
        assert result == "See the documentation for details."
        
        # Test footnotes
        text = "This is important[#]_ and see [1]_ for more."
        result = remove_rst_references(text)
        assert result == "This is important and see  for more."
    
    def test_is_navigation_text(self):
        """Test navigation text detection."""
        assert is_navigation_text("Previous")
        assert is_navigation_text("next")
        assert is_navigation_text("Back to index")
        assert is_navigation_text("<<")
        assert is_navigation_text("→")
        assert not is_navigation_text("This is content")
        assert not is_navigation_text("Previous versions show")
    
    def test_filter_noise_markdown(self):
        """Test comprehensive noise filtering for markdown."""
        text = """
        Check [docs](https://docs.com) and ![logo](logo.png).
        <!-- comment -->
        [![badge](https://shields.io/badge.svg)](link)
        
        Previous
        
        Real content here.
        """
        result = filter_noise(text, 'markdown')
        
        assert "docs.com" not in result
        assert "logo.png" not in result
        assert "comment" not in result
        assert "shields.io" not in result
        assert "Previous" not in result  # Navigation removed
        assert "Real content here" in result
    
    def test_filter_noise_rst(self):
        """Test comprehensive noise filtering for RST."""
        text = """
        See `docs <https://docs.com>`_ here.
        Reference [#]_ for details.
        
        .. toctree::
           :maxdepth: 2
           
        .. note:: This is important.
        
        Real content.
        """
        result = filter_noise(text, 'rst')
        
        assert "docs.com" not in result
        assert "[#]" not in result
        assert "toctree" not in result
        assert "This is important" in result  # Note content kept
        assert "Real content" in result
    
    def test_extract_frontmatter_yaml(self):
        """Test YAML frontmatter extraction."""
        content = """---
title: My Page
author: John
---

# Content

This is the content."""
        
        frontmatter, remaining = extract_frontmatter(content)
        
        assert "---" not in remaining
        assert "title: My Page" not in remaining
        assert "# Content" in remaining
        assert "This is the content" in remaining
    
    def test_extract_frontmatter_toml(self):
        """Test TOML frontmatter extraction."""
        content = """+++
title = "My Page"
author = "John"
+++

# Content

This is the content."""
        
        frontmatter, remaining = extract_frontmatter(content)
        
        assert "+++" not in remaining
        assert 'title = "My Page"' not in remaining
        assert "# Content" in remaining
    
    def test_extract_frontmatter_none(self):
        """Test when there's no frontmatter."""
        content = """# Content

This is the content."""
        
        frontmatter, remaining = extract_frontmatter(content)
        
        assert remaining == content