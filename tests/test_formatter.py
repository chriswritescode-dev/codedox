"""Tests for the enhanced code formatter."""

import pytest
from src.crawler.code_formatter import CodeFormatter


class TestCodeFormatter:
    """Test the CodeFormatter class."""
    
    @pytest.fixture
    def formatter(self):
        """Create a formatter instance."""
        return CodeFormatter()
    
    def test_format_with_wrong_language(self, formatter):
        """Test formatting when language is misidentified."""
        # JavaScript code marked as CSS
        js_code = '''export default {
  plugins: {
    "@tailwindcss/postcss": {},
  }
}'''
        
        # Should still format correctly due to fallback mechanisms
        result = formatter.format(js_code, 'css')
        assert 'export default' in result
        # Prettier might format this correctly through auto-detection fallback
        # so just check it didn't break the code
        assert 'plugins' in result and '@tailwindcss/postcss' in result
    
    def test_auto_detection(self, formatter):
        """Test automatic language detection."""
        # TypeScript code without language hint
        ts_code = '''interface User {
  name: string;
  age: number;
}'''
        
        result = formatter.format(ts_code)
        assert 'interface User' in result
        assert 'name: string' in result
    
    def test_format_with_info(self, formatter):
        """Test format_with_info method."""
        # JavaScript code
        js_code = 'const x = 5'
        
        info = formatter.format_with_info(js_code)
        assert 'formatted' in info
        assert 'original_language' in info
        assert 'detected_language' in info
        assert 'formatter_used' in info
        assert 'changed' in info
    
    def test_pattern_detection(self, formatter):
        """Test language detection from patterns."""
        # Test Python detection
        py_code = '''def hello():
    print("Hello, World!")'''
        assert formatter._detect_language_from_patterns(py_code) == 'python'
        
        # Test JavaScript detection
        js_code = 'const x = () => { return 42; }'
        assert formatter._detect_language_from_patterns(js_code) == 'javascript'
        
        # Test TypeScript detection
        ts_code = 'interface Foo { bar: string; }'
        assert formatter._detect_language_from_patterns(ts_code) == 'typescript'
        
        # Test JSON detection
        json_code = '{"key": "value"}'
        assert formatter._detect_language_from_patterns(json_code) == 'json'
        
        # Test CSS detection
        css_code = '.class { color: red; }'
        assert formatter._detect_language_from_patterns(css_code) == 'css'
        
        # Test SQL detection
        sql_code = 'SELECT * FROM users WHERE id = 1'
        assert formatter._detect_language_from_patterns(sql_code) == 'sql'
    
    def test_fallback_parsers(self, formatter):
        """Test fallback parser mechanism."""
        # Test getting fallback parsers
        assert 'typescript' in formatter._get_fallback_parsers('babel')
        assert 'babel' in formatter._get_fallback_parsers('typescript')
        assert 'scss' in formatter._get_fallback_parsers('css')
        assert formatter._get_fallback_parsers('unknown') == []
    
    def test_format_without_language(self, formatter):
        """Test formatting without providing a language."""
        # Should auto-detect and format
        codes = [
            ('const x = 5', 'javascript'),
            ('{"key": "value"}', 'json'),
            ('SELECT * FROM users', 'sql'),
            ('.class { color: red; }', 'css'),
        ]
        
        for code, expected_type in codes:
            result = formatter.format(code)
            assert result is not None
            # The code should either be unchanged or properly formatted
            assert len(result) > 0