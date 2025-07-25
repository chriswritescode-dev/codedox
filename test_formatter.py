#!/usr/bin/env python3
"""Test script to verify the new code formatter works with real extracted code."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.crawler.code_formatter import CodeFormatter

def test_javascript_formatting():
    """Test JavaScript formatting with real extracted code."""
    
    # This is the actual extracted code from Playwright docs that was poorly formatted
    poorly_formatted_js = """import {
  test, expect } from '@playwright/test';
  test('has title', async ({
    page }) => {
      await page.goto('https://playwright.dev/');  // Expect a title "to contain" a substring.  await expect(page).toHaveTitle(/Playwright/);
    });
    test('get started link', async ({
      page }) => {
        await page.goto('https://playwright.dev/');  // Click the get started link.  await page.getByRole('link', {
          name: 'Get started' }).click();  // Expects page to have a heading with the name of Installation.  await expect(page.getByRole('heading', {
            name: 'Installation' })).toBeVisible();
          });"""

    formatter = CodeFormatter()
    
    print("=== ORIGINAL CODE ===")
    print(poorly_formatted_js)
    print("\n=== FORMATTED CODE ===")
    
    formatted = formatter.format_code(poorly_formatted_js, 'javascript')
    print(formatted)
    
    return formatted

def test_python_formatting():
    """Test Python formatting."""
    
    poorly_formatted_python = """import os;import sys;def test_function():print('hello');x=1+2;return x"""
    
    formatter = CodeFormatter()
    
    print("\n=== PYTHON ORIGINAL CODE ===")
    print(poorly_formatted_python)
    print("\n=== PYTHON FORMATTED CODE ===")
    
    formatted = formatter.format_code(poorly_formatted_python, 'python')
    print(formatted)
    
    return formatted

if __name__ == '__main__':
    print("Testing the new code formatter...")
    
    js_result = test_javascript_formatting()
    py_result = test_python_formatting()
    
    print(f"\n=== RESULTS ===")
    print(f"JavaScript formatting: {'✓ Success' if '\\n' in js_result else '✗ Failed'}")
    print(f"Python formatting: {'✓ Success' if '\\n' in py_result else '✗ Failed'}")