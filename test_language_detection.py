#!/usr/bin/env python3
"""Test script for VS Code language detection."""

import asyncio
import sys
import logging

# Suppress debug logging
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('blib2to3').setLevel(logging.WARNING)
logging.getLogger('src.crawler').setLevel(logging.INFO)

from src.crawler.vscode_language_detector import detect_language

# Test cases with different programming languages
TEST_CASES = [
    # Python
    {
        "code": """def factorial(n):
    if n == 0:
        return 1
    return n * factorial(n - 1)

print(factorial(5))""",
        "expected": "python"
    },
    # JavaScript
    {
        "code": """const greeting = (name) => {
    return `Hello, ${name}!`;
};

console.log(greeting('World'));""",
        "expected": "javascript"
    },
    # TypeScript
    {
        "code": """interface User {
    id: number;
    name: string;
    email: string;
}

function getUser(id: number): User {
    return { id, name: 'John', email: 'john@example.com' };
}""",
        "expected": "typescript"
    },
    # Java
    {
        "code": """public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}""",
        "expected": "java"
    },
    # Go
    {
        "code": """package main

import "fmt"

func main() {
    fmt.Println("Hello, World!")
}""",
        "expected": "go"
    },
    # Rust
    {
        "code": """fn main() {
    let message = "Hello, World!";
    println!("{}", message);
}""",
        "expected": "rust"
    },
    # SQL
    {
        "code": """SELECT u.name, u.email, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.created_at > '2023-01-01'
GROUP BY u.id, u.name, u.email
HAVING COUNT(o.id) > 5;""",
        "expected": "sql"
    },
    # HTML
    {
        "code": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Test Page</title>
</head>
<body>
    <h1>Hello, World!</h1>
</body>
</html>""",
        "expected": "html"
    },
    # CSS
    {
        "code": """.container {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px;
    background-color: #f0f0f0;
}

.container h1 {
    color: #333;
    font-size: 2rem;
}""",
        "expected": "css"
    },
    # Bash
    {
        "code": """#!/bin/bash

for file in *.txt; do
    echo "Processing $file"
    wc -l "$file"
done""",
        "expected": "shell"  # VS Code returns 'shellscript' or 'shell'
    }
]


async def test_language_detection():
    """Test VS Code language detection with various code samples."""
    print("Testing VS Code Language Detection")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\nTest {i}: Expected '{test_case['expected']}'")
        print("-" * 30)
        
        try:
            result = await detect_language(test_case['code'])
            
            if result.get('success'):
                top_result = result['topResult']
                detected = top_result['language']
                confidence = top_result['confidence']
                
                print(f"Detected: {detected} (confidence: {confidence:.3f})")
                
                # Check if detection matches expected (allowing for variations)
                expected_variations = {
                    'shell': ['shellscript', 'shell', 'bash', 'sh'],
                    'bash': ['shellscript', 'shell', 'bash', 'sh'],
                    'javascript': ['javascript', 'js'],
                    'typescript': ['typescript', 'ts'],
                    'python': ['python', 'py'],
                    'rust': ['rust', 'rs'],
                }
                
                expected = test_case['expected']
                valid_results = expected_variations.get(expected, [expected])
                
                if detected in valid_results:
                    print("✅ PASSED")
                    passed += 1
                else:
                    print(f"❌ FAILED - Expected one of {valid_results}")
                    failed += 1
                    
                # Show top 3 results
                if result.get('allResults'):
                    print("\nTop results:")
                    for j, res in enumerate(result['allResults'][:3], 1):
                        print(f"  {j}. {res['language']} ({res['confidence']:.3f})")
            else:
                print(f"❌ FAILED - Detection error: {result}")
                failed += 1
                
        except Exception as e:
            print(f"❌ FAILED - Exception: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return passed, failed


async def test_html_extractor():
    """Test the HTML code extractor with VS Code detection."""
    from src.crawler.html_code_extractor import HTMLCodeExtractor
    
    print("\n\nTesting HTML Code Extractor")
    print("=" * 50)
    
    extractor = HTMLCodeExtractor()
    
    # Test HTML with code blocks
    test_html = """
    <html>
    <body>
        <h2>Python Example</h2>
        <pre><code class="language-python">
def hello():
    print("Hello, World!")
    
hello()
        </code></pre>
        
        <h2>JavaScript Example</h2>
        <pre><code>
const add = (a, b) => a + b;
console.log(add(1, 2));
        </code></pre>
        
        <h2>SQL Query</h2>
        <pre>
SELECT * FROM users WHERE active = true;
        </pre>
    </body>
    </html>
    """
    
    blocks = await extractor.extract_code_blocks(test_html, "test.html")
    
    print(f"\nFound {len(blocks)} code blocks:")
    for i, block in enumerate(blocks, 1):
        print(f"\n{i}. Language: {block.language}")
        print(f"   Title: {block.title or 'N/A'}")
        print(f"   Code preview: {block.code[:50]}...")
        if block.context_before:
            print(f"   Context: {block.context_before[0][:50]}...")


if __name__ == "__main__":
    print("Starting language detection tests...\n")
    
    async def main():
        # Test direct language detection
        passed, failed = await test_language_detection()
        
        # Test HTML extractor
        await test_html_extractor()
        
        # Exit with error code if tests failed
        sys.exit(0 if failed == 0 else 1)
    
    asyncio.run(main())