"""Tests for language detection."""

import pytest
from src.language import LanguageDetector, DetectionResult


class TestLanguageDetector:
    """Test language detection functionality."""
    
    @pytest.fixture
    def detector(self):
        """Create a language detector instance."""
        return LanguageDetector()
    
    def test_detect_python(self, detector):
        """Test Python detection."""
        code = """
def hello_world():
    print("Hello, World!")
    return 42
"""
        result = detector.detect(code)
        assert result.language == 'python'
        assert result.confidence >= 0.8
    
    def test_detect_javascript(self, detector):
        """Test JavaScript detection."""
        code = """
function helloWorld() {
    console.log("Hello, World!");
    return 42;
}
"""
        result = detector.detect(code)
        assert result.language == 'javascript'
        assert result.confidence >= 0.8
    
    def test_detect_by_extension(self, detector):
        """Test detection by file extension."""
        code = "print('test')"
        result = detector.detect(code, "test.py")
        assert result.language == 'python'
        # Method could be either 'tree-sitter' or 'extension' depending on parser availability
        assert result.method in ['tree-sitter', 'extension']
    
    def test_extract_functions_python(self, detector):
        """Test function extraction for Python."""
        code = """
def add(a, b):
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y
"""
        functions = detector.extract_functions(code, 'python')
        assert 'add' in functions
        assert 'multiply' in functions
    
    def test_extract_imports_python(self, detector):
        """Test import extraction for Python."""
        code = """
import os
from datetime import datetime
import numpy as np
"""
        imports = detector.extract_imports(code, 'python')
        assert 'os' in imports
        assert 'datetime' in imports
        assert 'numpy' in imports  # Only module name is extracted, not alias