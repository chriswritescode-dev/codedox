"""HTML-based code block extractor for documentation crawling."""

import logging
import re
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

logger = logging.getLogger(__name__)


@dataclass
class ExtractedCodeBlock:
    """Represents a code block extracted from HTML."""
    code: str
    language: str | None = None
    container_hierarchy: list[dict[str, Any]] | None = None
    context_before: list[str] | None = None
    title: str | None = None
    description: str | None = None


class HTMLCodeExtractor:
    """Extracts code blocks from HTML with surrounding documentation context."""

    # Elements to extract text content from
    CONTEXT_ELEMENTS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "dt", "dd", "span", "div"}

    CODE_SELECTORS = [
        # Get all pre elements with code children (most common pattern)
        ("pre > code", "pre-code-block"),
        # Get all pre elements without code children
        ("pre", "pre-block"),
        # Get standalone code elements (not inside pre)
        ("code", "code-block"),
    ]

    def __init__(self):
        """Initialize the code extractor."""
        self.stats = {"total_blocks": 0, "blocks_by_type": {}, "languages_found": set()}


    
    def extract_code_blocks(self, html: str, url: str) -> list[ExtractedCodeBlock]:
        """
        Extract all code blocks with their preceding context using simplified approach.
        
        For each code block:
        1. Find the nearest preceding heading (h1-h6) by traversing up and backward
        2. Collect ALL content between the heading and code block
        3. Stop at the code block - never include content after it
        
        Args:
            html: Raw HTML content
            url: URL of the page (for logging)
            
        Returns:
            List of ExtractedCodeBlock objects
        """
        soup = BeautifulSoup(html, "html.parser")
        
        extracted_blocks: list[ExtractedCodeBlock] = []
        processed_code_blocks: set[Tag] = set()
        
        def find_code_blocks(soup: BeautifulSoup) -> list[Tag]:
            """Find all code blocks we want to extract."""
            code_blocks: list[Tag] = []
            
            # Find all <pre> elements (most common for code blocks)
            for pre in soup.find_all('pre'):
                if pre not in processed_code_blocks:
                    code_blocks.append(pre)
            
            # Find standalone <code> elements (not inside <pre>)
            for code in soup.find_all('code'):
                if code.parent and code.parent.name != 'pre':
                    text = code.get_text().strip()
                    
                    # Skip ALL single-line inline code
                    if '\n' not in text:
                        continue
                    
                    # Only keep multi-line code blocks
                    if code not in processed_code_blocks:
                        code_blocks.append(code)
            
            return code_blocks
        
        def find_preceding_heading(code_element: Tag) -> tuple[Tag | None, Tag | None]:
            """
            Find the nearest heading that precedes the code block in document order.
            Returns: (heading_element, common_container)
            """
            current: Tag | None = code_element
            heading: Tag | None = None
            common_container: Tag | None = None
            
            # Traverse up the tree
            while current and hasattr(current, 'name') and current.name not in ['body', 'html']:
                parent = current.parent
                if not parent or not hasattr(parent, 'name'):
                    break
                
                # Get all children of parent
                children = [c for c in parent.children if hasattr(c, 'name') and c.name]
                
                # Find index of current element
                try:
                    current_index = children.index(current)
                except ValueError:
                    # Current not directly in children, it's nested deeper
                    # Find which child contains current
                    current_index = -1
                    for i, child in enumerate(children):
                        if hasattr(child, 'descendants') and current in child.descendants:
                            current_index = i
                            break
                
                if current_index > 0:
                    # Check previous siblings for headings
                    for i in range(current_index - 1, -1, -1):
                        sibling = children[i]
                        
                        # Direct heading
                        if isinstance(sibling, Tag) and sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                            heading = sibling
                            common_container = parent if isinstance(parent, Tag) else None
                            return heading, common_container
                        
                        # Heading inside sibling
                        if isinstance(sibling, Tag) and hasattr(sibling, 'find_all'):
                            # Get the last heading in this sibling (closest to our code)
                            headings = sibling.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                            if headings:
                                last_heading = headings[-1]  # Last heading is closest
                                if isinstance(last_heading, Tag):
                                    heading = last_heading
                                    common_container = parent if isinstance(parent, Tag) else None
                                    return heading, common_container
                
                # Move up to parent
                if isinstance(parent, Tag):
                    current = parent
                else:
                    break
            
            return heading, common_container
        
        def collect_content_between(heading: Tag | None, code_element: Tag, container: Tag | None, previous_code: Tag | None = None) -> list[str]:
            """
            Collect all text content between heading and code block.
            If no heading, collect content from start of container.
            If previous_code is provided, collect content between previous_code and current code_element.
            """
            descriptions: list[str] = []
            
            if not container:
                # No common container found, use code's parent
                container = code_element.parent
                if not container:
                    return descriptions
            
            # Determine if we should process in document order
            def get_element_position(elem: Tag) -> tuple[int, ...]:
                """Get position of element as tuple of indices in tree."""
                position: list[int] = []
                current = elem
                while current and current != container:
                    if current.parent:
                        siblings = [s for s in current.parent.children if hasattr(s, 'name')]
                        try:
                            idx = siblings.index(current)
                            position.insert(0, idx)
                        except ValueError:
                            position.insert(0, 0)
                    current = current.parent
                return tuple(position)
            
            # Get positions
            heading_pos = get_element_position(heading) if heading else None
            code_pos = get_element_position(code_element)
            prev_code_pos = get_element_position(previous_code) if previous_code else None
            
            # Collect all text elements in container
            for elem in container.descendants:
                if not hasattr(elem, 'name'):
                    continue
                
                # Skip the code block itself and its children
                if elem == code_element or code_element in (elem.descendants if hasattr(elem, 'descendants') else []):
                    continue
                
                # Skip previous code block and its children
                if previous_code and (elem == previous_code or previous_code in (elem.descendants if hasattr(elem, 'descendants') else [])):
                    continue
                
                # Check if this element is inside a <pre> tag (part of a code block)
                # This is critical - we need to check ancestors, not just the element itself
                is_inside_pre = False
                parent = elem.parent
                while parent and hasattr(parent, 'name'):
                    if parent.name == 'pre':
                        is_inside_pre = True
                        break
                    parent = parent.parent
                
                if is_inside_pre:
                    continue
                
                # Skip UI elements
                if elem.name in ['button', 'nav', 'svg', 'script', 'style', 'noscript']:
                    continue
                
                # Skip <pre> elements (code blocks)
                if elem.name == 'pre':
                    continue
                
                # Skip any element that contains <pre> descendants (containers of code blocks)
                # This must come BEFORE we check positions or extract text
                if hasattr(elem, 'find'):
                    if elem.find('pre'):
                        continue
                
                # Skip <code> elements that are multi-line or inside <pre> (block code)
                # But keep inline <code> elements (single line, not in <pre>)
                if elem.name == 'code':
                    # Check if it contains newlines (multi-line code)
                    code_text = elem.get_text()
                    if '\n' in code_text:
                        continue
                
                # Get position of this element
                elem_pos = get_element_position(elem)
                
                # Check if element is between heading/previous code and current code
                if prev_code_pos:
                    # Must be after previous code and before current code
                    if elem_pos <= prev_code_pos or elem_pos >= code_pos:
                        continue
                elif heading_pos:
                    # Must be after heading and before code
                    if elem_pos <= heading_pos or elem_pos >= code_pos:
                        continue
                else:
                    # No heading, just before code
                    if elem_pos >= code_pos:
                        continue
                
                # Extract text from various elements
                if elem.name in ['p', 'div', 'span', 'li', 'dt', 'dd', 'td', 'th']:
                    # Check if this element has child elements we'll process separately
                    has_child_content = any(
                        child.name in ['p', 'li', 'dt', 'dd']
                        for child in elem.children
                        if hasattr(child, 'name')
                    )
                    
                    if not has_child_content:
                        # Check if element contains buttons - if so, extract text without button content
                        if elem.find('button'):
                            # Extract text from all non-button children
                            text_parts = []
                            for child in elem.descendants:
                                # Check if it's a text node
                                if isinstance(child, NavigableString):
                                    # Check if this text node is inside a button
                                    parent = child.parent
                                    is_in_button = False
                                    while parent and parent != elem:
                                        if hasattr(parent, 'name') and parent.name == 'button':
                                            is_in_button = True
                                            break
                                        parent = parent.parent
                                    
                                    if not is_in_button:
                                        text = str(child).strip()
                                        if text:
                                            text_parts.append(text)
                            text = ' '.join(text_parts)
                        else:
                            # No buttons, extract normally
                            text = elem.get_text(separator=' ', strip=True)
                        
                        if text and len(text) > 10:
                            # Avoid duplicates
                            if not descriptions or text not in descriptions[-1]:
                                descriptions.append(text)
            
            return descriptions
        
        def build_hierarchy(element: Tag) -> list[dict[str, Any]]:
            """Build container hierarchy for the element."""
            hierarchy = []
            current = element.parent
            
            for _ in range(4):  # Limit depth
                if not current or current.name in ['body', 'html']:
                    break
                    
                hierarchy_info: dict[str, Any] = {
                    'tag': current.name,
                    'classes': current.get('class', []) if hasattr(current, 'get') else [],
                    'id': current.get('id') if hasattr(current, 'get') else None
                }
                hierarchy.append(hierarchy_info)
                current = current.parent
            
            return hierarchy
        

        
        # Find all code blocks
        code_blocks = find_code_blocks(soup)
        
        # Track previous code block for each heading
        previous_code_by_heading: dict[Tag | None, Tag] = {}
        
        for code_element in code_blocks:
            # Skip if already processed
            if code_element in processed_code_blocks:
                continue
            
            # Mark as processed
            processed_code_blocks.add(code_element)
            
            # Get the actual code element (might be child <code> of <pre>)
            actual_code_element = code_element
            if code_element.name == 'pre':
                code_child = code_element.find('code')
                if code_child:
                    actual_code_element = code_child
                    processed_code_blocks.add(code_child)
            elif code_element.parent and code_element.parent.name == 'pre':
                processed_code_blocks.add(code_element.parent)
            
            # Extract code text
            raw_code_text = self._extract_code_text(actual_code_element)
            
            # Skip empty code blocks
            if not raw_code_text or not raw_code_text.strip():
                continue
            
            # Find preceding heading
            heading, container = find_preceding_heading(code_element)
            
            # Get previous code block for this heading
            previous_code = previous_code_by_heading.get(heading)
            
            # Collect content between heading/previous code and current code
            descriptions = collect_content_between(heading, code_element, container, previous_code)
            
            # Update previous code for this heading
            previous_code_by_heading[heading] = code_element
            
            # Build hierarchy
            hierarchy = build_hierarchy(code_element)
            
            # Extract title text if heading found
            title = None
            if heading:
                title = heading.get_text(separator=' ', strip=True)
            
            # Create extracted block
            extracted = ExtractedCodeBlock(
                code=raw_code_text,
                language=None,  # Will be detected by LLM
                container_hierarchy=hierarchy,
                context_before=descriptions.copy(),
                title=title,
                description='\n'.join(descriptions) if descriptions else None
            )
            
            extracted_blocks.append(extracted)
            
            # Update stats
            self.stats['total_blocks'] += 1
            self.stats['blocks_by_type']['simplified'] = (
                self.stats['blocks_by_type'].get('simplified', 0) + 1
            )
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Extracted {len(extracted_blocks)} code blocks from {url} (simplified approach)")
            logger.debug(f"Stats: {self.stats}")
        
        return extracted_blocks



    def _extract_code_text(self, element: Tag) -> str:
        """Extract clean code text from an element."""
        # Clone the element to avoid modifying the original
        element_copy = element.__copy__()

        # Remove UI elements that might be inside code blocks
        ui_elements = ["button", "svg", "span.sr-only", 'div[role="tablist"]', 'div[role="tab"]']
        for selector in ui_elements:
            for ui_elem in element_copy.select(selector):
                ui_elem.decompose()

        # Remove elements with specific classes that indicate UI
        ui_classes = ["copy", "copy-button", "clipboard", "tab", "tabs", "sr-only"]
        for ui_elem in element_copy.find_all(True):
            if hasattr(ui_elem, "get"):
                classes = ui_elem.get("class", [])
                if not isinstance(classes, list):
                    classes = []
                if classes:  # Only process if we have classes
                    classes_str = " ".join(str(c) for c in classes).lower()
                    if any(ui_class in classes_str for ui_class in ui_classes):
                        ui_elem.decompose()

        # Remove any remaining links within code
        for link in element_copy.find_all("a"):
            if hasattr(link, "unwrap"):
                link.unwrap()

        # Extract text while preserving meaningful whitespace but not adding extra spaces
        # between syntax highlighting spans
        code_text = self._extract_text_no_extra_spaces(element_copy)

        # Clean up common artifacts
        # Remove line numbers if they appear at start of lines
        lines = code_text.split("\n")
        cleaned_lines = []

        for line in lines:
            # Remove line numbers like "1: " or "10: " at start
            cleaned_line = re.sub(r"^\s*\d+:\s*", "", line)
            cleaned_lines.append(cleaned_line)

        return "\n".join(cleaned_lines).strip()

    def _extract_text_no_extra_spaces(self, element: Tag) -> str:
        """Extract text from element without adding spaces between syntax highlighting spans."""
        # Handle different ways HTML might represent code with line breaks
        result: list[str] = []

        # Track if we're at the start of a new line-like element
        for elem in element.descendants:
            if isinstance(elem, str):
                # Preserve actual text content
                result.append(elem)
            elif hasattr(elem, "name"):
                if elem.name == "br":
                    # Convert <br> tags to newlines
                    result.append("\n")
                elif elem.name in ["div", "p"]:
                    # For block elements, check if this is a direct child
                    # and add newline before its content (except for first element)
                    parent_chain = []
                    current = elem
                    while current and current != element:
                        parent_chain.append(current)
                        current = current.parent

                    # Only add newline for direct children divs/p
                    if (
                        len(parent_chain) == 1
                        and result
                        and not (result[-1].endswith("\n") or result[-1] == "")
                    ):
                        result.append("\n")

        text = "".join(result)

        # Clean up the result
        lines = text.split("\n")
        cleaned_lines = []
        for line in lines:
            # Preserve indentation but remove trailing whitespace
            cleaned_lines.append(line.rstrip())

        # Join with newlines and remove any trailing whitespace
        # Also remove any leading empty lines
        return "\n".join(cleaned_lines).strip()

    def _classify_container(self, hierarchy: list[dict[str, Any]]) -> str | None:
        """Classify the container type based on hierarchy."""
        # Check classes and IDs in the hierarchy
        for level in hierarchy:
            classes = " ".join(level.get("classes", [])).lower()
            elem_id = (level.get("id") or "").lower()

            # API documentation patterns
            if any(
                pattern in classes or pattern in elem_id
                for pattern in ["api", "endpoint", "method", "operation"]
            ):
                return "api-method"

            # Example patterns
            if any(
                pattern in classes or pattern in elem_id
                for pattern in ["example", "sample", "demo", "snippet"]
            ):
                return "example"

            # Tutorial/guide patterns
            if any(
                pattern in classes or pattern in elem_id
                for pattern in ["tutorial", "guide", "step", "instruction"]
            ):
                return "tutorial-step"

            # Configuration patterns
            if any(
                pattern in classes or pattern in elem_id
                for pattern in ["config", "configuration", "setup", "settings"]
            ):
                return "configuration"

            # Reference documentation
            if any(
                pattern in classes or pattern in elem_id
                for pattern in ["reference", "documentation", "docs"]
            ):
                return "reference"

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



            if block.container_hierarchy:
                containers = " > ".join(
                    [
                        f"{h['tag']}.{'.'.join(h['classes'])}" if h["classes"] else h["tag"]
                        for h in block.container_hierarchy[:3]
                    ]
                )
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
        if self.stats["languages_found"]:
            output.append(f"Languages: {', '.join(sorted(self.stats['languages_found']))}")

        return "\n".join(output)
