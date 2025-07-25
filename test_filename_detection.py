#!/usr/bin/env python3
"""Test filename-based language detection."""

import asyncio
import logging

# Set up logging to see debug messages
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

from src.crawler.html_code_extractor import HTMLCodeExtractor

async def test_filename_detection():
    """Test filename-based language detection."""
    
    # Test cases with filenames in different HTML patterns
    test_cases = [
        # Filename in a div with class
        {
            "name": "Filename in div.filename",
            "html": """
            <div class="code-example">
                <div class="filename">app/page.tsx</div>
                <pre><code>
export default function HomePage() {
  return <h1>Welcome</h1>
}
                </code></pre>
            </div>
            """,
            "expected": "typescript"
        },
        # Filename in data attribute
        {
            "name": "Filename in data attribute",
            "html": """
            <div data-filename="src/main.py">
                <pre><code>
def main():
    print("Hello")
                </code></pre>
            </div>
            """,
            "expected": "python"
        },
        # Filename in title attribute
        {
            "name": "Filename in title attribute",
            "html": """
            <div title="package.json">
                <pre><code>
{
  "name": "my-app",
  "version": "1.0.0"
}
                </code></pre>
            </div>
            """,
            "expected": "json"
        },
        # Dockerfile special case
        {
            "name": "Dockerfile",
            "html": """
            <div class="code-block">
                <span class="code-title">Dockerfile</span>
                <pre><code>
FROM node:18
WORKDIR /app
COPY . .
RUN npm install
                </code></pre>
            </div>
            """,
            "expected": "dockerfile"
        },
        # Makefile special case
        {
            "name": "Makefile",
            "html": """
            <div>
                <div class="file-name">Makefile</div>
                <pre><code>
all: build

build:
	gcc -o app main.c
                </code></pre>
            </div>
            """,
            "expected": "makefile"
        },
        # Go mod file
        {
            "name": "go.mod",
            "html": """
            <div>
                <code class="filename">go.mod</code>
                <pre><code>
module example.com/myapp

go 1.21

require github.com/gin-gonic/gin v1.9.1
                </code></pre>
            </div>
            """,
            "expected": "go"
        },
        # Rust file
        {
            "name": "Rust file",
            "html": """
            <div>
                <p>src/main.rs</p>
                <pre><code>
fn main() {
    println!("Hello, world!");
}
                </code></pre>
            </div>
            """,
            "expected": "rust"
        },
        # Shell script
        {
            "name": "Shell script",
            "html": """
            <div>
                <span class="filename">deploy.sh</span>
                <pre><code>
#!/bin/bash
echo "Deploying..."
docker build -t myapp .
                </code></pre>
            </div>
            """,
            "expected": "shell"
        },
        # No filename - should use VS Code detection
        {
            "name": "No filename - VS Code detection",
            "html": """
            <pre><code>
import React from 'react'

export const Button = ({ children }) => {
  return <button>{children}</button>
}
                </code></pre>
            """,
            "expected": "typescript"  # VS Code correctly detects JSX as TypeScript
        }
    ]
    
    print("Testing Filename-Based Language Detection")
    print("=" * 60)
    
    extractor = HTMLCodeExtractor()
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        print("-" * 40)
        
        try:
            blocks = await extractor.extract_code_blocks(test['html'], "test.html")
            
            if blocks:
                block = blocks[0]
                print(f"  Detected language: {block.language}")
                print(f"  Expected language: {test['expected']}")
                print(f"  Match: {'✓' if block.language == test['expected'] else '✗'}")
                
                # The filename was already extracted during processing
            else:
                print("  No code blocks found!")
                
        except Exception as e:
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Test completed")

if __name__ == "__main__":
    asyncio.run(test_filename_detection())