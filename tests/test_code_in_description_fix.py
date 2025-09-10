"""Test that code blocks are never included in descriptions."""

import pytest
from src.crawler.extractors.html import HTMLCodeExtractor


class TestCodeInDescriptionFix:
    """Test that the fix prevents code blocks from being included in descriptions."""
    
    @pytest.mark.asyncio
    async def test_code_blocks_not_in_description(self):
        """Test that code inside div containers is not included in descriptions."""
        html = """
        <div>
            <h3>Get started</h3>
            <p>You can add jobs to a queue like this:</p>
            <div class="codeblock">
                <pre><code>from bullmq import Queue
queue = Queue("myQueue")
await queue.add("myJob", { "foo": "bar" })</code></pre>
            </div>
            <p>In order to consume the jobs:</p>
            <div class="codeblock">
                <pre><code>from bullmq import Worker
import asyncio</code></pre>
            </div>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = await extractor.extract_blocks(html, "test.html")
        
        assert len(blocks) == 2
        
        # First block should not have code in description
        assert blocks[0].description is not None
        assert "from bullmq import Queue" not in blocks[0].description
        assert "queue = Queue" not in blocks[0].description
        assert "You can add jobs" in blocks[0].description
        
        # Second block should not have first code block in description
        assert blocks[1].description is not None
        assert "from bullmq import Queue" not in blocks[1].description
        assert "from bullmq import Worker" not in blocks[1].description
        assert "In order to consume" in blocks[1].description
    
    @pytest.mark.asyncio
    async def test_inline_code_preserved(self):
        """Test that inline code text is preserved in descriptions."""
        html = """
        <div>
            <h2>Configuration</h2>
            <p>Use the <code>Worker</code> class with options.</p>
            <p>The <code>connection</code> parameter is optional.</p>
            <pre><code>const worker = new Worker('myQueue')</code></pre>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = await extractor.extract_blocks(html, "test.html")
        
        assert len(blocks) == 1
        assert blocks[0].description is not None
        # Inline code text should be preserved (without the <code> tags)
        assert "Worker" in blocks[0].description
        assert "connection" in blocks[0].description
        # Block code should not be in description
        assert "const worker" not in blocks[0].description
        assert "new Worker" not in blocks[0].description
    
    @pytest.mark.asyncio
    async def test_nested_code_blocks_excluded(self):
        """Test that nested code structures are properly excluded."""
        html = """
        <article>
            <h1>Documentation</h1>
            <section>
                <p>First section text.</p>
                <div class="example">
                    <pre><code>example code here</code></pre>
                </div>
            </section>
            <section>
                <p>Second section text.</p>
                <pre><code>main code block</code></pre>
            </section>
        </article>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = await extractor.extract_blocks(html, "test.html")
        
        # Should find both code blocks
        assert len(blocks) == 2
        
        # First block should have only first section text
        assert blocks[0].description is not None
        assert "First section text" in blocks[0].description
        assert "example code" not in blocks[0].description
        assert "Second section" not in blocks[0].description
        
        # Second block should have only second section text
        assert blocks[1].description is not None
        assert "Second section text" in blocks[1].description
        assert "example code" not in blocks[1].description
        assert "main code block" not in blocks[1].description
    
    @pytest.mark.asyncio
    async def test_standalone_code_blocks(self):
        """Test standalone code blocks (not in pre tags)."""
        html = """
        <div>
            <h2>Examples</h2>
            <p>Here's a simple example:</p>
            <code>inline_function()</code>
            <p>And a multi-line example:</p>
            <code>function example() {
  return true;
}</code>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = await extractor.extract_blocks(html, "test.html")
        
        # Only multi-line code block is extracted (single-line filtered out)
        assert len(blocks) == 1
        
        # The multi-line code block
        assert "function example" in blocks[0].code
        assert blocks[0].description is not None
        assert "multi-line example" in blocks[0].description
        
        # Description should have the text before the code
        assert "simple example" in blocks[0].description
    
    @pytest.mark.asyncio
    async def test_inline_button_text_excluded(self):
        """Test that inline button text within divs is excluded from descriptions."""
        html = """
        <div>
            <h2>Examples</h2>
            <div class="toolbar">
                <span>Try this example:</span>
                <button>Download Sandbox</button>
                <button>Keep your edits and reload sandbox</button>
                <button>Clear all edits</button>
                <button>Open in CodeSandbox</button>
            </div>
            <pre><code>import React from 'react';

function App() {
  return <div>Hello</div>;
}</code></pre>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = await extractor.extract_blocks(html, "test.html")
        
        # Should extract the code block
        assert len(blocks) == 1
        assert "import React" in blocks[0].code
        
        # Description should have the instruction text
        assert blocks[0].description is not None
        assert "Try this example" in blocks[0].description
        
        # But NOT button text
        assert "Download Sandbox" not in blocks[0].description
        assert "Keep your edits" not in blocks[0].description
        assert "Clear all edits" not in blocks[0].description
        assert "Open in CodeSandbox" not in blocks[0].description
    
    @pytest.mark.asyncio
    async def test_button_text_excluded_from_description(self):
        """Test that button text is not included in descriptions."""
        html = """
        <div>
            <h2>Code Example</h2>
            <div>
                <p>Here's how to use the function:</p>
                <button>Download</button>
                <button>Reload</button>
                <button>Fork</button>
            </div>
            <pre><code>function example() {
  return true;
}</code></pre>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = await extractor.extract_blocks(html, "test.html")
        
        # Should extract the code block
        assert len(blocks) == 1
        assert "function example" in blocks[0].code
        
        # Description should have the instruction text
        assert blocks[0].description is not None
        assert "how to use the function" in blocks[0].description
        
        # But NOT button text
        assert "Download" not in blocks[0].description
        assert "Reload" not in blocks[0].description
        assert "Fork" not in blocks[0].description
    
    @pytest.mark.asyncio
    async def test_syntax_highlighted_code_not_in_description(self):
        """Test that syntax-highlighted code with spans is not included in descriptions."""
        html = """
        <div>
            <h3>Get started</h3>
            <p>You can add jobs to a queue like this:</p>
            <div class="group/codeblock">
                <pre><code><span style="color:var(--shiki-token-keyword)">from</span><span style="color:var(--shiki-foreground)"> bullmq </span><span style="color:var(--shiki-token-keyword)">import</span><span style="color:var(--shiki-foreground)"> Queue</span>
<span style="color:var(--shiki-foreground)">queue </span><span style="color:var(--shiki-token-keyword)">=</span><span style="color:var(--shiki-foreground)"> </span><span style="color:var(--shiki-token-function)">Queue</span><span style="color:var(--shiki-token-punctuation)">(</span><span style="color:var(--shiki-token-string-expression)">"myQueue"</span><span style="color:var(--shiki-token-punctuation)">)</span>
<span style="color:var(--shiki-token-keyword)">await</span><span style="color:var(--shiki-foreground)"> queue</span><span style="color:var(--shiki-token-punctuation)">.</span><span style="color:var(--shiki-token-function)">add</span><span style="color:var(--shiki-token-punctuation)">(</span><span style="color:var(--shiki-token-string-expression)">"myJob"</span><span style="color:var(--shiki-token-punctuation)">, { </span><span style="color:var(--shiki-token-string-expression)">"foo"</span><span style="color:var(--shiki-token-punctuation)">: </span><span style="color:var(--shiki-token-string-expression)">"bar"</span><span style="color:var(--shiki-token-punctuation)"> })</span></code></pre>
            </div>
            <p>In order to consume the jobs:</p>
            <pre><code>from bullmq import Worker</code></pre>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = await extractor.extract_blocks(html, "test.html")
        
        assert len(blocks) == 2
        
        # First block should not have code with weird spacing in description
        assert blocks[0].description is not None
        assert "You can add jobs" in blocks[0].description
        # Check for telltale signs of extracted syntax-highlighted code
        assert "Queue ( " not in blocks[0].description  # Would have spaces between tokens
        assert " = Queue" not in blocks[0].description
        assert "from bullmq import" not in blocks[0].description
        assert "await queue" not in blocks[0].description
        
        # Second block should have clean description
        assert blocks[1].description is not None
        assert "In order to consume" in blocks[1].description
        assert "from bullmq" not in blocks[1].description
