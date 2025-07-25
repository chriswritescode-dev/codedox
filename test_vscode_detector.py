#!/usr/bin/env python3
"""Test VS Code language detector directly."""

import asyncio
from src.crawler.vscode_language_detector import detect_language, get_detector

async def test_detector():
    """Test the VS Code language detector."""
    
    # Test simple Python code
    code = """def hello():
    print("Hello, World!")"""
    
    print("Testing VS Code Language Detector")
    print("=" * 40)
    
    try:
        # Get detector instance
        detector = await get_detector()
        print("✓ Detector initialized")
        
        # Test detection
        result = await detect_language(code)
        print(f"✓ Detection result: {result}")
        
        if result.get('success'):
            print(f"✓ Language: {result['topResult']['language']}")
            print(f"✓ Confidence: {result['topResult']['confidence']}")
        else:
            print(f"✗ Detection failed: {result}")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_detector())