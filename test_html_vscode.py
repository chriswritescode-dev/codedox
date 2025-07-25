#!/usr/bin/env python3
"""Test HTML extractor with VS Code detection."""

import asyncio
import logging

# Set up logging to see errors
logging.basicConfig(level=logging.DEBUG)

from src.crawler.html_code_extractor import HTMLCodeExtractor

async def test_html_extractor():
    """Test HTML extractor with VS Code detection."""
    
    # Simple HTML with Python code
    html = """
    <html>
    <body>
        <pre><code>
def hello():
    print("Hello, World!")
        </code></pre>
    </body>
    </html>
    """
    
    print("Testing HTML Extractor with VS Code Detection")
    print("=" * 50)
    
    try:
        extractor = HTMLCodeExtractor()
        blocks = await extractor.extract_code_blocks(html, "test.html")
        
        print(f"Found {len(blocks)} blocks")
        for i, block in enumerate(blocks):
            print(f"\nBlock {i+1}:")
            print(f"  Language: {block.language}")
            print(f"  Code: {block.code[:50]}...")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_html_extractor())