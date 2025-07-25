#!/usr/bin/env python3
"""Test the formatter with the specific Next.js code example."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.crawler.code_formatter import CodeFormatter

def test_nextjs_code():
    """Test with the specific Next.js getUserById code."""
    
    # This is the code you showed that's not formatting correctly
    nextjs_code = """export async function getUserById(id: string) {
const data = await fetch(`https://...`, {
next: {
tags: ['user'],
},
})
}"""
    
    formatter = CodeFormatter()
    formatted = formatter.format_code(nextjs_code, 'typescript')
    
    print("=== ORIGINAL NEXT.JS CODE ===")
    print(nextjs_code)
    print("\n=== FORMATTED WITH JSBEAUTIFIER ===")
    print(formatted)
    
    # Expected Prettier output would be something like:
    expected_prettier_like = """export async function getUserById(id: string) {
  const data = await fetch(`https://...`, {
    next: {
      tags: ['user'],
    },
  });
}"""
    
    print("\n=== EXPECTED PRETTIER-LIKE OUTPUT ===")
    print(expected_prettier_like)
    
    print(f"\n=== COMPARISON ===")
    print(f"Current formatter indents properly: {'✓' if '  const data' in formatted else '✗'}")
    print(f"Adds proper spacing: {'✓' if formatted.count('\\n') >= 6 else '✗'}")

if __name__ == '__main__':
    test_nextjs_code()