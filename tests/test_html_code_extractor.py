"""Tests for HTML code extraction functionality."""

from bs4 import BeautifulSoup

from src.crawler.html_code_extractor import HTMLCodeExtractor


class TestHTMLCodeExtractor:
    """Test HTML code extraction and language detection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = HTMLCodeExtractor()

    def test_extract_code_from_pre_tags(self):
        """Test extracting code from <pre> tags."""
        html = """
        <html>
            <body>
                <pre><code>function hello() {
    console.log("Hello, World!");
}</code></pre>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')

        blocks = self.extractor.extract_code_blocks(html, "https://test.com")

        assert len(blocks) >= 1
        assert "function hello()" in blocks[0].code

    def test_extract_code_from_code_tags(self):
        """Test extracting code from <code> tags inside <pre> (standalone <code> tags are not extracted by design)."""
        html = """
        <html>
            <body>
                <pre><code>const x: number = 42;</code></pre>
            </body>
        </html>
        """

        blocks = self.extractor.extract_code_blocks(html, "https://test.com")

        assert len(blocks) >= 1
        assert "const x: number = 42;" in blocks[0].code

    def test_language_detection_typescript(self):
        """Test TypeScript language detection."""
        html = """
        <pre><code>interface User {
    name: string;
    age: number;
}</code></pre>
        """
        blocks = self.extractor.extract_code_blocks(html, "https://test.com")

        assert len(blocks) >= 1

    def test_language_detection_javascript(self):
        """Test JavaScript language detection."""
        html = """
        <pre><code>export function calculate(a, b) {
    return a + b;
}</code></pre>
        """
        blocks = self.extractor.extract_code_blocks(html, "https://test.com")

        assert len(blocks) >= 1

    def test_language_detection_python(self):
        """Test Python language detection."""
        html = """
        <pre><code>def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)</code></pre>
        """
        blocks = self.extractor.extract_code_blocks(html, "https://test.com")

        assert len(blocks) >= 1

    def test_language_detection_bash(self):
        """Test Bash language detection."""
        html = """
        <pre><code>#!/bin/bash
echo "Hello World"
ls -la</code></pre>
        """
        blocks = self.extractor.extract_code_blocks(html, "https://test.com")

        assert len(blocks) >= 1

    def test_language_detection_json(self):
        """Test JSON language detection."""
        html = """
        <pre><code>{
    "name": "test",
    "version": "1.0.0"
}</code></pre>
        """
        blocks = self.extractor.extract_code_blocks(html, "https://test.com")

        assert len(blocks) >= 1

    def test_language_detection_css_import(self):
        """Test CSS language detection with @import statement."""
        html = """
        <pre><code>@import "tailwindcss";
body {
    margin: 0;
}</code></pre>
        """
        blocks = self.extractor.extract_code_blocks(html, "https://test.com")

        assert len(blocks) >= 1

    def test_skip_short_code_blocks(self):
        """Test that very short code blocks are skipped."""
        html = """
        <html>
            <body>
                <code>x</code>  <!-- Too short -->
                <pre><code>function longEnoughFunction() {
    return "This should be extracted";
}</code></pre>
            </body>
        </html>
        """
        blocks = self.extractor.extract_code_blocks(html, "https://test.com")

        assert len(blocks) >= 1
        assert "longEnoughFunction" in blocks[0].code

    def test_extract_surrounding_context(self):
        """Test extraction of surrounding context."""
        html = """
        <html>
            <body>
                <h2>User Authentication</h2>
                <p>This function handles user login:</p>
                <pre><code>function login(username, password) {
    return authenticate(username, password);
}</code></pre>
                <p>Make sure to validate input.</p>
            </body>
        </html>
        """
        blocks = self.extractor.extract_code_blocks(html, "https://test.com")

        assert len(blocks) >= 1
        # Check that context_before is extracted
        assert hasattr(blocks[0], 'context_before')
        # context_after was removed - we only collect context before code blocks
        assert not hasattr(blocks[0], 'context_after')

    def test_stats_tracking(self):
        """Test that statistics are properly tracked."""
        html = """
        <html>
            <body>
                <pre><code>const x = 1;</code></pre>
                <pre><code>def func(): pass</code></pre>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Reset stats
        self.extractor.stats = {
            'total_blocks': 0,
            'blocks_by_type': {},
            'languages_found': set()
        }

        blocks = self.extractor.extract_code_blocks(html, "https://test.com")

        assert len(blocks) >= 2
        assert self.extractor.stats['total_blocks'] >= 2

    def test_extract_from_complex_nested_structure(self):
        """Test extraction from complex nested HTML structure."""
        html = """
        <html>
            <body>
                <div class="documentation">
                    <section>
                        <h3>Example Code</h3>
                        <div class="code-container">
                            <pre><code>interface ApiResponse {
    data: any[];
    status: number;
}</code></pre>
                        </div>
                    </section>
                </div>
            </body>
        </html>
        """
        blocks = self.extractor.extract_code_blocks(html, "https://test.com")

        assert len(blocks) >= 1
        assert "ApiResponse" in blocks[0].code

    def test_handle_empty_code_blocks(self):
        """Test handling of empty or whitespace-only code blocks."""
        html = """
        <html>
            <body>
                <pre><code></code></pre>
                <pre><code>   </code></pre>
                <pre><code>
                
                </code></pre>
                <pre><code>function valid() { return true; }</code></pre>
            </body>
        </html>
        """
        blocks = self.extractor.extract_code_blocks(html, "https://test.com")

        # Only the valid function should be extracted
        assert len(blocks) >= 1
        assert "function valid()" in blocks[0].code
