#!/usr/bin/env python3
"""Test the complete extraction with real Next.js example."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.crawler.html_code_extractor import HTMLCodeExtractor

def test_with_real_nextjs_html():
    """Test with a simulated Next.js HTML structure."""
    
    # Simulate the HTML structure from Next.js docs
    html_content = '''
    <div class="prose prose-vercel max-w-none">
        <article class="mt-4 w-full min-w-0 max-w-6xl px-1 md:px-6">
            <div class="relative code-block-module__NOThwW__wrapper not-prose">
                <pre><code>export async function getUserById(id: string) {
  const data = await fetch(`https://...`, {
    next: {
      tags: ['user'],
    },
  })
  return data
}</code></pre>
            </div>
        </article>
    </div>
    '''
    
    extractor = HTMLCodeExtractor()
    
    # Extract code blocks
    extracted_blocks = extractor.extract_code_blocks(html_content, "https://nextjs.org/docs/test")
    
    print("=== EXTRACTION RESULTS ===")
    print(f"Total blocks found: {len(extracted_blocks)}")
    
    for i, block in enumerate(extracted_blocks):
        print(f"\n--- Block {i+1} ---")
        print(f"Language: {block.language}")
        print(f"Code length: {len(block.code)}")
        print("Code preview:")
        print(block.code[:200] + "..." if len(block.code) > 200 else block.code)
        
    return extracted_blocks

if __name__ == '__main__':
    blocks = test_with_real_nextjs_html()
    
    if blocks and blocks[0].language in ['typescript', 'javascript']:
        print(f"\n✅ SUCCESS: Language detected as '{blocks[0].language}'")
        print("✅ This will now use jsbeautifier for formatting!")
    else:
        print(f"\n❌ FAILED: Language detected as '{blocks[0].language if blocks else 'None'}'")