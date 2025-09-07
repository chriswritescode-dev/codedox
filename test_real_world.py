"""Test with real-world HTML examples to verify improved filtering."""

from src.crawler.html_code_extractor import HTMLCodeExtractor

def test_real_world_examples():
    # Example from React documentation
    html = """
    <div>
        <h2>Using State</h2>
        <p>The <code>useState</code> Hook lets you add React state to function components.</p>
        <p>Call it like <code>useState(initialValue)</code> to declare a state variable.</p>
        <p>Access properties with <code>state.value</code> or <code>this.props.children</code>.</p>
        <p>Use types like <code>React.FC&lt;Props&gt;</code> or <code>React.Component</code>.</p>
        
        <p>Here's a complete example:</p>
        <pre><code class="language-jsx">
import React, { useState } from 'react';

function Counter() {
    const [count, setCount] = useState(0);
    
    return (
        &lt;div&gt;
            &lt;p&gt;You clicked {count} times&lt;/p&gt;
            &lt;button onClick={() =&gt; setCount(count + 1)}&gt;
                Click me
            &lt;/button&gt;
        &lt;/div&gt;
    );
}
        </code></pre>
        
        <p>You can also use inline expressions like <code>onClick={() =&gt; alert('Hi!')}</code></p>
        <p>Or simple assignments: <code>disabled = true</code></p>
        <p>But avoid single references like <code>PropTypes</code> or <code>Component.defaultProps</code></p>
    </div>
    """
    
    extractor = HTMLCodeExtractor()
    blocks = extractor.extract_code_blocks(html, "test.html")
    
    print(f"\nTotal blocks extracted: {len(blocks)}")
    print("-" * 60)
    
    for i, block in enumerate(blocks, 1):
        # Truncate long code for display
        code_display = block.code.replace('\n', '\\n')[:80]
        if len(block.code) > 80:
            code_display += "..."
        print(f"{i}. [{block.language or 'unknown'}] {code_display}")
    
    # Verify filtering is working correctly
    codes = [block.code for block in blocks]
    
    # These single tokens should NOT be extracted
    assert not any("useState" == code for code in codes), "Single 'useState' should be filtered"
    assert not any("useState(initialValue)" == code for code in codes), "Function calls should be filtered"  
    assert not any("state.value" == code for code in codes), "Property access should be filtered"
    assert not any("this.props.children" == code for code in codes), "Chain access should be filtered"
    assert not any("React.FC<Props>" == code for code in codes), "Type annotations should be filtered"
    assert not any("React.Component" == code for code in codes), "Class names should be filtered"
    assert not any("PropTypes" == code for code in codes), "Single identifiers should be filtered"
    assert not any("Component.defaultProps" == code for code in codes), "Static properties should be filtered"
    
    # These should BE extracted (they contain actual code)
    assert any("onClick={() => alert('Hi!')}" in code for code in codes), "Arrow functions should be extracted"
    assert any("disabled = true" in code for code in codes), "Assignments should be extracted"
    assert any("import React" in code for code in codes), "Pre block should be extracted"
    
    print("\n✅ All filtering rules working correctly!")
    print("\nFiltered out (single tokens):")
    print("  • useState")
    print("  • useState(initialValue)")
    print("  • state.value")
    print("  • React.FC<Props>")
    print("  • PropTypes")
    print("  • Component.defaultProps")
    
    print("\nExtracted (real code):")
    for block in blocks:
        if len(block.code) < 50:  # Only show short ones for clarity
            print(f"  • {block.code}")

if __name__ == "__main__":
    test_real_world_examples()