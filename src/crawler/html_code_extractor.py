"""HTML-based code block extractor for documentation crawling."""

import logging
import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup, NavigableString, Tag
from dataclasses import dataclass, field
from .code_formatter import CodeFormatter
from .language_mapping import normalize_language, get_language_from_filename
import os

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
    
    def _process_code_block(self, block: Tag, selector_type: str, use_async_detection: bool = False) -> Optional[ExtractedCodeBlock]:
        """
        Process a single code block element.
        
        Args:
            block: The code block element
            selector_type: Type of selector that found this block
            use_async_detection: Whether to use async language detection
            
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
        
        # Detect language first
        language = self._detect_language(block)
        
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
            context_after=context['after'],
            container_type=container_type,
            title=context.get('title'),
            description=context.get('description')
        )
        
        # Update stats
        self.stats['total_blocks'] += 1
        self.stats['blocks_by_type'][selector_type] = self.stats['blocks_by_type'].get(selector_type, 0) + 1
        if language:
            self.stats['languages_found'].add(language)
        
        return extracted
    
    def extract_code_blocks(self, html: str, url: str) -> List[ExtractedCodeBlock]:
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
                extracted = self._process_code_block(block, selector_type, use_async_detection=False)
                if extracted:
                    extracted_blocks.append(extracted)
        
        logger.info(f"Extracted {len(extracted_blocks)} code blocks from {url}")
        logger.debug(f"Stats: {self.stats}")
        
        return extracted_blocks
    
    async def _process_code_block_async(self, block: Tag, selector_type: str) -> Optional[ExtractedCodeBlock]:
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
        
        # Detect language first - async version
        language = await self._detect_language_async(block)
        
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
            context_after=context['after'],
            container_type=container_type,
            title=context.get('title'),
            description=context.get('description')
        )
        
        # Update stats
        self.stats['total_blocks'] += 1
        self.stats['blocks_by_type'][selector_type] = self.stats['blocks_by_type'].get(selector_type, 0) + 1
        if language:
            self.stats['languages_found'].add(language)
        
        return extracted
    
    async def extract_code_blocks_async(self, html: str, url: str) -> List[ExtractedCodeBlock]:
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
        # Use .strings to get all text content without BeautifulSoup adding separators
        return ''.join(element.strings)
    
    def _detect_language(self, element: Tag) -> Optional[str]:
        """Detect programming language using HTML classes and content analysis."""
        code_text = self._extract_code_text(element)
        if not code_text or len(code_text.strip()) < 10:
            return None
        
        # First check if language is specified in HTML classes
        classes = element.get('class', [])
        if classes:
            for cls in classes:
                # Common patterns: language-python, lang-js, highlight-java, etc.
                if 'language-' in cls:
                    lang = cls.split('language-')[-1].split()[0]
                    return self._normalize_language_name(lang)
                elif 'lang-' in cls:
                    lang = cls.split('lang-')[-1].split()[0]
                    return self._normalize_language_name(lang)
        
        # Check parent elements for language hints
        parent = element.parent
        while parent and parent.name != 'body':
            parent_classes = parent.get('class', [])
            if parent_classes:
                for cls in parent_classes:
                    if 'language-' in cls or 'lang-' in cls:
                        lang = cls.split('-')[-1].split()[0]
                        return self._normalize_language_name(lang)
            parent = parent.parent
        
        # Use pattern-based detection
        return self._pattern_based_detection(code_text)
    
    async def _detect_language_async(self, element: Tag) -> Optional[str]:
        """Detect programming language using HTML classes and pattern matching (VS Code detection disabled)."""
        code_text = self._extract_code_text(element)
        if not code_text or len(code_text.strip()) < 10:
            return None
        
        # First check if language is specified in HTML classes
        classes = element.get('class', [])
        if classes:
            for cls in classes:
                # Common patterns: language-python, lang-js, highlight-java, etc.
                if 'language-' in cls:
                    lang = cls.split('language-')[-1].split()[0]
                    return self._normalize_language_name(lang)
                elif 'lang-' in cls:
                    lang = cls.split('lang-')[-1].split()[0]
                    return self._normalize_language_name(lang)
        
        # Check parent elements for language hints
        parent = element.parent
        while parent and parent.name != 'body':
            parent_classes = parent.get('class', [])
            if parent_classes:
                for cls in parent_classes:
                    if 'language-' in cls or 'lang-' in cls:
                        lang = cls.split('-')[-1].split()[0]
                        return self._normalize_language_name(lang)
            parent = parent.parent
        
        # Extract context to get filename
        context = self._extract_context(element)
        filename = context.get('filename')
        
        # Check filename hints before VS Code detection
        if filename:
            lang_from_filename = self._get_language_from_filename(filename)
            if lang_from_filename:
                logger.debug(f"Language from filename '{filename}': {lang_from_filename}")
                return lang_from_filename
        
        
        # Fall back to pattern-based detection
        logger.debug("Falling back to pattern-based detection")
        return self._pattern_based_detection(code_text)
    
    def _normalize_language_name(self, lang: str) -> str:
        """Normalize language name to a standard format."""
        return normalize_language(lang)
    
    def _get_language_from_filename(self, filename: str) -> Optional[str]:
        """Determine language from filename or extension."""
        return get_language_from_filename(filename)
    
    def _pattern_based_detection(self, code_text: str) -> str:
        """Pattern-based detection for programming languages with improved specificity."""
        code_lower = code_text.lower()
        lines = code_text.split('\n')
        first_line = lines[0].strip() if lines else ''
        
        # Shell/Bash patterns - check shebang first (most specific)
        if code_text.startswith('#!'):
            if any(shell in first_line for shell in ['/bash', '/sh', '/zsh', '/fish']):
                return 'bash'
            elif '/usr/bin/env' in first_line:
                if 'python' in first_line:
                    return 'python'
                elif 'node' in first_line:
                    return 'javascript'
                elif 'ruby' in first_line:
                    return 'ruby'
                elif 'perl' in first_line:
                    return 'perl'
        
        # JSON pattern - must have valid JSON structure
        if (code_text.strip().startswith('{') and code_text.strip().endswith('}') and 
            '":' in code_text and code_text.count('{') == code_text.count('}')):
            # Additional check: no JavaScript keywords
            if not any(kw in code_text for kw in ['function', 'const', 'let', 'var', '=>', 'class']):
                return 'json'
        
        # YAML pattern - check for key: value patterns without braces
        if (': ' in code_text and not '{' in code_text and not '}' in code_text and
            any(line.strip().endswith(':') for line in lines)):
            return 'yaml'
        
        # CSS patterns - must have CSS-specific properties
        css_properties = ['color:', 'display:', 'margin:', 'padding:', 'font-', 'background:', 
                         'width:', 'height:', 'position:', 'border:', 'text-align:']
        if ('{' in code_text and '}' in code_text and 
            any(prop in code_text for prop in css_properties)):
            # Check for CSS-specific patterns
            if ('@import' in code_text or '@media' in code_text or 
                any(selector in code_text for selector in ['.class', '#id', 'body {', 'div {'])):
                return 'css'
            # Additional check: no JavaScript function declarations
            if not any(pattern in code_text for pattern in ['function(', 'function ', '=> {']):
                return 'css'
        
        # TypeScript patterns - must have type annotations
        if any(pattern in code_text for pattern in [': string', ': number', ': boolean', 
                                                    'interface ', 'type ', ': any', ': void',
                                                    '<T>', 'extends ', 'implements ']):
            return 'typescript'
        
        # JavaScript patterns - check for JS-specific syntax
        js_patterns = ['function ', 'const ', 'let ', 'var ', '=>', 'async ', 'await ',
                      'export ', 'import ', 'require(', 'module.exports', 'console.log']
        if any(pattern in code_text for pattern in js_patterns):
            # Additional check for React/JSX
            if any(jsx in code_text for jsx in ['<div>', '<span>', 'React.', 'useState', 'useEffect']):
                return 'javascript'
            # Check for Node.js patterns
            if any(node in code_text for node in ['require(', 'module.exports', 'process.', 'fs.']):
                return 'javascript'
            return 'javascript'
        
        # Python patterns - check for Python-specific syntax
        python_patterns = ['def ', 'import ', 'from ', 'class ', 'if __name__', 
                          'print(', 'self.', '__init__', 'async def', 'await ',
                          'try:', 'except:', 'finally:', 'with ']
        if any(pattern in code_text for pattern in python_patterns):
            return 'python'
        
        # Ruby patterns
        if any(pattern in code_text for pattern in ['def ', 'end', 'puts ', 'require ', 
                                                    'class ', 'module ', 'attr_', '.each']):
            return 'ruby'
        
        # Go patterns
        if any(pattern in code_text for pattern in ['func ', 'package ', 'import (', 
                                                    'fmt.', 'var ', 'const ', ':=']):
            return 'go'
        
        # Rust patterns
        if any(pattern in code_text for pattern in ['fn ', 'let ', 'mut ', 'impl ', 
                                                    'struct ', 'enum ', 'trait ', 'use ']):
            return 'rust'
        
        # C/C++ patterns
        if any(pattern in code_text for pattern in ['#include', 'int main', 'void ', 
                                                    'printf(', 'std::', 'namespace ']):
            return 'cpp'
        
        # Java patterns
        if any(pattern in code_text for pattern in ['public class', 'private ', 'protected ',
                                                    'static void', 'System.out.', 'import java.']):
            return 'java'
        
        # SQL patterns
        sql_keywords = ['SELECT', 'FROM', 'WHERE', 'INSERT', 'UPDATE', 'DELETE', 
                       'CREATE TABLE', 'ALTER TABLE', 'DROP TABLE']
        if any(keyword in code_text.upper() for keyword in sql_keywords):
            return 'sql'
        
        # HTML patterns (both escaped and unescaped)
        if (any(tag in code_text for tag in ['<html', '<div', '<body', '<head', '</html>', '<p', '</p>']) or
            any(tag in code_text for tag in ['&lt;html', '&lt;div', '&lt;body', '&lt;/html&gt;', '&lt;p&gt;', '&lt;/p&gt;'])):
            return 'html'
        
        # Shell patterns - fallback for commands without shebang
        if (any(cmd in code_text for cmd in ['echo ', 'cd ', 'ls ', 'mkdir ', 'rm ', 'cp ']) and
            ('$' in code_text or '|' in code_text or '&&' in code_text)):
            return 'bash'
        
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
            
            # Look for filename in this container
            if not context['filename']:
                # Check for common filename indicators
                filename_elem = None
                
                # Check for elements with filename-related classes
                for elem in parent.find_all(['div', 'span', 'code']):
                    elem_classes = elem.get('class', [])
                    if any('filename' in cls.lower() or 'file-name' in cls.lower() 
                           or 'code-title' in cls.lower() for cls in elem_classes):
                        filename_elem = elem
                        break
                
                # Check for data attributes
                if not filename_elem and parent.get('data-filename'):
                    context['filename'] = parent.get('data-filename')
                elif not filename_elem and parent.get('title') and '.' in parent.get('title'):
                    # Sometimes filename is in title attribute
                    context['filename'] = parent.get('title')
                elif filename_elem:
                    filename_text = filename_elem.get_text(strip=True)
                    if filename_text and ('.' in filename_text or filename_text in ['Dockerfile', 'Makefile']):
                        context['filename'] = filename_text
            
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
        
        # Extract filename from context if not found
        if not context['filename'] and context['before']:
            # Look for filename patterns in context
            for text in context['before']:
                # Common patterns: "app/page.tsx", "src/index.js", "package.json"
                if ('/' in text or '.' in text) and len(text) < 100:
                    # Check if it looks like a filename
                    import re
                    filename_pattern = r'^[\w\-/]+\.\w+$|^Dockerfile$|^Makefile$|^\.[\w]+$'
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