"""HTML code extractor with semantic context extraction."""

import logging
import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from .base import BaseCodeExtractor
from .models import ExtractedCodeBlock, ExtractedContext

logger = logging.getLogger(__name__)


class HTMLCodeExtractor(BaseCodeExtractor):
    """Extract code blocks from HTML with semantic context."""
    
    def __init__(self):
        """Initialize the HTML code extractor."""
        self.stats = {"total_blocks": 0, "blocks_by_type": {}, "languages_found": set()}
    
    def extract_blocks(self, content: str, source_url: str | None = None) -> list[ExtractedCodeBlock]:
        """
        Extract all code blocks with their preceding context using simplified approach.
        
        For each code block:
        1. Find the nearest preceding heading (h1-h6) by traversing up and backward
        2. Collect ALL content between the heading and code block
        3. Stop at the code block - never include content after it
        
        Args:
            content: Raw HTML content
            source_url: URL of the page (for logging)
            
        Returns:
            List of ExtractedCodeBlock objects
        """
        soup = BeautifulSoup(content, "html.parser")
        
        extracted_blocks: list[ExtractedCodeBlock] = []
        processed_code_blocks: set[Tag] = set()
        
        # Get the main page title (H1)
        main_title = self._get_main_title(soup)
        
        # Find all code blocks
        code_blocks = self._find_code_blocks(soup, processed_code_blocks)
        
        # Track previous code block for each heading
        previous_code_by_heading: dict[tuple[str | None, Tag | None], Tag] = {}
        
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
            
            # Skip empty code blocks or single-line code
            if not self.should_extract_code_block(raw_code_text):
                continue
            
            # Find preceding heading
            heading_text, heading_element = self.find_preceding_heading(code_element, 0)
            
            # Get previous code block for this heading
            heading_key = (heading_text, heading_element)
            previous_code = previous_code_by_heading.get(heading_key)
            
            # Extract context between heading/previous code and current code
            context = self.extract_context_between(
                code_element,
                heading_element,
                previous_code
            )
            
            # Update context with title combining section heading with page title
            if heading_text:
                if main_title and main_title != heading_text:
                    # Combine section heading with main title like "Examples | CodeDox"
                    context.title = f"{heading_text} | {main_title}"
                else:
                    context.title = heading_text
            elif main_title:
                # Use main title if no section heading
                context.title = main_title
            
            # Update previous code block for this heading
            previous_code_by_heading[heading_key] = code_element
            
            # Create extracted block
            extracted = ExtractedCodeBlock(
                code=raw_code_text,
                language=None,  # Will be detected by LLM
                context=context,
                source_url=source_url
            )
            
            extracted_blocks.append(extracted)
            
            # Update stats
            self.stats['total_blocks'] += 1
            self.stats['blocks_by_type']['html'] = (
                self.stats['blocks_by_type'].get('html', 0) + 1
            )
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Extracted {len(extracted_blocks)} code blocks from {source_url}")
            logger.debug(f"Stats: {self.stats}")
        
        return extracted_blocks
    
    def _get_main_title(self, soup: BeautifulSoup) -> str | None:
        """Get the main page title from H1 tag."""
        h1 = soup.find('h1')
        if h1:
            # Get text and clean it up
            title = h1.get_text(strip=True)
            if title:
                return title
        return None
    
    def find_preceding_heading(self, element: Tag, position: int = 0) -> tuple[str | None, Tag | None]:
        """
        Find the nearest heading that precedes the code block in document order.
        
        Args:
            element: The code block element
            position: Not used for HTML (kept for interface compatibility)
            
        Returns:
            Tuple of (heading_text, heading_element)
        """
        current: Tag | None = element
        heading: Tag | None = None
        heading_text: str | None = None
        
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
                        heading_text = sibling.get_text(separator=' ', strip=True)
                        return heading_text, heading
                    
                    # Heading inside sibling
                    if isinstance(sibling, Tag) and hasattr(sibling, 'find_all'):
                        # Get the last heading in this sibling (closest to our code)
                        headings = sibling.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                        if headings:
                            last_heading = headings[-1]  # Last heading is closest
                            if isinstance(last_heading, Tag):
                                heading = last_heading
                                heading_text = last_heading.get_text(separator=' ', strip=True)
                                return heading_text, heading
            
            # Move up to parent
            if isinstance(parent, Tag):
                current = parent
            else:
                break
        
        return heading_text, heading
    
    def extract_context_between(self, code_element: Tag, heading: Tag | None, previous_code: Tag | None) -> ExtractedContext:
        """
        Extract and clean context between heading and code block.
        
        Args:
            code_element: The code block element
            heading: The preceding heading element (if found)
            previous_code: The previous code block under same heading (if any)
            
        Returns:
            Extracted context with description and raw content
        """
        descriptions: list[str] = []
        raw_content: list[str] = []
        
        # Find common container
        container = self._find_common_container(code_element, heading)
        if not container:
            container = code_element.parent
            if not container:
                return ExtractedContext()
        
        # Get positions
        heading_pos = self._get_element_position(heading, container) if heading else None
        code_pos = self._get_element_position(code_element, container)
        prev_code_pos = self._get_element_position(previous_code, container) if previous_code else None
        
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
            if self._is_inside_pre(elem):
                continue
            
            # Skip UI elements
            if elem.name in ['button', 'nav', 'svg', 'script', 'style', 'noscript']:
                continue
            
            # Skip <pre> elements (code blocks)
            if elem.name == 'pre':
                continue
            
            # Skip any element that contains <pre> descendants (containers of code blocks)
            if hasattr(elem, 'find') and elem.find('pre'):
                continue
            
            # Skip <code> elements that would be extracted as code blocks
            if elem.name == 'code':
                code_text = elem.get_text()
                if self.should_extract_code_block(code_text):
                    continue
            
            # Get position of this element
            elem_pos = self._get_element_position(elem, container)
            
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
                    text = self._extract_element_text(elem)
                    if text and len(text) > 10:
                        # Avoid duplicates
                        if not descriptions or text not in descriptions[-1]:
                            descriptions.append(text)
                            raw_content.append(elem.prettify() if hasattr(elem, 'prettify') else str(elem))
        
        # Join descriptions and clean up
        description = ' '.join(descriptions) if descriptions else None
        
        if description:
            # Filter noise using HTML-specific cleaning
            description = self._clean_html_text(description)
        
        return ExtractedContext(
            title=None,  # Will be set by the calling method
            description=description,
            raw_content=raw_content
        )
    

    def _find_code_blocks(self, soup: BeautifulSoup, processed: set[Tag]) -> list[Tag]:
        """Find all code blocks we want to extract."""
        code_blocks: list[Tag] = []
        
        # Find all <pre> elements (most common for code blocks)
        for pre in soup.find_all('pre'):
            if pre not in processed:
                # Check if the content should be extracted
                text = pre.get_text().strip()
                if self.should_extract_code_block(text):
                    code_blocks.append(pre)
        
        # Find standalone <code> elements (not inside <pre>)
        for code in soup.find_all('code'):
            if code.parent and code.parent.name != 'pre':
                # Skip if inside a button element
                if code.find_parent('button'):
                    continue
                    
                text = code.get_text().strip()
                
                # Check if this inline code should be extracted
                if not self.should_extract_code_block(text):
                    continue
                
                # Add the code block
                if code not in processed:
                    code_blocks.append(code)
        
        return code_blocks
    
    def _find_common_container(self, elem1: Tag | None, elem2: Tag | None) -> Tag | None:
        """Find the common container for two elements."""
        if not elem1:
            return elem2.parent if elem2 else None
        if not elem2:
            return elem1.parent
        
        # Get all parents of elem1
        parents1 = []
        current = elem1.parent
        while current:
            parents1.append(current)
            current = current.parent
        
        # Find first common parent with elem2
        current = elem2.parent
        while current:
            if current in parents1:
                return current
            current = current.parent
        
        return None
    
    def _get_element_position(self, elem: Tag | None, container: Tag) -> tuple[int, ...]:
        """Get position of element as tuple of indices in tree."""
        if not elem:
            return ()
            
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
    
    def _is_inside_pre(self, elem: Tag) -> bool:
        """Check if element is inside a <pre> tag."""
        parent = elem.parent
        while parent and hasattr(parent, 'name'):
            if parent.name == 'pre':
                return True
            parent = parent.parent
        return False
    
    def _extract_element_text(self, elem: Tag) -> str:
        """Extract text from element, handling buttons and other special cases."""
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
            return ' '.join(text_parts)
        else:
            # No buttons, extract normally
            return elem.get_text(separator=' ', strip=True)
    
    def _clean_html_text(self, text: str) -> str:
        """Clean HTML-specific noise from text."""
        # Remove common UI text patterns
        ui_patterns = [
            r'Copy\s+code',
            r'Copy\s+to\s+clipboard',
            r'Copied!',
            r'Click\s+to\s+copy',
        ]
        
        for pattern in ui_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _build_hierarchy(self, element: Tag) -> list[dict[str, Any]]:
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
        
        # Extract text while preserving meaningful whitespace
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
