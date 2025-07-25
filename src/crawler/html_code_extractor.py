"""HTML-based code block extractor for documentation crawling."""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup, NavigableString, Tag
from dataclasses import dataclass, field
from .code_formatter import CodeFormatter

logger = logging.getLogger(__name__)


@dataclass
class ExtractedCodeBlock:
    """Represents an extracted code block with its context."""
    code: str
    language: Optional[str] = None
    container_hierarchy: List[Dict[str, Any]] = field(default_factory=list)
    context_before: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)
    container_type: Optional[str] = None  # example, api-method, tutorial-step, etc.
    title: Optional[str] = None
    description: Optional[str] = None


class HTMLCodeExtractor:
    """Extracts code blocks from HTML with surrounding documentation context."""
    
    # Elements to extract text content from
    CONTEXT_ELEMENTS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'dt', 'dd', 'span', 'div'}
    
    # Elements to completely skip/remove
    SKIP_ELEMENTS = {'a', 'nav', 'aside', 'footer', 'header', 'button', 'input', 'select', 
                     'script', 'style', 'noscript', 'iframe', 'svg', 'img'}
    
    # Classes/IDs that indicate navigation or UI elements (to skip)
    SKIP_PATTERNS = {
        'navigation', 'nav', 'menu', 'sidebar', 'footer', 'header', 'breadcrumb',
        'social', 'share', 'ad', 'advertisement', 'banner', 'popup', 'modal',
        'toolbar', 'pagination', 'pager', 'widget'
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
    ]
    
    def __init__(self):
        """Initialize the code extractor."""
        self.stats = {
            'total_blocks': 0,
            'blocks_by_type': {},
            'languages_found': set()
        }
        self.formatter = CodeFormatter()
    
    def extract_code_blocks(self, html: str, url: str) -> List[ExtractedCodeBlock]:
        """
        Extract all code blocks from HTML with their documentation context.
        
        Args:
            html: Raw HTML content
            url: URL of the page (for logging)
            
        Returns:
            List of ExtractedCodeBlock objects
        """
        soup = BeautifulSoup(html, 'html.parser')
        extracted_blocks = []
        
        # Note: We don't remove any elements to avoid missing code blocks
        # self._remove_skip_elements(soup)
        
        # Find all code blocks
        for selector, selector_type in self.CODE_SELECTORS:
            blocks = soup.select(selector)
            
            for block in blocks:
                # Skip if already processed (nested selectors might match same element)
                if block.get('data-processed'):
                    continue
                    
                block['data-processed'] = 'true'
                
                # Extract the code content
                raw_code_text = self._extract_code_text(block)
                
                # Skip empty or very short code blocks (likely inline code)
                if not raw_code_text or len(raw_code_text.strip()) < 10:
                    continue
                
                # Detect language first (needed for formatting)
                language = self._detect_language(block)
                
                # Format the code using language-specific rules
                code_text = self.formatter.format_code(raw_code_text, language)
                
                # Skip inline code in sentences (unless it's multi-line after formatting)
                if self._is_inline_code(block) and '\n' not in code_text:
                    continue
                
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
                    context_after=context['after'],
                    container_type=container_type,
                    title=context.get('title'),
                    description=context.get('description')
                )
                
                extracted_blocks.append(extracted)
                
                # Update stats
                self.stats['total_blocks'] += 1
                self.stats['blocks_by_type'][selector_type] = self.stats['blocks_by_type'].get(selector_type, 0) + 1
                if language:
                    self.stats['languages_found'].add(language)
        
        logger.info(f"Extracted {len(extracted_blocks)} code blocks from {url}")
        logger.debug(f"Stats: {self.stats}")
        
        return extracted_blocks
    
    def _remove_skip_elements(self, soup: BeautifulSoup) -> None:
        """Remove all elements we want to skip."""
        # Remove by tag name
        for tag in self.SKIP_ELEMENTS:
            for element in soup.find_all(tag):
                element.decompose()
        
        # Remove by class/id patterns
        from bs4.element import Tag
        # Collect elements to remove first to avoid modifying during iteration
        elements_to_remove = []
        
        for element in soup.find_all(True):  # All elements
            if not isinstance(element, Tag):  # Skip non-tag elements
                continue
            
            classes = element.get('class', [])
            element_id = element.get('id', '')
            
            # Check if any class or id matches skip patterns
            should_skip = False
            for pattern in self.SKIP_PATTERNS:
                if any(pattern in cls.lower() for cls in classes):
                    should_skip = True
                    break
                if pattern in element_id.lower():
                    should_skip = True
                    break
            
            if should_skip:
                elements_to_remove.append(element)
        
        # Now remove the collected elements
        for element in elements_to_remove:
            element.decompose()
    
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
                classes = ui_elem.get('class', [])
                if any(ui_class in ' '.join(classes).lower() for ui_class in ui_classes):
                    ui_elem.decompose()
        
        # Remove any remaining links within code
        for link in element_copy.find_all('a'):
            link.unwrap()
        
        # Get text, preserving whitespace
        code_text = element_copy.get_text()
        
        # Clean up common artifacts
        # Remove line numbers if they appear at start of lines
        lines = code_text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remove line numbers like "1: " or "10: " at start
            cleaned_line = re.sub(r'^\s*\d+:\s*', '', line)
            cleaned_lines.append(cleaned_line)
        
        return '\n'.join(cleaned_lines).strip()
    
    def _detect_language(self, element: Tag) -> Optional[str]:
        """Detect programming language using content analysis."""
        code_text = self._extract_code_text(element)
        if not code_text or len(code_text.strip()) < 10:
            return None
        
        # Use simple but reliable pattern matching
        code_lower = code_text.lower()
        
        # Shell/Bash patterns (check first to avoid conflicts with 'export')
        if any(pattern in code_text for pattern in ['#!/bin/bash', '#!/bin/sh']) or (code_text.startswith('#!') and 'bash' in code_lower):
            return 'bash'
        elif 'echo ' in code_text and ('$' in code_text or code_text.strip().startswith('export ')):
            return 'bash'
        
        # JSON pattern (check early as it's very specific)
        elif code_text.strip().startswith('{') and code_text.strip().endswith('}') and '"' in code_text:
            return 'json'
        
        # TypeScript/JavaScript patterns
        elif any(pattern in code_text for pattern in [': string', ': number', ': boolean', 'interface ', 'type ']):
            return 'typescript'
        elif any(pattern in code_text for pattern in ['function ', 'const ', 'let ', 'var ', '=>', 'export ', 'import ']):
            return 'javascript'
        
        # Python patterns
        elif any(pattern in code_text for pattern in ['def ', 'import ', 'from ', 'class ', 'if __name__']):
            return 'python'
        
        # HTML patterns
        elif any(pattern in code_lower for pattern in ['<html', '<div', '<span', '<p>', '</div>', '</html>']):
            return 'html'
        
        # CSS patterns
        elif any(pattern in code_text for pattern in ['{', '}', ': ', ';']) and any(prop in code_lower for prop in ['color:', 'margin:', 'padding:', 'display:']):
            return 'css'
        
        # Default to text if no patterns match
        return 'text'
    
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
                parent_classes = parent.get('class', [])
                if any('code' in cls or 'example' in cls for cls in parent_classes):
                    return False
            return True
        
        return False
    
    def _extract_context(self, code_element: Tag) -> Dict[str, Any]:
        """Extract surrounding context for a code block."""
        context = {
            'before': [],
            'after': [],
            'hierarchy': [],
            'title': None,
            'description': None
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
                'classes': parent.get('class', []),
                'id': parent.get('id')
            }
            context['hierarchy'].append(hierarchy_info)
            
            # Look for title in this container
            if not context['title']:
                title_elem = parent.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                if title_elem:
                    title_text = title_elem.get_text(separator=' ', strip=True)
                    if title_text:
                        context['title'] = title_text
            
            # Get context from siblings at this level
            # Previous siblings (context before)
            for sibling in list(current.previous_siblings)[:3]:  # Limit to 3 siblings
                if isinstance(sibling, NavigableString):
                    continue
                if sibling.name in self.CONTEXT_ELEMENTS:
                    # Check if sibling contains code blocks
                    if sibling.find_all(['pre', 'code']):
                        # Skip elements that contain code blocks
                        continue
                    text = sibling.get_text(separator=' ', strip=True)
                    if text and len(text) > 10:
                        context['before'].insert(0, text)  # Insert at beginning to maintain order
            
            # Next siblings (context after)
            for sibling in list(current.next_siblings)[:2]:  # Limit to 2 siblings after
                if isinstance(sibling, NavigableString):
                    continue
                if sibling.name in self.CONTEXT_ELEMENTS:
                    # Check if sibling contains code blocks
                    if sibling.find_all(['pre', 'code']):
                        # Skip elements that contain code blocks
                        continue
                    text = sibling.get_text(separator=' ', strip=True)
                    if text and len(text) > 10:
                        context['after'].append(text)
            
            current = parent
            levels_up += 1
        
        # Set description from first paragraph in context
        if context['before'] and not context['description']:
            # Look for a paragraph that's not a title
            for text in context['before']:
                if not any(text.startswith(h) for h in ['#', 'Step', 'Example']):
                    context['description'] = text
                    break
        
        return context
    
    def _classify_container(self, hierarchy: List[Dict[str, Any]]) -> Optional[str]:
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
    
    def format_output(self, blocks: List[ExtractedCodeBlock]) -> str:
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
            
            if block.context_after:
                output.append("\nContext After:")
                for ctx in block.context_after[:2]:  # First 2 items
                    output.append(f"  - {ctx[:100]}...")
        
        output.append(f"\n\nTotal blocks found: {len(blocks)}")
        if self.stats['languages_found']:
            output.append(f"Languages: {', '.join(sorted(self.stats['languages_found']))}")
        
        return '\n'.join(output)