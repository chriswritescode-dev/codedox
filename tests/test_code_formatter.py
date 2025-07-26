"""Test code formatting functionality."""

import unittest
from unittest.mock import patch, Mock
from src.crawler.code_formatter import CodeFormatter


class TestCodeFormatter(unittest.TestCase):
    """Test the CodeFormatter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.formatter = CodeFormatter()
    
    def test_javascript_formatting(self):
        """Test JavaScript code formatting."""
        # Skip if Prettier not available
        if not self.formatter.prettier_available:
            self.skipTest("Prettier not available")
        
        code = "function test(){return true;}"
        formatted = self.formatter.format(code, 'javascript')
        
        # Prettier should format it nicely
        self.assertIn("function test()", formatted)
        self.assertIn("return true", formatted)
    
    def test_typescript_formatting(self):
        """Test TypeScript code formatting."""
        if not self.formatter.prettier_available:
            self.skipTest("Prettier not available")
        
        code = "interface User{name:string;age:number;}"
        formatted = self.formatter.format(code, 'typescript')
        
        # Should have proper spacing
        self.assertIn("interface User", formatted)
        self.assertIn("name: string", formatted)
        self.assertIn("age: number", formatted)
    
    def test_jsx_formatting(self):
        """Test JSX code formatting."""
        if not self.formatter.prettier_available:
            self.skipTest("Prettier not available")
        
        code = "<div className='test'><span>{value}</span></div>"
        formatted = self.formatter.format(code, 'jsx')
        
        # Should format JSX properly
        self.assertIn("<div", formatted)
        self.assertIn("className", formatted)
        self.assertIn("{value}", formatted)
    
    def test_python_formatting(self):
        """Test Python code formatting."""
        code = "def test(x,y):\n    return x+y"
        formatted = self.formatter.format(code, 'python')
        
        # Should maintain proper indentation
        self.assertIn("def test(x,y):", formatted)
        self.assertIn("    return x+y", formatted)
    
    def test_json_formatting(self):
        """Test JSON formatting."""
        code = '{"name":"test","value":123}'
        formatted = self.formatter.format(code, 'json')
        
        # Should be properly indented
        self.assertIn('"name"', formatted)
        self.assertIn('"value"', formatted)
        if self.formatter.prettier_available:
            # Prettier formats with newlines
            self.assertIn('\n', formatted)
    
    def test_sql_formatting(self):
        """Test SQL formatting."""
        code = "select * from users where id = 1"
        formatted = self.formatter.format(code, 'sql')
        
        # Should uppercase keywords
        self.assertIn("SELECT", formatted)
        self.assertIn("FROM", formatted)
        self.assertIn("WHERE", formatted)
    
    def test_unknown_language(self):
        """Test formatting for unknown language."""
        code = "  some code  \n\n\n  more code  "
        formatted = self.formatter.format(code, 'unknown')
        
        # Should do basic formatting
        self.assertEqual(formatted, "some code\n\nmore code")
    
    def test_empty_code(self):
        """Test formatting empty code."""
        self.assertEqual(self.formatter.format("", 'javascript'), "")
        self.assertEqual(self.formatter.format(None, 'python'), None)
    
    def test_prettier_fallback(self):
        """Test fallback when Prettier is not available."""
        formatter = CodeFormatter()
        formatter.prettier_available = False
        
        code = "function test(){return true;}"
        formatted = formatter.format(code, 'javascript')
        
        # Should get basic formatting
        self.assertEqual(formatted, "function test(){return true;}")
    
    def test_prettier_error_handling(self):
        """Test handling of Prettier errors."""
        with patch('subprocess.run') as mock_run:
            # Version check succeeds, formatting fails
            mock_run.side_effect = [
                Mock(returncode=0, stdout="3.0.0"),
                Mock(returncode=1, stderr="Parse error")
            ]
            
            formatter = CodeFormatter()
            code = "function test() { return true; }"
            formatted = formatter.format(code, 'javascript')
            
            # Should fall back to basic formatting
            self.assertEqual(formatted, code)
    
    def test_invalid_json(self):
        """Test formatting invalid JSON."""
        code = '{"invalid": json}'
        formatted = self.formatter.format(code, 'json')
        
        # Should return as-is for invalid JSON
        self.assertEqual(formatted, code)
    
    def test_html_formatting(self):
        """Test HTML formatting."""
        code = "<div><p>test</p></div>"
        formatted = self.formatter.format(code, 'html')
        
        if self.formatter.prettier_available:
            # Prettier formats HTML
            self.assertIn("<div>", formatted)
            self.assertIn("<p>", formatted)
        else:
            # Basic formatting
            self.assertEqual(formatted, code)
    
    def test_css_formatting(self):
        """Test CSS formatting."""
        if not self.formatter.prettier_available:
            self.skipTest("Prettier not available")
        
        code = ".class{color:red;font-size:12px;}"
        formatted = self.formatter.format(code, 'css')
        
        # Should format with proper spacing
        self.assertIn("color:", formatted)
        self.assertIn("font-size:", formatted)
    
    def test_yaml_formatting(self):
        """Test YAML formatting."""
        code = "key:   value\nlist:\n  - item1\n  - item2"
        formatted = self.formatter.format(code, 'yaml')
        
        # Should preserve YAML structure
        self.assertIn("key:", formatted)
        self.assertIn("- item1", formatted)
        self.assertIn("- item2", formatted)


if __name__ == '__main__':
    unittest.main()