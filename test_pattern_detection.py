#!/usr/bin/env python3
"""Test pattern-based language detection."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def detect_language_patterns(code_text):
    """Implement the same logic as the new _detect_language method."""
    if not code_text or len(code_text.strip()) < 10:
        return None
    
    # Use simple but reliable pattern matching
    code_lower = code_text.lower()
    
    # TypeScript/JavaScript patterns
    if any(pattern in code_text for pattern in [': string', ': number', ': boolean', 'interface ', 'type ']):
        return 'typescript'
    elif any(pattern in code_text for pattern in ['function ', 'const ', 'let ', 'var ', '=>', 'export ', 'import ']):
        return 'javascript'
    
    # Python patterns
    elif any(pattern in code_text for pattern in ['def ', 'import ', 'from ', 'class ', 'if __name__']):
        return 'python'
    
    # JSON pattern
    elif code_text.strip().startswith('{') and code_text.strip().endswith('}') and '"' in code_text:
        return 'json'
    
    # Shell/Bash patterns
    elif any(pattern in code_text for pattern in ['#!/bin/bash', '#!/bin/sh', 'echo ', 'export ', '${']):
        return 'bash'
    
    # HTML patterns
    elif any(pattern in code_lower for pattern in ['<html', '<div', '<span', '<p>', '</div>', '</html>']):
        return 'html'
    
    # CSS patterns
    elif any(pattern in code_text for pattern in ['{', '}', ': ', ';']) and any(prop in code_lower for prop in ['color:', 'margin:', 'padding:', 'display:']):
        return 'css'
    
    # Default to text if no patterns match
    return 'text'

def test_nextjs_detection():
    """Test with Next.js examples."""
    
    test_cases = [
        ("TypeScript with types", """export async function getUserById(id: string) {
const data = await fetch(`https://...`, {
next: {
tags: ['user'],
},
})
}"""),
        ("JavaScript ES6", """export async function getUserById(id) {
const data = await fetch(`https://...`, {
next: {
tags: ['user'],
},
})
}"""),
        ("Python function", """def get_user_by_id(user_id):
    return db.query('SELECT * FROM users WHERE id = ?', user_id)"""),
        ("JSON data", """{"name": "test", "value": 123, "active": true}"""),
        ("Bash script", """#!/bin/bash
echo "Hello World"
export PATH="/usr/local/bin:$PATH\""""),
    ]
    
    print("=== PATTERN-BASED DETECTION TEST ===")
    for name, code in test_cases:
        detected = detect_language_patterns(code)
        print(f"{name:20} -> {detected}")
        print(f"Code preview: {code[:50]}...")
        print()

if __name__ == '__main__':
    test_nextjs_detection()