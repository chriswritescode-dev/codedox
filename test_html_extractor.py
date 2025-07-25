#!/usr/bin/env python
"""Test HTML extraction directly without the full crawl flow"""

import asyncio
import json
from pathlib import Path
from crawl4ai import AsyncWebCrawler
from src.crawler.html_code_extractor import HTMLCodeExtractor
from src.crawler.config import create_browser_config


async def test_html_extraction(url: str):
    """Test HTML extraction on a specific URL."""
    print(f"\n{'='*60}")
    print(f"Testing HTML extraction for: {url}")
    print(f"{'='*60}\n")
    
    # Create browser config
    browser_config = create_browser_config(headless=True)
    
    # Create HTML extractor
    html_extractor = HTMLCodeExtractor()
    
    try:
        # Fetch the page
        async with AsyncWebCrawler(config=browser_config) as crawler:
            print("Fetching page...")
            result = await crawler.arun(url)
            
            if not result.success:
                print(f"Failed to fetch page: {result.error_message}")
                return
            
            print(f"Page fetched successfully. HTML length: {len(result.html)} chars")
            
            # Extract code blocks from HTML
            print("\nExtracting code blocks...")
            blocks = html_extractor.extract_code_blocks(result.html, url)
            
            if blocks:
                print(f"\nFound {len(blocks)} code blocks!")
                
                # Print formatted output
                debug_output = html_extractor.format_output(blocks)
                print("\n" + debug_output)
                
                # Save to JSON
                output_dir = Path("test_extraction_output")
                output_dir.mkdir(exist_ok=True)
                
                output_file = output_dir / f"{url.replace('/', '_').replace(':', '')}.json"
                
                # Convert blocks to JSON-serializable format
                blocks_data = []
                for block in blocks:
                    blocks_data.append({
                        "code": block.code,
                        "language": block.language,
                        "container_hierarchy": block.container_hierarchy,
                        "context_before": block.context_before,
                        "context_after": block.context_after,
                        "container_type": block.container_type,
                        "title": block.title,
                        "description": block.description,
                        "code_length": len(block.code),
                        "has_context": bool(block.context_before or block.context_after)
                    })
                
                # Convert sets to lists for JSON serialization
                stats = html_extractor.stats.copy()
                if 'languages_found' in stats:
                    stats['languages_found'] = list(stats['languages_found'])
                
                output_data = {
                    "url": url,
                    "total_blocks": len(blocks),
                    "blocks": blocks_data,
                    "stats": stats
                }
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                
                print(f"\nResults saved to: {output_file}")
                
            else:
                print("\nNo code blocks found.")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run tests on various documentation sites."""
    import sys
    
    # Get URLs from command line or use defaults
    if len(sys.argv) > 1:
        test_urls = sys.argv[1:]
    else:
        # Default test URLs
        test_urls = [
            "https://docs.python.org/3/tutorial/introduction.html",
            "https://nextjs.org/docs/getting-started/installation",
        ]
        print("No URLs provided. Using default test URLs.")
        print("Usage: python test_html_extractor.py <url1> <url2> ...\n")
    
    for url in test_urls:
        await test_html_extraction(url)
        print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    print("Starting HTML extraction test...")
    asyncio.run(main())