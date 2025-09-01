"""HTML-based code block extractor for documentation crawling."""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


@dataclass
class ExtractedCodeBlock:
    """Represents an extracted code block with its context."""
    code: str
    language: str | None = None
    container_hierarchy: list[dict[str, Any]] = field(default_factory=list)
    context_before: list[str] = field(default_factory=list)
    container_type: str | None = None  # example, api-method, tutorial-step,
    # etc.
    title: str | None = None
    description: str | None = None


class HTMLCodeExtractor:
    """Extracts code blocks from HTML with surrounding documentation context."""

    # Elements to extract text content from
    CONTEXT_ELEMENTS = {
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'dt', 'dd', 'span', 'div'
    }


    # Code block selectors to find
    CODE_SELECTORS = [
        # Most common pattern - standalone pre tags
        ('pre', 'pre-direct'),

        # Standard code blocks
        ('pre > code', 'standard'),
        ('pre code', 'nested'),

        # Syntax highlighters
        ('div.highlight pre', 'highlight'),
        ('div.highlight pre code', 'highlight-nested'),
        ('div.codehilite pre', 'codehilite'),
        ('div[class*="highlight-"] pre', 'highlight-lang'),
        ('pre[class*="language-"]', 'prism'),
        ('code[class*="language-"]', 'prism-inline'),

        # Documentation systems
        ('div.sourceCode pre', 'pandoc'),
        ('div.code-block pre', 'generic-block'),
        ('div.codeblock pre', 'generic-block'),
        ('div[class*="code-example"] pre', 'example'),

        # API documentation
        ('div.api-example pre', 'api-example'),
        ('div.endpoint-example pre', 'endpoint-example'),

        # Interactive environments (usually we'd skip these but let's detect them)
        ('div.CodeMirror-code', 'codemirror'),
        ('div.monaco-editor', 'monaco'),

        # Code blocks that might be in aside/nav elements
        ('aside pre', 'aside-code'),
        ('aside code', 'aside-inline'),
        ('.sidebar pre', 'sidebar-code'),
        ('.sidebar code', 'sidebar-inline'),

        # Code in documentation navigation (sometimes shows examples)
        ('.docs-nav pre', 'nav-code'),
        ('.docs-nav code', 'nav-inline'),
        ('.table-of-contents code', 'toc-code'),

        # Links that contain code (common in docs)
        ('a > code', 'link-code'),
        ('a code', 'link-nested-code'),
    ]

    def __init__(self):
        """Initialize the code extractor."""
        self.stats = {
            'total_blocks': 0,
            'blocks_by_type': {},
            'languages_found': set()
        }

    def _process_code_block(self, block: Tag, selector_type: str) -> ExtractedCodeBlock | None:
        """
        Process a single code block element.
        
        Args:
            block: The code block element
            selector_type: Type of selector that found this block
            
        Returns:
            ExtractedCodeBlock or None if block should be skipped
        """
        # Skip if already processed (nested selectors might match same element)
        if block.get('data-processed'):
            return None

        block['data-processed'] = 'true'

        # Extract the code content
        raw_code_text = self._extract_code_text(block)

        # Skip empty or very short code blocks (likely inline code)
        if not raw_code_text or len(raw_code_text.strip()) < 10:
            return None

        # Language will be detected by LLM
        language = None

        # Use raw code text without formatting to preserve original
        code_text = raw_code_text

        # Skip inline code in sentences (unless it's multi-line)
        if self._is_inline_code(block) and '\n' not in code_text:
            return None

        # Extract surrounding context
        context = self._extract_context(block)

        # Classify container type
        container_type = self._classify_container(context['hierarchy'])

        # Create extracted block
        extracted = ExtractedCodeBlock(
            code=code_text,
            language=language,
            container_hierarchy=context['hierarchy'],
            context_before=context['before'],
            container_type=container_type,
            title=context.get('title'),
            description=context.get('description')
        )

        # Update stats
        self.stats['total_blocks'] += 1
        self.stats['blocks_by_type'][selector_type] = self.stats['blocks_by_type'].get(selector_type, 0) + 1

        return extracted

    def extract_code_blocks(self, html: str, url: str) -> list[ExtractedCodeBlock]:
        """
        Extract all code blocks from HTML with their documentation context (synchronous version).
        
        Args:
            html: Raw HTML content
            url: URL of the page (for logging)
            
        Returns:
            List of ExtractedCodeBlock objects
        """
        soup = BeautifulSoup(html, 'html.parser')


        extracted_blocks = []

        # Find all code blocks
        for selector, selector_type in self.CODE_SELECTORS:
            blocks = soup.select(selector)


            for block in blocks:
                extracted = self._process_code_block(block, selector_type)
                if extracted:
                    extracted_blocks.append(extracted)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Extracted {len(extracted_blocks)} code blocks from {url}")
            logger.debug(f"Stats: {self.stats}")

        return extracted_blocks

    async def _process_code_block_async(self, block: Tag, selector_type: str) -> ExtractedCodeBlock | None:
        """
        Process a single code block element with async language detection.
        
        Args:
            block: The code block element
            selector_type: Type of selector that found this block
            
        Returns:
            ExtractedCodeBlock or None if block should be skipped
        """
        # Skip if already processed (nested selectors might match same element)
        if block.get('data-processed'):
            return None

        block['data-processed'] = 'true'

        # Extract the code content
        raw_code_text = self._extract_code_text(block)

        # Skip empty or very short code blocks (likely inline code)
        if not raw_code_text or len(raw_code_text.strip()) < 10:
            return None

        # Language will be detected by LLM
        language = None

        # Use raw code text without formatting to preserve original
        code_text = raw_code_text

        # Skip inline code in sentences (unless it's multi-line)
        if self._is_inline_code(block) and '\n' not in code_text:
            return None

        # Extract surrounding context
        context = self._extract_context(block)

        # Classify container type
        container_type = self._classify_container(context['hierarchy'])

        # Create extracted block
        extracted = ExtractedCodeBlock(
            code=code_text,
            language=language,
            container_hierarchy=context['hierarchy'],
            context_before=context['before'],
            container_type=container_type,
            title=context.get('title'),
            description=context.get('description')
        )

        # Update stats
        self.stats['total_blocks'] += 1
        self.stats['blocks_by_type'][selector_type] = self.stats['blocks_by_type'].get(selector_type, 0) + 1

        return extracted

    async def extract_code_blocks_async(self, html: str, url: str) -> list[ExtractedCodeBlock]:
        """
        Extract all code blocks from HTML with their documentation context (async version with VS Code detection).
        
        Args:
            html: Raw HTML content
            url: URL of the page (for logging)
            
        Returns:
            List of ExtractedCodeBlock objects
        """
        soup = BeautifulSoup(html, 'html.parser')


        extracted_blocks = []

        # Find all code blocks
        for selector, selector_type in self.CODE_SELECTORS:
            blocks = soup.select(selector)

            for block in blocks:
                extracted = await self._process_code_block_async(block, selector_type)
                if extracted:
                    extracted_blocks.append(extracted)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Extracted {len(extracted_blocks)} code blocks from {url}")
            logger.debug(f"Stats: {self.stats}")

        return extracted_blocks

    def _extract_code_text(self, element: Tag) -> str:
        """Extract clean code text from an element."""
        # Clone the element to avoid modifying the original
        element_copy = element.__copy__()

        # Remove UI elements that might be inside code blocks
        ui_elements = ['button', 'svg', 'span.sr-only', 'div[role="tablist"]', 'div[role="tab"]']
        for selector in ui_elements:
            for ui_elem in element_copy.select(selector):
                ui_elem.decompose()

        # Remove elements with specific classes that indicate UI
        ui_classes = ['copy', 'copy-button', 'clipboard', 'tab', 'tabs', 'sr-only']
        for ui_elem in element_copy.find_all(True):
            if hasattr(ui_elem, 'get'):
                classes: list = ui_elem.get('class', None) or []
                classes_str = ' '.join(classes).lower()
                if any(ui_class in classes_str for ui_class in ui_classes):
                    ui_elem.decompose()

        # Remove any remaining links within code
        for link in element_copy.find_all('a'):
            if hasattr(link, 'unwrap'):
                link.unwrap()

        # Extract text while preserving meaningful whitespace but not adding extra spaces
        # between syntax highlighting spans
        code_text = self._extract_text_no_extra_spaces(element_copy)

        # Clean up common artifacts
        # Remove line numbers if they appear at start of lines
        lines = code_text.split('\n')
        cleaned_lines = []

        for line in lines:
            # Remove line numbers like "1: " or "10: " at start
            cleaned_line = re.sub(r'^\s*\d+:\s*', '', line)
            cleaned_lines.append(cleaned_line)

        return '\n'.join(cleaned_lines).strip()

    def _extract_text_no_extra_spaces(self, element: Tag) -> str:
        """Extract text from element without adding spaces between syntax highlighting spans."""
        # Handle different ways HTML might represent code with line breaks
        result: list[str] = []

        # Track if we're at the start of a new line-like element
        for elem in element.descendants:
            if isinstance(elem, str):
                # Preserve actual text content
                result.append(elem)
            elif hasattr(elem, 'name'):
                if elem.name == 'br':
                    # Convert <br> tags to newlines
                    result.append('\n')
                elif elem.name in ['div', 'p']:
                    # For block elements, check if this is a direct child
                    # and add newline before its content (except for first element)
                    parent_chain = []
                    current = elem
                    while current and current != element:
                        parent_chain.append(current)
                        current = current.parent

                    # Only add newline for direct children divs/p
                    if len(parent_chain) == 1 and result and not (result[-1].endswith('\n') or result[-1] == ''):
                        result.append('\n')

        text = ''.join(result)

        # Clean up the result
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            # Preserve indentation but remove trailing whitespace
            cleaned_lines.append(line.rstrip())

        # Join with newlines and remove any trailing whitespace
        # Also remove any leading empty lines
        return '\n'.join(cleaned_lines).strip()

    def _is_inline_code(self, element: Tag) -> bool:
        """Check if this is inline code (not a block)."""
        # If it's just a <code> tag without <pre>, likely inline
        if element.name == 'code' and not element.find_parent('pre'):
            return True

        # Check if parent is a paragraph or span (inline context)
        parent = element.parent
        if parent and parent.name in {'p', 'span', 'li', 'td'}:
            # But allow if it's in a list item that's specifically for code
            if parent.name == 'li':
                parent_classes: list = parent.get('class', None) or []
                if any('code' in cls or 'example' in cls for cls in parent_classes):
                    return False
            return True

        return False

    def _extract_context(self, code_element: Tag) -> dict[str, Any]:
        """Extract surrounding context for a code block."""
        context: dict[str, Any] = {
            'before': [],
            'hierarchy': [],
            'title': None,
            'description': None,
            'filename': None
        }

        # Walk up the DOM tree to find context
        current = code_element
        levels_up = 0

        while current.parent and levels_up < 4:
            parent = current.parent

            # Skip if we hit body or html
            if parent.name in {'body', 'html'}:
                break

            # Record hierarchy
            hierarchy_info = {
                'tag': parent.name,
                'classes': parent.get('class', None) or [],
                'id': parent.get('id')
            }
            context['hierarchy'].append(hierarchy_info)

            # Look for title in this container - only before the code element
            if not context['title']:
                # Check if code_element is descendant of current
                code_is_descendant = code_element in (current.descendants if hasattr(current, 'descendants') else [])
                
                for elem in parent.children:
                    # Stop when we reach the current element or its container
                    if elem == current or (code_is_descendant and elem == code_element):
                        break
                    # Skip navigation elements
                    if hasattr(elem, 'name') and elem.name in ['button', 'nav', 'a']:
                        continue
                    if hasattr(elem, 'name') and elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        title_text = elem.get_text(separator=' ', strip=True)
                        if title_text:
                            context['title'] = title_text
                            break

            # Look for filename in this container - only before the code element
            if not context['filename']:
                # Check for common filename indicators
                filename_elem = None
                code_is_descendant = code_element in (current.descendants if hasattr(current, 'descendants') else [])

                # Check for elements with filename-related classes
                for elem in parent.children:
                    # Stop when we reach the current element or its container
                    if elem == current or (code_is_descendant and elem == code_element):
                        break
                    
                    if hasattr(elem, 'name') and elem.name in ['div', 'span', 'code']:
                        if hasattr(elem, 'get'):
                            elem_classes = elem.get('class', None) or []
                        else:
                            elem_classes = []
                        if any('filename' in cls.lower() or 'file-name' in cls.lower()
                               or 'code-title' in cls.lower() for cls in elem_classes):
                            filename_elem = elem
                            break

                # Check for data attributes
                if not filename_elem and parent.get('data-filename'):
                    context['filename'] = parent.get('data-filename')
                elif not filename_elem and parent.get('title') and '.' in (parent.get('title') or ''):
                    # Sometimes filename is in title attribute
                    context['filename'] = parent.get('title')
                elif filename_elem:
                    filename_text = filename_elem.get_text(strip=True)
                    if filename_text and ('.' in filename_text or filename_text in ['Dockerfile', 'Makefile']):
                        context['filename'] = filename_text

            # Look for content elements in the parent container that appear before the code block
            if parent and hasattr(parent, 'children'):
                children_list = list(parent.children)
                
                # Find where the current element is in the parent's children
                for idx, child in enumerate(children_list):
                    if child == current:
                        # We found the code block, now get content before it
                        # but stop if we hit another code block
                        for i in range(idx - 1, -1, -1):  # Work backwards from current element
                            prev_child = children_list[i]
                            if hasattr(prev_child, 'name'):
                                # Stop if we hit another code block
                                if prev_child.name in ['pre', 'code']:
                                    break
                                # Also check if this element contains a code block
                                if prev_child.name == 'div' and prev_child.find(['pre', 'code']):
                                    break
                                    
                                # Collect content elements
                                if prev_child.name in ['p', 'span', 'h2', 'h3', 'h4']:
                                    text = prev_child.get_text(separator=' ', strip=True)
                                    if text and len(text) > 10:
                                        # Insert at beginning since we're going backwards
                                        context['before'].insert(0, text)
                                elif prev_child.name == 'ul':
                                    # Get text from list items
                                    list_items = []
                                    for li in prev_child.find_all('li'):
                                        text = li.get_text(separator=' ', strip=True)
                                        if text and len(text) > 10:
                                            list_items.append(text)
                                    # Insert all list items at beginning
                                    for item in reversed(list_items):
                                        context['before'].insert(0, item)
                        break  # Stop once we've processed elements before the code block

            current = parent
            levels_up += 1

        # Extract filename from context if not found
        if not context['filename'] and context['before']:
            # Look for filename patterns in context
            for text in context['before']:
                # Common patterns: "app/page.tsx", "src/index.js", "package.json"
                if ('/' in text or '.' in text) and len(text) < 100:
                    # Check if it looks like a filename
                    import re
                    filename_pattern = r'^[\w\-\/]+\.\w+$|^Dockerfile$|^Makefile$|^\\.[\w]+$'
                    if re.match(filename_pattern, text.strip()):
                        context['filename'] = text.strip()
                        break

        # Set description from first paragraph in context
        if context['before'] and not context['description']:
            # Look for a paragraph that's not a title
            for text in context['before']:
                if not any(text.startswith(h) for h in ['#', 'Step', 'Example']):
                    context['description'] = text
                    break

        return context

    def _classify_container(self, hierarchy: list[dict[str, Any]]) -> str | None:
        """Classify the container type based on hierarchy."""
        # Check classes and IDs in the hierarchy
        for level in hierarchy:
            classes = ' '.join(level.get('classes', [])).lower()
            elem_id = (level.get('id') or '').lower()

            # API documentation patterns
            if any(pattern in classes or pattern in elem_id
                   for pattern in ['api', 'endpoint', 'method', 'operation']):
                return 'api-method'

            # Example patterns
            if any(pattern in classes or pattern in elem_id
                   for pattern in ['example', 'sample', 'demo', 'snippet']):
                return 'example'

            # Tutorial/guide patterns
            if any(pattern in classes or pattern in elem_id
                   for pattern in ['tutorial', 'guide', 'step', 'instruction']):
                return 'tutorial-step'

            # Configuration patterns
            if any(pattern in classes or pattern in elem_id
                   for pattern in ['config', 'configuration', 'setup', 'settings']):
                return 'configuration'

            # Reference documentation
            if any(pattern in classes or pattern in elem_id
                   for pattern in ['reference', 'documentation', 'docs']):
                return 'reference'

        return None

    def format_output(self, blocks: list[ExtractedCodeBlock]) -> str:
        """Format extracted blocks for debugging/display."""
        output = []

        for i, block in enumerate(blocks, 1):
            output.append(f"\n{'='*60}")
            output.append(f"Code Block #{i}")
            output.append(f"{'='*60}")

            if block.language:
                output.append(f"Language: {block.language}")

            if block.container_type:
                output.append(f"Type: {block.container_type}")

            if block.container_hierarchy:
                containers = " > ".join([
                    f"{h['tag']}.{'.'.join(h['classes'])}" if h['classes']
                    else h['tag']
                    for h in block.container_hierarchy[:3]
                ])
                output.append(f"Container: {containers}")

            if block.title:
                output.append(f"\nTitle: {block.title}")

            if block.context_before:
                output.append("\nContext Before:")
                for ctx in block.context_before[-2:]:  # Last 2 items
                    output.append(f"  - {ctx[:100]}...")

            output.append(f"\nCode ({len(block.code)} chars):")
            output.append("-" * 40)
            # Show first 10 lines or 500 chars
            code_preview = block.code[:500]
            if len(block.code) > 500:
                code_preview += "\n... (truncated)"
            output.append(code_preview)
            output.append("-" * 40)

        output.append(f"\n\nTotal blocks found: {len(blocks)}")
        if self.stats['languages_found']:
            output.append(f"Languages: {', '.join(sorted(self.stats['languages_found']))}")

        return '\n'.join(output)
