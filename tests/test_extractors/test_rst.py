"""Tests for RSTCodeExtractor."""

import pytest

from src.crawler.extractors.rst import RSTCodeExtractor


class TestRSTCodeExtractor:
    """Test the RSTCodeExtractor."""
    
    def test_extract_code_block_directive(self):
        """Test extraction of code-block directives."""
        content = """
Installation
============

To install the package, run:

.. code-block:: python

    import package
    
    def install():
        package.setup()
        return True

This will set everything up.
"""
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        assert 'import package' in blocks[0].code
        assert 'def install():' in blocks[0].code
        assert blocks[0].language == 'python'
        assert 'To install the package, run:' in blocks[0].context.description
    
    def test_extract_literal_block(self):
        """Test extraction of literal blocks (::)."""
        content = """
Configuration
=============

Create a config file::

    {
        "host": "localhost",
        "port": 3000
    }

Save it as config.json.
"""
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        assert '"host": "localhost"' in blocks[0].code
        assert blocks[0].language is None  # Literal blocks don't specify language
    
    def test_skip_single_line_code(self):
        """Test that single-line code is skipped."""
        content = """
Usage
=====

Use the ``config.json`` file.

.. code:: bash

    echo "test"

The inline literal ``myfunction()`` is not extracted.
"""
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        # Single line should be skipped
        assert len(blocks) == 0
    
    def test_extract_multi_line_code(self):
        """Test extraction of multi-line code blocks."""
        content = """
Database Schema
===============

Define your schema:

.. code:: sql

    CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        price DECIMAL(10, 2)
    );

This creates the products table.
"""
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        assert 'CREATE TABLE products' in blocks[0].code
        assert blocks[0].language == 'sql'
    
    def test_underlined_headings(self):
        """Test different heading styles."""
        content = """
Main Title
==========

Content here.

.. code:: python

    def main():
        pass

Section Title
-------------

More content.

.. code:: python

    def section():
        return True
"""
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 2
        # First block should be under Main Title
        assert 'def main():' in blocks[0].code
        # Second block under Section Title
        assert 'def section():' in blocks[1].code
    
    def test_directive_content_extraction(self):
        """Test extraction of content from directives."""
        content = """
Important Notes
===============

.. note::
   
   This is an important note about the code.

.. code:: python

    def important():
        # Note applies here
        return True

.. warning::
   
   Be careful with this function.

The function is critical.
"""
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        desc = blocks[0].context.description
        # Note content should be included
        assert 'important note' in desc
    
    def test_filter_rst_references(self):
        """Test that RST references are filtered."""
        content = """
Documentation
=============

See the `API docs <https://example.com>`_ for details.

.. code:: python

    def api_call():
        return "result"

Check [#]_ for more info.
"""
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        desc = blocks[0].context.description
        
        # References should be cleaned
        assert 'API docs' in desc
        assert 'https://example.com' not in desc
        assert '[#]_' not in desc
    
    def test_multiple_blocks_under_heading(self):
        """Test multiple code blocks under same heading."""
        content = """
Setup Process
=============

First, install dependencies:

.. code:: bash

    pip install requests
    pip install flask

Then create your app:

.. code:: python

    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "Hello"

Finally, run it.
"""
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 2
        assert blocks[0].language == 'bash'
        assert blocks[1].language == 'python'
        
        # First block should mention dependencies
        assert 'install dependencies' in blocks[0].context.description
        
        # Second block should mention creating app
        assert 'create your app' in blocks[1].context.description
    
    def test_code_directive_with_options(self):
        """Test code directive with options."""
        content = """
Example
=======

Here's highlighted code:

.. code:: python
   :linenos:
   :emphasize-lines: 2,3
   
   def example():
       important_line1()
       important_line2()
       return True

The highlighted lines are key.
"""
        extractor = RSTCodeExtractor()
        blocks = extractor.extract_blocks(content)
        
        assert len(blocks) == 1
        assert 'def example():' in blocks[0].code
        # Options should be skipped, only code extracted
        assert ':linenos:' not in blocks[0].code