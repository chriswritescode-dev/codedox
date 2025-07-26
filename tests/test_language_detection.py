"""Tests for language detection functionality."""

import pytest
from bs4 import BeautifulSoup
from src.crawler.html_code_extractor import HTMLCodeExtractor


class TestLanguageDetection:
    """Test pattern-based language detection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = HTMLCodeExtractor()
    
    def test_detect_typescript(self):
        """Test TypeScript detection patterns."""
        typescript_patterns = [
            "const name: string = 'test';",
            "let count: number = 42;",
            "interface User { id: number; }",
            "type Status = 'active' | 'inactive';",
            "function getName(): string { return 'test'; }",
            "const isReady: boolean = true;",
        ]
        
        for code in typescript_patterns:
            element = BeautifulSoup(f"<code>{code}</code>", 'html.parser').find('code')
            language = self.extractor._detect_language(element)
            assert language == 'typescript', f"Failed to detect TypeScript in: {code}"
    
    def test_detect_javascript(self):
        """Test JavaScript detection patterns."""
        javascript_patterns = [
            "function calculate() { return 42; }",
            "const result = getValue();",
            "let items = [];",
            "var config = {};",
            "export default MyComponent;",
            "import React from 'react';",
            "const arrow = () => true;",
        ]
        
        for code in javascript_patterns:
            element = BeautifulSoup(f"<code>{code}</code>", 'html.parser').find('code')
            language = self.extractor._detect_language(element)
            assert language == 'javascript', f"Failed to detect JavaScript in: {code}"
    
    def test_detect_python(self):
        """Test Python detection patterns."""
        python_patterns = [
            "def calculate(): return 42",
            "class User: pass", 
            "if __name__ == '__main__':",
        ]
        
        for code in python_patterns:
            element = BeautifulSoup(f"<code>{code}</code>", 'html.parser').find('code')
            language = self.extractor._detect_language(element)
            assert language == 'python', f"Failed to detect Python in: {code}"
    
    def test_detect_bash(self):
        """Test Bash/Shell detection patterns."""
        bash_patterns = [
            "#!/bin/bash\necho 'hello'",
            "#!/bin/sh\nls -la", 
            "echo $HOME && ls",
        ]
        
        for code in bash_patterns:
            element = BeautifulSoup(f"<code>{code}</code>", 'html.parser').find('code')
            language = self.extractor._detect_language(element)
            assert language == 'bash', f"Failed to detect Bash in: {code}"
    
    def test_detect_json(self):
        """Test JSON detection patterns."""
        json_patterns = [
            '{"name": "test", "version": "1.0"}',
            '{"config": {"enabled": true}}',
            '{"items": [1, 2, 3]}',
        ]
        
        for code in json_patterns:
            element = BeautifulSoup(f"<code>{code}</code>", 'html.parser').find('code')
            language = self.extractor._detect_language(element)
            assert language == 'json', f"Failed to detect JSON in: {code}"
    
    def test_detect_html(self):
        """Test HTML detection patterns.""" 
        html_patterns = [
            "&lt;div&gt;Hello World&lt;/div&gt;",
            "&lt;html&gt;&lt;head&gt;&lt;title&gt;Test&lt;/title&gt;&lt;/head&gt;&lt;/html&gt;",
            "&lt;p&gt;Content&lt;/p&gt;",
        ]
        
        for code in html_patterns:
            element = BeautifulSoup(f"<code>{code}</code>", 'html.parser').find('code')
            language = self.extractor._detect_language(element)
            assert language == 'html', f"Failed to detect HTML in: {code}"
    
    def test_detect_css(self):
        """Test CSS detection patterns."""
        css_patterns = [
            ".container { display: flex; }",
            "#main { color: red; }",
            "body { margin: 0; padding: 0; }",
        ]
        
        for code in css_patterns:
            element = BeautifulSoup(f"<code>{code}</code>", 'html.parser').find('code')
            language = self.extractor._detect_language(element)
            assert language == 'css', f"Failed to detect CSS in: {code}"
    
    
    def test_priority_order_typescript_over_javascript(self):
        """Test that TypeScript is detected over JavaScript when both patterns exist."""
        mixed_code = "const name: string = 'test'; function test() { return true; }"
        element = BeautifulSoup(f"<code>{mixed_code}</code>", 'html.parser').find('code')
        language = self.extractor._detect_language(element)
        
        # TypeScript should take priority due to type annotation
        assert language == 'typescript'
    
    def test_priority_order_bash_over_javascript(self):
        """Test that Bash is detected over JavaScript when 'export' appears in shell context."""
        bash_export = "#!/bin/bash\nexport NODE_ENV=production"
        element = BeautifulSoup(f"<code>{bash_export}</code>", 'html.parser').find('code')
        language = self.extractor._detect_language(element)
        
        # Should detect as bash due to shebang
        assert language == 'bash'
    
    def test_unknown_language_returns_text(self):
        """Test that unknown code patterns return 'text'."""
        unknown_patterns = [
            "some random text without programming patterns that is long enough",
            "Lorem ipsum dolor sit amet consectetur adipiscing elit",
        ]
        
        for code in unknown_patterns:
            element = BeautifulSoup(f"<code>{code}</code>", 'html.parser').find('code')
            language = self.extractor._detect_language(element)
            assert language == 'text', f"Should detect as text for: {code}"
    
    def test_short_code_returns_none(self):
        """Test that very short code snippets return None."""
        short_patterns = [
            "x",
            "42", 
            "def",
            "{}",
            "[]",
        ]
        
        for code in short_patterns:
            element = BeautifulSoup(f"<code>{code}</code>", 'html.parser').find('code')
            language = self.extractor._detect_language(element)
            assert language is None, f"Should not detect language for short code: {code}"
    
    def test_complex_mixed_content(self):
        """Test language detection in complex mixed content."""
        # JavaScript with embedded JSON
        js_with_json = '''
        const config = {
            "api": {
                "endpoint": "https://api.example.com"
            }
        };
        function loadConfig() {
            return config;
        }
        '''
        element = BeautifulSoup(f"<code>{js_with_json}</code>", 'html.parser').find('code')
        language = self.extractor._detect_language(element)
        assert language == 'javascript'  # Should detect as JS due to function keyword
    
    def test_case_insensitive_detection(self):
        """Test that language detection is case insensitive."""
        patterns = [
            ("function test() { return true; }", 'javascript'),
            ("def calculate(): return 42", 'python'),
        ]
        
        for code, expected_lang in patterns:
            element = BeautifulSoup(f"<code>{code}</code>", 'html.parser').find('code')
            language = self.extractor._detect_language(element)
            assert language == expected_lang, f"Case insensitive detection failed for: {code}"
    
    def test_multiline_code_detection(self):
        """Test language detection in multiline code blocks."""
        multiline_python = '''
        class UserManager:
            def __init__(self):
                self.users = []
            
            def add_user(self, user):
                self.users.append(user)
                return True
        '''
        element = BeautifulSoup(f"<code>{multiline_python}</code>", 'html.parser').find('code')
        language = self.extractor._detect_language(element)
        assert language == 'python'
    
    def test_detect_with_comments(self):
        """Test language detection works with code comments."""
        patterns = [
            ("// This is a comment\nfunction test() { return true; }", 'javascript'),
            ("# This is a comment\ndef test(): return True", 'python'),
            ("#menu { color: red; }", 'css'),
        ]
        
        for code, expected_lang in patterns:
            element = BeautifulSoup(f"<code>{code}</code>", 'html.parser').find('code')
            language = self.extractor._detect_language(element)
            assert language == expected_lang, f"Comment detection failed for: {code}"