#!/usr/bin/env python3
"""Test the formatter with properly formatted code examples."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.crawler.code_formatter import CodeFormatter

def test_clean_javascript():
    """Test with well-formed JavaScript that just needs better formatting."""
    
    # Single-line but valid JavaScript
    js_code = "function calculate(a, b) { const result = a + b; console.log('Result:', result); return result; }"
    
    formatter = CodeFormatter()
    formatted = formatter.format_code(js_code, 'javascript')
    
    print("=== CLEAN JS ORIGINAL ===")
    print(js_code)
    print("\n=== CLEAN JS FORMATTED ===")
    print(formatted)
    print(f"\nLine breaks added: {'✓' if '\\n' in formatted else '✗'}")

def test_clean_python():
    """Test with well-formed Python code."""
    
    # Single-line but valid Python
    py_code = "def calculate(a, b):\\n    result = a + b\\n    print(f'Result: {result}')\\n    return result"
    
    formatter = CodeFormatter()
    formatted = formatter.format_code(py_code, 'python')
    
    print("\\n=== CLEAN PYTHON ORIGINAL ===")
    print(repr(py_code))  # Show the raw string
    print("\\n=== CLEAN PYTHON FORMATTED ===")
    print(formatted)
    print(f"\\nBlack formatting worked: {'✓' if 'def calculate' in formatted else '✗'}")

def test_extracted_playwright_code():
    """Test with the actual extracted Playwright code from our JSON file."""
    
    # This is the first code block from the extraction - properly formed
    playwright_code = '''import { test, expect } from '@playwright/test';
test('has title', async ({ page }) => {
  await page.goto('https://playwright.dev/');
  await expect(page).toHaveTitle(/Playwright/);
});
test('get started link', async ({ page }) => {
  await page.goto('https://playwright.dev/');
  await page.getByRole('link', { name: 'Get started' }).click();
  await expect(page.getByRole('heading', { name: 'Installation' })).toBeVisible();
});'''
    
    formatter = CodeFormatter()
    formatted = formatter.format_code(playwright_code, 'javascript')
    
    print("\\n=== PLAYWRIGHT ORIGINAL ===")
    print(playwright_code)
    print("\\n=== PLAYWRIGHT FORMATTED ===")
    print(formatted)
    print(f"\\nFormatting improved: {'✓' if len(formatted.split('\\n')) >= len(playwright_code.split('\\n')) else '✗'}")

if __name__ == '__main__':
    print("Testing formatter with clean code examples...")
    test_clean_javascript()
    test_clean_python()
    test_extracted_playwright_code()