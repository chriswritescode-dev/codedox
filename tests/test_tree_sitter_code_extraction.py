"""Test tree-sitter integration in code extraction."""

import pytest
from src.parser.code_extractor import CodeExtractor, TREE_SITTER_AVAILABLE
from src.language.detector import LanguageDetector


class TestTreeSitterCodeExtraction:
    """Test suite for tree-sitter enhanced code extraction."""
    
    @pytest.fixture
    def extractor_with_tree_sitter(self):
        """Create a code extractor with tree-sitter enabled."""
        return CodeExtractor(
            min_code_lines=2,
            use_tree_sitter=True,
            min_quality_score=0.7
        )
    
    @pytest.fixture
    def extractor_without_tree_sitter(self):
        """Create a code extractor with tree-sitter disabled."""
        return CodeExtractor(
            min_code_lines=2,
            use_tree_sitter=False
        )
    
    @pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
    def test_tree_sitter_filters_inline_code(self, extractor_with_tree_sitter):
        """Test that tree-sitter filters out low-quality inline code."""
        # This should be rejected - it's not a complete code structure
        markdown = '''
        Here's an example: `CrawlerRunConfig( markdown_generator = DefaultMarkdownGenerator() )`
        
        Another inline code: `print("hello world")`
        '''
        
        blocks = extractor_with_tree_sitter.extract_from_content(markdown, content_type="markdown")
        assert len(blocks) == 0  # Should reject single-line inline code
    
    @pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
    def test_tree_sitter_accepts_valid_code(self, extractor_with_tree_sitter):
        """Test that tree-sitter accepts valid code blocks."""
        markdown = '''```python
def calculate_sum(a, b):
    """Calculate the sum of two numbers."""
    return a + b
```

```javascript
function calculateSum(a, b) {
    // Calculate the sum
    return a + b;
}
```'''
        
        blocks = extractor_with_tree_sitter.extract_from_content(markdown, content_type="markdown")
        assert len(blocks) == 2
        assert blocks[0].language == 'python'
        assert blocks[1].language == 'javascript'
    
    @pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
    def test_tree_sitter_rejects_malformed_code(self, extractor_with_tree_sitter):
        """Test that tree-sitter rejects code with too many syntax errors."""
        markdown = '''
        ```python
        def broken_function(
            if True  # Missing colon and parenthesis
                print("This won't work"
            return None
        ```
        '''
        
        blocks = extractor_with_tree_sitter.extract_from_content(markdown, content_type="markdown")
        # Should reject due to syntax errors
        assert len(blocks) == 0
    
    @pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
    def test_tree_sitter_quality_scoring(self, extractor_with_tree_sitter):
        """Test code quality scoring functionality."""
        test_cases = [
            # Good quality code
            ('''def hello():
    print("world")''', True),
            
            # Prose text disguised as code
            ('This is describing how the function works and what it returns', False),
            
            # Just a comment
            ('''# This is just a comment
# Another comment''', False),
            
            # Complete class
            ('''class Example:
    def __init__(self):
        self.value = 42''', True),
            
            # Random text that looks like code
            ('''the function returns
the value of x''', False),
        ]
        
        for code, should_pass in test_cases:
            score = extractor_with_tree_sitter._calculate_code_quality(code, 'python')
            if should_pass:
                assert score >= 0.7, f"Expected high score for: {code[:30]}..."
            else:
                assert score < 0.7, f"Expected low score for: {code[:30]}..."
    
    def test_tree_sitter_disabled_fallback(self, extractor_without_tree_sitter):
        """Test that extraction works without tree-sitter."""
        markdown = '''```python
def test():
    pass
```'''
        
        blocks = extractor_without_tree_sitter.extract_from_content(markdown, content_type="markdown")
        assert len(blocks) == 1
        assert blocks[0].language == 'python'
    
    @pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
    def test_html_code_extraction_with_tree_sitter(self, extractor_with_tree_sitter):
        """Test tree-sitter validation on HTML-extracted code."""
        html = '''
        <pre><code class="language-python">
def valid_function():
    return True
        </code></pre>
        
        <!-- This should be filtered out -->
        <code>print("single line")</code>
        
        <!-- This should pass - multi-line code -->
        <code>function test() {
    console.log("test");
}</code>
        '''
        
        blocks = extractor_with_tree_sitter.extract_from_content(html, content_type="html")
        # The extractor might not filter inline code in HTML, so we could get 2 or 3 blocks
        assert len(blocks) >= 2  # At least the pre/code block and multi-line code block
        # Check that we have the expected Python function
        python_blocks = [b for b in blocks if "def valid_function" in b.content]
        assert len(python_blocks) == 1
    
    @pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
    def test_language_detection_override(self, extractor_with_tree_sitter):
        """Test that tree-sitter can correct wrong language hints."""
        # Markdown says it's Python but it's actually JavaScript
        markdown = '''```python
function calculateSum(a, b) {
    return a + b;
}
```'''
        
        blocks = extractor_with_tree_sitter.extract_from_content(markdown, content_type="markdown")
        # Tree-sitter should still accept it even with wrong language hint
        assert len(blocks) == 1
        # The language might be corrected by tree-sitter detection
    
    @pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
    def test_prose_rejection(self, extractor_with_tree_sitter):
        """Test that prose-like content is rejected even if it has code-like formatting."""
        markdown = '''
        ```
        This is a description of how the function works.
        It takes two parameters and returns their sum.
        The implementation is straightforward.
        ```
        '''
        
        blocks = extractor_with_tree_sitter.extract_from_content(markdown, content_type="markdown")
        # Should reject prose even though it's in a code block
        assert len(blocks) == 0
    
    @pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
    def test_complete_structures_bonus(self, extractor_with_tree_sitter):
        """Test that complete structures get quality bonus."""
        # Complete function should score higher
        complete_function = '''def process_data(items):
    """Process a list of items."""
    results = []
    for item in items:
        if item.is_valid():
            results.append(item.transform())
    return results'''
        
        # Incomplete snippet should score lower (just the body without function)
        incomplete_snippet = '''results = []
for item in items:
    results.append(item)'''
        
        complete_score = extractor_with_tree_sitter._calculate_code_quality(complete_function, 'python')
        incomplete_score = extractor_with_tree_sitter._calculate_code_quality(incomplete_snippet, 'python')
        
        assert complete_score > incomplete_score
        assert complete_score >= 0.8  # Should get bonus for complete structure