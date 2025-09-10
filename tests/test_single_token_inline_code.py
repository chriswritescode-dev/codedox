"""Test that single-line inline code is not extracted as snippets."""

import pytest
import asyncio
from src.crawler.extractors.html import HTMLCodeExtractor


class TestSingleLineInlineCode:
    """Test filtering of single-line inline code."""
    
    @pytest.mark.asyncio
    async def test_single_line_inline_not_extracted(self):
        """Test that ALL single-line inline code is not extracted as snippets."""
        html = """
        <div>
            <h2>React Hooks</h2>
            <p>Use <code>useState</code> for state management.</p>
            <p>The <code>defaultChecked</code> prop sets initial checkbox state.</p>
            <p>Call <code>setValue(123)</code> to update.</p>
            <p>Use <code>Array.from()</code> to convert.</p>
            <p>Access with <code>user.name</code> notation.</p>
            <p>Component type <code>React.FC</code> for TypeScript.</p>
            <p>Module <code>lodash.debounce</code> import.</p>
            <p>Variable: <code>const value = 5</code></p>
            <p>JSX: <code>&lt;input /&gt;</code></p>
            <p>Object: <code>{ key: value }</code></p>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = await extractor.extract_blocks(html, "test.html")
        
        # NONE of these single-line snippets should be extracted
        assert len(blocks) == 0
        
    @pytest.mark.asyncio
    async def test_multi_line_inline_extracted(self):
        """Test that multi-line inline code IS extracted as snippets."""
        html = """
        <div>
            <h2>Examples</h2>
            <p>Multi-line function: <code>function test() {
  return true;
}</code></p>
            <p>Multi-line object: <code>{
  key: 'value',
  other: 123
}</code></p>
            <p>Multi-line array: <code>[
  'item1',
  'item2'
]</code></p>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = await extractor.extract_blocks(html, "test.html")
        
        # All multi-line code should be extracted
        assert len(blocks) == 3
        
        code_snippets = [block.code for block in blocks]
        assert any("function test()" in code for code in code_snippets)
        assert any("key: 'value'" in code for code in code_snippets)
        assert any("'item1'" in code for code in code_snippets)
    
    @pytest.mark.asyncio
    async def test_single_line_in_description(self):
        """Test that single-line inline code still appears in descriptions for nearby multi-line blocks."""
        html = """
        <div>
            <h2>API Reference</h2>
            <p>The <code>useState</code> hook returns a state variable.</p>
            <p>Use <code>defaultChecked</code> for initial state.</p>
            <p>Here's the full usage:</p>
            <pre><code>const [checked, setChecked] = useState(false);
const [name, setName] = useState('');
const [age, setAge] = useState(0);</code></pre>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = await extractor.extract_blocks(html, "test.html")
        
        # Only the pre block should be extracted
        assert len(blocks) == 1
        assert "const [checked, setChecked]" in blocks[0].code
        
        # Single-line inline code should appear in description
        assert blocks[0].description is not None
        assert "useState" in blocks[0].description
        assert "defaultChecked" in blocks[0].description
    
    @pytest.mark.asyncio
    async def test_edge_cases(self):
        """Test edge cases for inline code filtering."""
        html = """
        <div>
            <h2>Edge Cases</h2>
            <p>Empty: <code></code></p>
            <p>Just spaces: <code>   </code></p>
            <p>Single line: <code>hello world</code></p>
            <p>Multi-line inline: <code>line1
line2</code></p>
            <p>Multi-line with indentation: <code>function test() {
  return true;
}</code></p>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = await extractor.extract_blocks(html, "test.html")
        
        # Only multi-line code should be extracted
        assert len(blocks) == 2
        
        # Check that both multi-line blocks are extracted
        code_snippets = [block.code for block in blocks]
        assert any("line1" in code and "line2" in code for code in code_snippets)
        assert any("function test()" in code for code in code_snippets)
    
    @pytest.mark.asyncio
    async def test_mixed_content(self):
        """Test page with mix of single-line and multi-line code."""
        html = """
        <div>
            <h2>Component Props</h2>
            <p>Required props: <code>name</code>, <code>value</code>, <code>onChange</code></p>
            <p>Optional: <code>defaultValue</code> and <code>disabled</code></p>
            <p>Full example:</p>
            <pre><code>function MyComponent({ name, value, onChange }) {
  return &lt;input name={name} value={value} onChange={onChange} /&gt;
}</code></pre>
            <p>Short form: <code>&lt;MyComponent name="test" /&gt;</code></p>
        </div>
        """
        
        extractor = HTMLCodeExtractor()
        blocks = await extractor.extract_blocks(html, "test.html")
        
        # Should extract the pre block (multi-line) and the JSX example (3+ words)
        assert len(blocks) == 2
        
        # Check the function block
        function_block = next(b for b in blocks if "function MyComponent" in b.code)
        assert "onChange" in function_block.code
        
        # Single-word inline code should appear in description
        assert function_block.description is not None
        assert "Required props" in function_block.description
        assert "name" in function_block.description
