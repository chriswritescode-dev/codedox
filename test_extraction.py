#!/usr/bin/env python
"""Test HTML extraction for z-index page."""

import asyncio
from src.crawler.html_code_extractor import HTMLCodeExtractor

# Sample HTML from z-index page
html_sample = """
<div class="prose">
    <p>Prefix a <code>z-index</code> utility with a breakpoint variant like <code>md:</code> to only apply the utility at medium screen sizes and above:</p>
    <pre><code>&lt;div class="z-0 md:z-50 ..."&gt;  &lt;!-- ... --&gt;&lt;/div&gt;</code></pre>
</div>
"""

async def test():
    extractor = HTMLCodeExtractor()
    blocks = await extractor.extract_code_blocks_async(html_sample, "https://tailwindcss.com/docs/z-index")
    
    for i, block in enumerate(blocks):
        print(f"\n=== Block {i+1} ===")
        print(f"Code: {block.code}")
        print(f"Language: {block.language}")
        print(f"Context before: {block.context_before}")
        print(f"Title: {block.title}")
        print(f"Description: {block.description}")

if __name__ == "__main__":
    asyncio.run(test())