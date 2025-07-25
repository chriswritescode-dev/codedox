#!/usr/bin/env python3
"""Test Pygments language detection with Next.js examples."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from pygments.lexers import guess_lexer

def test_nextjs_detection():
    """Test language detection with Next.js TypeScript code."""
    
    # The Next.js code that was failing detection
    nextjs_code = """export async function getUserById(id: string) {
const data = await fetch(`https://...`, {
next: {
tags: ['user'],
},
})
}"""
    
    try:
        lexer = guess_lexer(nextjs_code)
        detected_lang = lexer.name.lower()
        
        print("=== NEXT.JS CODE ===")
        print(nextjs_code)
        print(f"\nDetected language: {detected_lang}")
        print(f"Lexer class: {lexer.__class__.__name__}")
        
        # Test the mapping
        lang_mapping = {
            'javascript': 'javascript',
            'typescript': 'typescript', 
            'python': 'python',
        }
        
        final_lang = lang_mapping.get(detected_lang, detected_lang)
        print(f"Mapped language: {final_lang}")
        
        return final_lang
        
    except Exception as e:
        print(f"Detection failed: {e}")
        return None

def test_various_languages():
    """Test detection with various programming languages."""
    
    test_cases = [
        ("Python", "def calculate(x, y):\n    return x + y"),
        ("JavaScript", "function calculate(x, y) { return x + y; }"),
        ("TypeScript", "function calculate(x: number, y: number): number { return x + y; }"),
        ("JSON", '{"name": "test", "value": 123}'),
        ("Bash", "#!/bin/bash\necho 'Hello World'")
    ]
    
    print("\n=== TESTING VARIOUS LANGUAGES ===")
    for expected, code in test_cases:
        try:
            lexer = guess_lexer(code)
            detected = lexer.name
            print(f"{expected:10} -> {detected:15} ({'✓' if expected.lower() in detected.lower() else '✗'})")
        except Exception as e:
            print(f"{expected:10} -> ERROR: {e}")

if __name__ == '__main__':
    nextjs_result = test_nextjs_detection()
    test_various_languages()
    
    print(f"\n=== RESULT ===")
    print(f"Next.js detection successful: {'✓' if nextjs_result else '✗'}")
    if nextjs_result in ['javascript', 'typescript']:
        print("✓ Will use jsbeautifier for formatting!")