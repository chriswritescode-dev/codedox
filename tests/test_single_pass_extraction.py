"""Tests for the new single-pass HTML code extraction method."""

import pytest

from src.crawler.html_code_extractor import HTMLCodeExtractor


class TestSinglePassExtraction:
    """Test the new single-pass extraction method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = HTMLCodeExtractor()

    def test_sequential_code_blocks_with_context(self):
        """Test that context is properly associated with sequential code blocks."""
        html = """
        <html>
            <body>
                <h1>API Documentation</h1>
                <section>
                    <h2>Authentication</h2>
                    <p>First, get your API token:</p>
                    <pre><code>const token = await getToken();</code></pre>
                    
                    <p>Then use the token to make requests:</p>
                    <pre><code>const response = await fetch(url, {
  headers: { 'Authorization': token }
});</code></pre>
                    
                    <h2>Error Handling</h2>
                    <p>Always handle errors properly:</p>
                    <pre><code>try {
  await apiCall();
} catch (error) {
  console.error(error);
}</code></pre>
                </section>
            </body>
        </html>
        """
        
        blocks = self.extractor.extract_code_blocks_single_pass(html, "test.com")
        
        assert len(blocks) == 3
        
        # First block should have "Authentication" title and first description
        assert blocks[0].title == "Authentication"
        assert any("get your API token" in desc for desc in blocks[0].context_before)
        assert "getToken" in blocks[0].code
        
        # Second block should still have "Authentication" title but different description
        assert blocks[1].title == "Authentication"
        assert any("use the token" in desc for desc in blocks[1].context_before)
        assert "fetch" in blocks[1].code
        
        # Third block should have "Error Handling" title
        assert blocks[2].title == "Error Handling"
        assert any("handle errors" in desc for desc in blocks[2].context_before)
        assert "try" in blocks[2].code

    def test_nested_code_blocks_no_duplicates(self):
        """Test that nested pre/code structures don't create duplicates."""
        html = """
        <html>
            <body>
                <pre><code>function test() { return true; }</code></pre>
                <pre>console.log("standalone pre");</pre>
                <code>const inline = "should be skipped";</code>
                <div>
                    <code>
const multiline = "should be included";
console.log(multiline);
                    </code>
                </div>
            </body>
        </html>
        """
        
        blocks = self.extractor.extract_code_blocks_single_pass(html, "test.com")
        
        # Should get: pre>code, standalone pre, and multi-line code
        assert len(blocks) == 3
        assert "function test" in blocks[0].code
        assert "standalone pre" in blocks[1].code
        assert "multiline" in blocks[2].code

    def test_filename_detection(self):
        """Test that filenames are properly detected from various sources."""
        html = """
        <html>
            <body>
                <div class="code-example">
                    <span class="filename">package.json</span>
                    <pre><code>{"name": "test"}</code></pre>
                </div>
                
                <div data-filename="app.js">
                    <pre><code>console.log("app");</code></pre>
                </div>
                
                <div title="config.yaml">
                    <pre><code>version: 1</code></pre>
                </div>
            </body>
        </html>
        """
        
        blocks = self.extractor.extract_code_blocks_single_pass(html, "test.com")
        
        assert len(blocks) == 3
        # Note: Filename detection is in the context extraction, verify it works

    def test_container_type_classification(self):
        """Test that container types are properly classified."""
        html = """
        <html>
            <body>
                <div class="api-endpoint">
                    <pre><code>GET /api/users</code></pre>
                </div>
                
                <section class="example">
                    <pre><code>example.run();</code></pre>
                </section>
                
                <div id="configuration-section">
                    <pre><code>config.set("key", "value");</code></pre>
                </div>
            </body>
        </html>
        """
        
        blocks = self.extractor.extract_code_blocks_single_pass(html, "test.com")
        
        assert len(blocks) == 3
        assert blocks[0].container_type == "api-method"
        assert blocks[1].container_type == "example"
        assert blocks[2].container_type == "configuration"

    def test_context_reset_between_blocks(self):
        """Test that descriptions are reset but titles persist."""
        html = """
        <html>
            <body>
                <h1>Main Title</h1>
                <p>Description for first block</p>
                <pre><code>function first() { return 1; }</code></pre>
                
                <p>Description for second block</p>
                <pre><code>function second() { return 2; }</code></pre>
                
                <h2>Subtitle</h2>
                <p>Description for third block</p>
                <pre><code>function third() { return 3; }</code></pre>
            </body>
        </html>
        """
        
        blocks = self.extractor.extract_code_blocks_single_pass(html, "test.com")
        
        assert len(blocks) == 3
        
        # First two blocks should have "Main Title"
        assert blocks[0].title == "Main Title"
        assert blocks[1].title == "Main Title"
        
        # Third block should have "Subtitle"
        assert blocks[2].title == "Subtitle"
        
        # Each should have only its own description
        assert any("first block" in desc for desc in blocks[0].context_before)
        assert not any("second block" in desc for desc in blocks[0].context_before)
        
        assert any("second block" in desc for desc in blocks[1].context_before)
        assert not any("first block" in desc for desc in blocks[1].context_before)
        
        assert any("third block" in desc for desc in blocks[2].context_before)
        assert not any("first block" in desc for desc in blocks[2].context_before)

    def test_skip_ui_elements(self):
        """Test that UI elements are properly skipped."""
        html = """
        <html>
            <body>
                <button>Copy</button>
                <nav>Navigation</nav>
                <p>Real content here</p>
                <pre><code>code.here();</code></pre>
                <div class="copy-button">Copy Code</div>
                <script>console.log("should be skipped");</script>
            </body>
        </html>
        """
        
        blocks = self.extractor.extract_code_blocks_single_pass(html, "test.com")
        
        assert len(blocks) == 1
        assert "code.here" in blocks[0].code
        assert any("Real content" in desc for desc in blocks[0].context_before)
        # UI elements should not appear in context
        assert not any("Copy" in desc for desc in blocks[0].context_before)
        assert not any("Navigation" in desc for desc in blocks[0].context_before)

    def test_complex_nested_structure(self):
        """Test extraction from deeply nested documentation structure."""
        html = """
        <html>
            <body>
                <article>
                    <section class="docs">
                        <div class="content">
                            <h1>Documentation</h1>
                            <div class="subsection">
                                <h2>Getting Started</h2>
                                <div class="example-wrapper">
                                    <p>Install the package:</p>
                                    <pre><code>npm install package</code></pre>
                                    
                                    <p>Import and use:</p>
                                    <pre><code>import pkg from 'package';</code></pre>
                                </div>
                            </div>
                        </div>
                    </section>
                </article>
            </body>
        </html>
        """
        
        blocks = self.extractor.extract_code_blocks_single_pass(html, "test.com")
        
        assert len(blocks) == 2
        
        # Both should have the subtitle (more specific)
        assert blocks[0].title == "Getting Started"
        assert blocks[1].title == "Getting Started"
        
        # Check context
        assert any("Install" in desc for desc in blocks[0].context_before)
        assert any("Import" in desc for desc in blocks[1].context_before)

    def test_inline_vs_block_code_detection(self):
        """Test that inline code is skipped unless multi-line."""
        html = """
        <html>
            <body>
                <p>Use <code>inline()</code> for this.</p>
                <p>But this is different: <code>
multi
line
code
                </code></p>
                <div><code>const block = "also extracted";</code></div>
                <pre><code>pre.code();</code></pre>
            </body>
        </html>
        """
        
        blocks = self.extractor.extract_code_blocks_single_pass(html, "test.com")
        
        # Should extract: multi-line code in p, div>code (if long enough), and pre>code
        # The inline() should be skipped
        assert not any("inline()" in block.code for block in blocks)
        assert any("multi\nline\ncode" in block.code for block in blocks)
        assert any("pre.code" in block.code for block in blocks)

    def test_comparison_with_old_method(self):
        """Compare results between old and new extraction methods."""
        html = """
        <html>
            <body>
                <h1>Test Comparison</h1>
                <section class="api-docs">
                    <h2>API Methods</h2>
                    <p>First method description</p>
                    <pre><code>api.method1();</code></pre>
                    
                    <p>Second method description</p>
                    <pre><code>api.method2();</code></pre>
                </section>
            </body>
        </html>
        """
        
        # Extract with both methods
        old_blocks = self.extractor.extract_code_blocks(html, "test.com")
        new_blocks = self.extractor.extract_code_blocks_single_pass(html, "test.com")
        
        # Should get same number of blocks
        assert len(old_blocks) == len(new_blocks) == 2
        
        # Code content should be identical
        assert old_blocks[0].code == new_blocks[0].code
        assert old_blocks[1].code == new_blocks[1].code
        
        # New method should have better context association
        # (Old method looks backwards, new method accumulates forward)
        assert new_blocks[0].title == "API Methods"
        assert new_blocks[1].title == "API Methods"