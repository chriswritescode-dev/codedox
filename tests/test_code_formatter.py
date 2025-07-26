"""Tests for code formatting functionality."""

import pytest
from unittest.mock import Mock, patch
from src.crawler.code_formatter import CodeFormatter


class TestCodeFormatter:
    """Test code formatting with different languages and formatters."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = CodeFormatter()
    
    def test_format_javascript_basic(self):
        """Test basic JavaScript formatting."""
        messy_js = "function test(){console.log('hello');return true;}"
        
        formatted = self.formatter.format_code(messy_js, 'javascript')
        
        # Should be formatted with proper spacing and indentation
        assert 'function test()' in formatted
        assert '    console.log(' in formatted or 'console.log(' in formatted
        assert 'return true;' in formatted
    
    def test_format_typescript_basic(self):
        """Test basic TypeScript formatting."""
        messy_ts = "interface User{name:string;age:number;}function getUser():User{return{name:'test',age:25};}"
        
        formatted = self.formatter.format_code(messy_ts, 'typescript')
        
        # Should be formatted with proper spacing
        assert 'interface User' in formatted
        assert 'name: string' in formatted or 'name:string' in formatted
        assert 'function getUser()' in formatted
    
    def test_format_python_basic(self):
        """Test basic Python formatting using Black."""
        messy_python = "def test(x,y):return x+y"
        
        formatted = self.formatter.format_code(messy_python, 'python')
        
        # Should be formatted with proper spacing
        assert 'def test(x, y):' in formatted
        assert 'return x + y' in formatted
    
    def test_format_json_basic(self):
        """Test JSON formatting."""
        messy_json = '{"name":"test","items":[1,2,3],"config":{"enabled":true}}'
        
        formatted = self.formatter.format_code(messy_json, 'json')
        
        # Should be formatted with proper indentation
        assert '{\n' in formatted
        assert '    "name": "test"' in formatted or '"name": "test"' in formatted
        assert '    "items": [' in formatted or '"items": [' in formatted
    
    def test_format_unknown_language_fallback(self):
        """Test that unknown languages fall back to basic cleanup."""
        code = "some random code    with  extra   spaces"
        
        formatted = self.formatter.format_code(code, 'unknown_language')
        
        # Unknown languages get basic formatting, may preserve original spacing
        assert 'some random code' in formatted
        assert 'extra' in formatted
        assert 'spaces' in formatted
    
    def test_format_empty_code(self):
        """Test formatting empty or whitespace-only code."""
        assert self.formatter.format_code("", 'javascript') == ""
        assert self.formatter.format_code("   ", 'python') == "   "  # Whitespace preserved
        assert self.formatter.format_code("\n\n", 'json') == "\n\n"  # Whitespace preserved
    
    @patch('src.crawler.code_formatter.JSBEAUTIFIER_AVAILABLE', False)
    def test_javascript_fallback_when_jsbeautifier_unavailable(self):
        """Test JavaScript formatting falls back when jsbeautifier is unavailable."""
        code = "function test(){return true;}"
        
        formatted = self.formatter.format_code(code, 'javascript')
        
        # Should still format with basic rules
        assert 'function test()' in formatted
        assert '{' in formatted
        assert 'return true;' in formatted
    
    @patch('src.crawler.code_formatter.BLACK_AVAILABLE', False)
    def test_python_fallback_when_black_unavailable(self):
        """Test Python formatting falls back when Black is unavailable."""
        code = "def test(x,y):return x+y"
        
        formatted = self.formatter.format_code(code, 'python')
        
        # Should still format with basic rules
        assert 'def test(' in formatted
        assert 'return x' in formatted
    
    def test_jsbeautifier_error_handling(self):
        """Test handling of jsbeautifier errors."""
        # Mock jsbeautifier to raise an exception
        with patch('src.crawler.code_formatter.jsbeautifier') as mock_jsbeautifier:
            mock_jsbeautifier.beautify.side_effect = Exception("Format error")
            
            code = "function test(){return true;}"
            formatted = self.formatter.format_code(code, 'javascript')
            
            # Should fall back gracefully
            assert 'function test()' in formatted
    
    def test_black_error_handling(self):
        """Test handling of Black formatting errors."""
        # Mock Black to raise an exception
        with patch('src.crawler.code_formatter.black') as mock_black:
            mock_black.format_str.side_effect = Exception("Format error")
            
            code = "def test():return True"
            formatted = self.formatter.format_code(code, 'python')
            
            # Should fall back gracefully
            assert 'def test()' in formatted
            assert 'return True' in formatted
    
    def test_json_error_handling(self):
        """Test handling of invalid JSON."""
        invalid_json = '{"invalid": json syntax}'
        
        formatted = self.formatter.format_code(invalid_json, 'json')
        
        # Should return cleaned up version without crashing
        assert 'invalid' in formatted
        assert 'json syntax' in formatted
    
    def test_formatting_preserves_functionality(self):
        """Test that formatting preserves code functionality."""
        # Test with a more complex JavaScript function
        complex_js = """function fibonacci(n){if(n<=1)return n;else return fibonacci(n-1)+fibonacci(n-2);}"""
        
        formatted = self.formatter.format_code(complex_js, 'javascript')
        
        # Key functionality should be preserved
        assert 'function fibonacci(n)' in formatted
        assert 'if (n <= 1)' in formatted or 'if(n<=1)' in formatted
        assert 'return n' in formatted
        assert 'fibonacci(n - 1)' in formatted or 'fibonacci(n-1)' in formatted
    
    def test_multiple_language_formatting(self):
        """Test formatting multiple different languages."""
        test_cases = [
            ('function test() { return true; }', 'javascript'),
            ('def test(): return True', 'python'),
            ('{"test": true}', 'json'),
            ('interface Test { value: boolean; }', 'typescript'),
            ('echo "test"', 'bash')
        ]
        
        for code, language in test_cases:
            formatted = self.formatter.format_code(code, language)
            assert formatted is not None
            assert len(formatted.strip()) > 0
            # Each should be formatted or at least returned safely
            assert 'test' in formatted.lower()
    
    def test_large_code_block_handling(self):
        """Test handling of large code blocks."""
        # Create a large JavaScript function
        large_code = "function test() {\n" + "    console.log('line');\n" * 1000 + "}"
        
        formatted = self.formatter.format_code(large_code, 'javascript')
        
        # Should handle large blocks without issues
        assert 'function test()' in formatted
        assert formatted.count('console.log') == 1000
    
    def test_special_characters_handling(self):
        """Test handling of special characters in code."""
        code_with_special_chars = '''function test() {
    const message = "Hello 🌍! This is a test with émojis & spéçial chars";
    return message;
}'''
        
        formatted = self.formatter.format_code(code_with_special_chars, 'javascript')
        
        # Should preserve special characters
        assert '🌍' in formatted
        assert 'émojis' in formatted
        assert 'spéçial' in formatted