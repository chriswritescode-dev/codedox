# HTML Code Extraction Refactor Plan

## Current Problem
The current implementation is too complex and captures content that appears AFTER code blocks, not just before. It also only processes certain element types (p, ul, li) which misses important context.

## New Approach - Simple and Effective

### Core Algorithm
1. **Find all code blocks** in the document
2. For each code block:
   - **Traverse upward** through the DOM tree to find ALL elements at the same level or parent levels
   - **Find the nearest heading** (h1-h6) that appears before the code block in document order
   - **Collect ALL content** between that heading and the code block as the description
   - Stop at the code block - never include content after it

### Key Principles

#### 1. Document Order Matters
- We need to determine what comes "before" in the actual rendered document
- This means checking the position of elements in their parent containers
- An element is "before" if it's an earlier sibling or in an earlier ancestor sibling

#### 2. Heading Discovery
- Start from the code block
- Check all siblings before it for headings
- If no heading found, go up one level and repeat
- Continue until we find a heading or reach the body/main element
- The first heading we find (searching upward and backward) is our title

#### 3. Content Collection
- Once we have a heading, collect EVERYTHING between it and the code block
- This includes ALL element types, not just p/ul/li
- Convert all text content to the description
- Join multiple elements with newlines

#### 4. Simplifications
- Remove all complex pattern matching for container types
- Remove the multi-pass approach
- Remove restrictions on which elements to process
- Just find heading → collect everything until code block → done

### Implementation Steps

1. **Find Code Blocks**
   ```python
   def find_code_blocks(soup):
       # Find all <pre> and standalone <code> elements
       # Skip inline code in p, span, etc.
   ```

2. **Find Preceding Heading**
   ```python
   def find_preceding_heading(code_element):
       # Starting from code element
       # Work up the tree level by level
       # At each level, check all previous siblings
       # Return first heading found
   ```

3. **Collect Content Between**
   ```python
   def collect_content_between(heading_element, code_element):
       # Determine the common container
       # Collect all elements after heading
       # Stop when we reach the code element
       # Return all text content
   ```

### Example Structure Handling

For modern docs like BullMQ:
```html
<main>
  <header>
    <h1>Adding jobs in bulk</h1>  <!-- This becomes the title -->
  </header>
  <div class="grid">
    <p>Sometimes it is necessary...</p>  <!-- These become -->
    <p>You may think of queue.addBulk...</p>  <!-- the description -->
    <div class="codeblock">
      <pre><code>...</code></pre>  <!-- Stop here -->
    </div>
    <p>It is possible to add...</p>  <!-- NOT included -->
  </div>
</main>
```

Result:
- Title: "Adding jobs in bulk"
- Description: "Sometimes it is necessary... You may think of queue.addBulk..."
- Code: The actual code content

### Benefits of This Approach
1. **Simpler**: No complex container detection or pattern matching
2. **More accurate**: Gets all relevant content, not just specific elements
3. **Correct ordering**: Only captures content BEFORE the code block
4. **Universal**: Works with any HTML structure
5. **Maintainable**: Easy to understand and debug

### Edge Cases to Handle
1. **No heading found**: Use None for title
2. **No content between heading and code**: Empty description
3. **Multiple code blocks after one heading**: Each gets the content between the heading and itself (not shared)
4. **Nested code blocks**: Process parent first, mark as processed

### Testing Strategy
1. Test with simple HTML (heading → paragraph → code)
2. Test with complex modern docs (BullMQ style)
3. Test with multiple code blocks
4. Test with no headings
5. Test with nested structures