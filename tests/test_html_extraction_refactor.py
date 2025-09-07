"""Tests for the refactored HTML code extraction algorithm."""

import pytest
from src.crawler.html_code_extractor import HTMLCodeExtractor


def assert_in_description(text: str, description: str | None) -> None:
    """Helper to assert text is in description."""
    assert description is not None, "Description should not be None"
    assert text in description
    

def assert_not_in_description(text: str, description: str | None) -> None:
    """Helper to assert text is not in description."""
    assert description is None or text not in description


class TestHTMLExtractionRefactor:
    """Test the simplified HTML code extraction approach."""
    
    def test_simple_heading_paragraph_code(self):
        """Test simple case: heading → paragraph → code."""
        html = """
        <html>
        <body>
            <h2>Installation Guide</h2>
            <p>To install the package, run the following command:</p>
            <pre><code>npm install my-package</code></pre>
        </body>
        </html>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_code_blocks(html, "test.html")
        
        assert len(blocks) == 1
        assert blocks[0].title == "Installation Guide"
        assert blocks[0].description is not None
        assert "To install the package" in blocks[0].description
        assert "npm install my-package" in blocks[0].code
    
    def test_modern_docs_structure(self):
        """Test modern docs structure like BullMQ."""
        html = """
        <main>
            <header>
                <h1>Adding jobs in bulk</h1>
            </header>
            <div class="grid">
                <p>Sometimes it is necessary to add multiple jobs at once.</p>
                <p>You may think of queue.addBulk as a faster option.</p>
                <div class="codeblock">
                    <pre><code>queue.addBulk([job1, job2, job3])</code></pre>
                </div>
                <p>It is possible to add more options after the code.</p>
            </div>
        </main>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_code_blocks(html, "test.html")
        
        assert len(blocks) == 1
        assert blocks[0].title == "Adding jobs in bulk"
        assert_in_description("Sometimes it is necessary", blocks[0].description)
        assert_in_description("You may think of queue.addBulk", blocks[0].description)
        # Should NOT include content after code
        assert_not_in_description("It is possible to add more options", blocks[0].description)
        assert "queue.addBulk" in blocks[0].code
    
    def test_multiple_code_blocks_one_heading(self):
        """Test multiple code blocks after one heading."""
        html = """
        <div>
            <h2>API Examples</h2>
            <p>Here's how to make a GET request:</p>
            <pre><code>fetch('/api/users')</code></pre>
            <p>And here's a POST request:</p>
            <pre><code>fetch('/api/users', { method: 'POST' })</code></pre>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_code_blocks(html, "test.html")
        
        assert len(blocks) == 2
        
        # First block should get content between heading and first code
        assert blocks[0].title == "API Examples"
        assert_in_description("how to make a GET request", blocks[0].description)
        assert_not_in_description("POST request", blocks[0].description)
        assert "fetch('/api/users')" in blocks[0].code
        
        # Second block should get content between first code and second code
        assert blocks[1].title == "API Examples"
        assert_in_description("POST request", blocks[1].description)
        assert_not_in_description("GET request", blocks[1].description)
        assert "method: 'POST'" in blocks[1].code
    
    def test_no_heading_found(self):
        """Test when no heading is found before code."""
        html = """
        <div>
            <p>This is some documentation without a heading.</p>
            <pre><code>console.log('hello')</code></pre>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_code_blocks(html, "test.html")
        
        assert len(blocks) == 1
        assert blocks[0].title is None
        assert_in_description("documentation without a heading", blocks[0].description)
        assert "console.log" in blocks[0].code
    
    def test_nested_structure(self):
        """Test deeply nested HTML structure."""
        html = """
        <article>
            <section>
                <div class="content">
                    <header>
                        <h3>Configuration</h3>
                    </header>
                    <div class="description">
                        <p>Set up your config file as follows:</p>
                        <ul>
                            <li>Create a config.json file</li>
                            <li>Add your settings</li>
                        </ul>
                    </div>
                    <div class="example">
                        <pre><code>{ "port": 3000 }</code></pre>
                    </div>
                </div>
            </section>
        </article>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_code_blocks(html, "test.html")
        
        assert len(blocks) == 1
        assert blocks[0].title == "Configuration"
        assert "Set up your config file" in blocks[0].description
        assert "Create a config.json file" in blocks[0].description
        assert "Add your settings" in blocks[0].description
        assert '"port": 3000' in blocks[0].code
    
    def test_heading_in_sibling_container(self):
        """Test when heading is in a sibling container."""
        html = """
        <div class="doc-section">
            <div class="heading-container">
                <h2>Database Setup</h2>
            </div>
            <div class="content-container">
                <p>Initialize your database with this command:</p>
                <pre><code>createdb myapp</code></pre>
            </div>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_code_blocks(html, "test.html")
        
        assert len(blocks) == 1
        assert blocks[0].title == "Database Setup"
        assert "Initialize your database" in blocks[0].description
        assert "createdb myapp" in blocks[0].code
    
    def test_exclude_content_after_code(self):
        """Test that content after code block is not included."""
        html = """
        <div>
            <h2>Example Usage</h2>
            <p>Before the code block.</p>
            <pre><code>example()</code></pre>
            <p>After the code block - should not be included.</p>
            <p>More content after - also should not be included.</p>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_code_blocks(html, "test.html")
        
        assert len(blocks) == 1
        assert blocks[0].title == "Example Usage"
        assert "Before the code block" in blocks[0].description
        assert "After the code block" not in blocks[0].description
        assert "More content after" not in blocks[0].description
    
    def test_skip_inline_code(self):
        """Test that inline code is skipped."""
        html = """
        <div>
            <h2>Documentation</h2>
            <p>Use <code>inline()</code> for inline operations.</p>
            <p>For batch operations, use this:</p>
            <pre><code>batch_process(items)</code></pre>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_code_blocks(html, "test.html")
        
        assert len(blocks) == 1
        assert "batch_process" in blocks[0].code
        # Inline code should not be extracted as separate block
        assert not any("inline()" in block.code for block in blocks if "inline()" == block.code.strip())
    
    def test_api_method_extraction(self):
        """Test that API method code blocks are properly extracted with title."""
        html = """
        <div class="api-method">
            <h3>POST /api/users</h3>
            <p>Create a new user.</p>
            <pre><code>{"name": "John"}</code></pre>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_code_blocks(html, "test.html")
        
        assert len(blocks) == 1
        assert blocks[0].title == "POST /api/users"
        assert '{"name": "John"}' in blocks[0].code
    
    def test_empty_description(self):
        """Test when there's no content between heading and code."""
        html = """
        <div>
            <h2>Quick Example</h2>
            <pre><code>quickExample()</code></pre>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_code_blocks(html, "test.html")
        
        assert len(blocks) == 1
        assert blocks[0].title == "Quick Example"
        assert blocks[0].description is None or blocks[0].description == ""