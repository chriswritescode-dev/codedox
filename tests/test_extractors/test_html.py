"""Tests for HTMLCodeExtractor."""

import pytest

from src.crawler.extractors.html import HTMLCodeExtractor


class TestHTMLCodeExtractor:
    """Test the HTMLCodeExtractor."""
    
    def test_extract_pre_code_block(self):
        """Test extraction of <pre><code> blocks."""
        html = """
        <html>
        <body>
            <h1>Installation</h1>
            <p>To install the package, run:</p>
            <pre><code>npm install express
npm install mongoose</code></pre>
            <p>This will install the dependencies.</p>
        </body>
        </html>
        """
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_blocks(html)
        
        assert len(blocks) == 1
        assert 'npm install express' in blocks[0].code
        assert 'npm install mongoose' in blocks[0].code
        assert blocks[0].context.title == 'Installation'
        assert 'To install the package' in blocks[0].context.description
    
    def test_skip_single_line_code(self):
        """Test that single-line <code> blocks are skipped."""
        html = """
        <html>
        <body>
            <h2>Configuration</h2>
            <p>Use the <code>config.json</code> file.</p>
            <p>Run <code>npm start</code> to begin.</p>
            <pre><code>const app = express();
app.listen(3000);</code></pre>
        </body>
        </html>
        """
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_blocks(html)
        
        # Only the multi-line pre block should be extracted
        assert len(blocks) == 1
        assert 'const app = express()' in blocks[0].code
        # Single-line inline code should not be extracted
        assert 'config.json' not in blocks[0].code
        assert 'npm start' not in blocks[0].code
    
    def test_extract_standalone_multiline_code(self):
        """Test extraction of multi-line <code> blocks without <pre>."""
        html = """
        <html>
        <body>
            <h2>Example</h2>
            <p>Here's the code:</p>
            <code>function hello() {
    return "world";
}</code>
        </body>
        </html>
        """
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_blocks(html)
        
        assert len(blocks) == 1
        assert 'function hello()' in blocks[0].code
        assert blocks[0].context.title == 'Example'
    
    def test_nested_heading_detection(self):
        """Test finding headings in nested structures."""
        html = """
        <html>
        <body>
            <div class="container">
                <section>
                    <h3>API Methods</h3>
                    <div class="content">
                        <p>Call the API like this:</p>
                        <pre><code>api.get('/users')
api.post('/users')</code></pre>
                    </div>
                </section>
            </div>
        </body>
        </html>
        """
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_blocks(html)
        
        assert len(blocks) == 1
        assert blocks[0].context.title == 'API Methods'
        assert 'Call the API' in blocks[0].context.description
    
    def test_multiple_blocks_under_same_heading(self):
        """Test multiple code blocks under the same heading."""
        html = """
        <html>
        <body>
            <h2>Setup Process</h2>
            <p>First, install dependencies:</p>
            <pre><code>pip install flask
pip install requests</code></pre>
            <p>Then, create your app:</p>
            <pre><code>from flask import Flask
app = Flask(__name__)</code></pre>
            <p>Finally, run it.</p>
        </body>
        </html>
        """
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_blocks(html)
        
        assert len(blocks) == 2
        
        # First block should have context about installing
        assert 'pip install flask' in blocks[0].code
        assert 'install dependencies' in blocks[0].context.description
        
        # Second block should have context about creating app
        assert 'from flask import Flask' in blocks[1].code
        assert 'create your app' in blocks[1].context.description
        
        # Both should have the same title
        assert blocks[0].context.title == 'Setup Process'
        assert blocks[1].context.title == 'Setup Process'
    
    def test_skip_button_text(self):
        """Test that button text is excluded from descriptions."""
        # Test with single-line code that has <3 significant words
        html = """
        <html>
        <body>
            <h2>Example</h2>
            <div>
                <span>Here's the code:</span>
                <button>Copy</button>
            </div>
            <pre><code>fn x</code></pre>
        </body>
        </html>
        """
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_blocks(html)
        
        assert len(blocks) == 0  # Single line code with <3 significant words should be skipped
        
        # Test with multi-line code
        html = """
        <html>
        <body>
            <h2>Example</h2>
            <div>
                <span>Here's the code:</span>
                <button>Copy</button>
            </div>
            <pre><code>console.log("test");
console.log("test2");</code></pre>
        </body>
        </html>
        """
        blocks = extractor.extract_blocks(html)
        assert len(blocks) == 1
        desc = blocks[0].context.description
        assert "Here's the code" in desc
        assert "Copy" not in desc  # Button text should be excluded
    
    def test_skip_navigation_elements(self):
        """Test that navigation elements are skipped."""
        html = """
        <html>
        <body>
            <nav>
                <a href="/">Home</a>
                <a href="/docs">Docs</a>
            </nav>
            <h1>Documentation</h1>
            <p>Example code:</p>
            <pre><code>def main():
    pass</code></pre>
        </body>
        </html>
        """
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_blocks(html)
        
        assert len(blocks) == 1
        desc = blocks[0].context.description
        assert 'Example code' in desc
        assert 'Home' not in desc
        assert 'Docs' not in desc
    
    def test_complex_nested_structure(self):
        """Test extraction from complex nested HTML."""
        html = """
        <html>
        <body>
            <article>
                <header>
                    <h1>Tutorial</h1>
                </header>
                <div class="section">
                    <h2>Getting Started</h2>
                    <div class="subsection">
                        <p>Initialize your project:</p>
                        <div class="code-container">
                            <pre><code>npm init -y
npm install express</code></pre>
                        </div>
                    </div>
                </div>
            </article>
        </body>
        </html>
        """
        extractor = HTMLCodeExtractor()
        blocks = extractor.extract_blocks(html)
        
        assert len(blocks) == 1
        assert 'npm init -y' in blocks[0].code
        # Should find the closest heading
        assert blocks[0].context.title == 'Getting Started | Tutorial'
        assert 'Initialize your project' in blocks[0].context.description