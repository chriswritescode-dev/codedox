#!/usr/bin/env python3
"""Simple test of markdown extraction without dependencies."""

import sys
sys.path.insert(0, '.')

# Import only the markdown extractor to avoid dependency issues
from src.crawler.markdown_code_extractor import MarkdownCodeExtractor

def test_extraction():
    extractor = MarkdownCodeExtractor()
    
    # Read test file
    with open('test_upload.md', 'r') as f:
        content = f.read()
    
    # Extract code blocks
    blocks = extractor.extract_code_blocks(content, 'test.md')
    
    print(f"Found {len(blocks)} code blocks")
    print(f"\nExtraction stats: {extractor.stats}")
    
    for i, block in enumerate(blocks):
        print(f"\nBlock {i+1}:")
        print(f"  Language: {block.language}")
        print(f"  Lines: {len(block.code.splitlines())}")
        print(f"  Method: {block.metadata.get('extraction_method')}")
        print(f"  Section: {block.metadata.get('section')}")
        if block.context_before:
            print(f"  Context before: {block.context_before[0][:50]}..." if block.context_before[0] else "")
        print(f"  First line: {block.code.splitlines()[0][:50]}..." if block.code else 'Empty')

if __name__ == "__main__":
    test_extraction()