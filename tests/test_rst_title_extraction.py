"""Tests for RST title extraction functionality."""

import pytest

from src.api.routes.upload_utils import TitleExtractor


class TestRSTTitleExtraction:
    """Test RST title extraction from content."""

    def test_extract_rst_title_with_overline_and_underline(self):
        """Test extraction of RST title with both overline and underline."""
        content = """==================
RST Test Document
==================

This is a test RST document.
        """
        
        title = TitleExtractor.extract_from_content(content)
        assert title == "RST Test Document"

    def test_extract_rst_title_with_underline_only(self):
        """Test extraction of RST title with underline only."""
        content = """RST Test Document
==================

This is a test RST document.
        """
        
        title = TitleExtractor.extract_from_content(content)
        assert title == "RST Test Document"

    def test_extract_rst_title_with_different_markers(self):
        """Test extraction of RST title with different underline markers."""
        # Test with dashes
        content1 = """My Title
--------

Some content.
        """
        assert TitleExtractor.extract_from_content(content1) == "My Title"
        
        # Test with tildes
        content2 = """Another Title
~~~~~~~~~~~~~

Some content.
        """
        assert TitleExtractor.extract_from_content(content2) == "Another Title"

    def test_extract_markdown_title_still_works(self):
        """Test that markdown title extraction still works."""
        content = """# Markdown Title

This is a markdown document.
        """
        
        title = TitleExtractor.extract_from_content(content)
        assert title == "Markdown Title"

    def test_extract_markdown_title_takes_precedence(self):
        """Test that markdown title takes precedence if both formats present."""
        content = """# Markdown Title

RST Style Title
===============

This document has both.
        """
        
        title = TitleExtractor.extract_from_content(content)
        assert title == "Markdown Title"

    def test_no_title_found(self):
        """Test when no title is found."""
        content = """This is just regular text.
No title here.
        """
        
        title = TitleExtractor.extract_from_content(content)
        assert title is None

    def test_rst_title_with_max_lines_limit(self):
        """Test RST title extraction respects max_lines parameter."""
        content = """Some preamble text
More preamble

Actual Title
============

Content here.
        """
        
        # With default max_lines (10), should find the title
        title = TitleExtractor.extract_from_content(content)
        assert title == "Actual Title"
        
        # With max_lines=2, should not find the title
        title = TitleExtractor.extract_from_content(content, max_lines=2)
        assert title is None

    def test_resolve_with_rst_content(self):
        """Test the resolve method with RST content."""
        content = """Documentation Title
===================

Some content.
        """
        
        # Without explicit title, should extract from content
        title = TitleExtractor.resolve(None, content, "upload://test/untitled.rst")
        assert title == "Documentation Title"
        
        # With explicit title, should use that
        title = TitleExtractor.resolve("Explicit Title", content, "upload://test/untitled.rst")
        assert title == "Explicit Title"
        
        # Without title in content, should use URL
        no_title_content = "Just some text"
        title = TitleExtractor.resolve(None, no_title_content, "upload://test/my_document.rst")
        assert title == "my_document"