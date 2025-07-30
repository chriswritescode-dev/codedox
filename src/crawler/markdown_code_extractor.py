"""Markdown-based code block extractor for uploaded documentation."""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from .language_mapping import normalize_language, get_language_from_filename
from .extraction_models import SimpleCodeBlock

logger = logging.getLogger(__name__)


@dataclass
class MarkdownSection:
    """Represents a section in markdown with its hierarchy."""
    level: int
    title: str
    content: List[str] = field(default_factory=list)
    line_number: int = 0


class MarkdownCodeExtractor:
    """Extracts code blocks from markdown with surrounding documentation context."""
    
    # Regex patterns for code block detection
    FENCED_CODE_PATTERN = re.compile(
        r'^```(\w+)?\s*\n(.*?)\n```',
        re.MULTILINE | re.DOTALL
    )
    
    INDENTED_CODE_PATTERN = re.compile(
        r'^((?:[ ]{4}|\t).*(?:\n(?:[ ]{4}|\t).*)*)',
        re.MULTILINE
    )
    
    HTML_CODE_PATTERN = re.compile(
        r'<pre[^>]*>(?:<code[^>]*>)?(.*?)(?:</code>)?</pre>',
        re.IGNORECASE | re.DOTALL
    )
    
    # Pattern for heading detection
    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    
    # Pattern for inline code (to exclude from context)
    INLINE_CODE_PATTERN = re.compile(r'`[^`]+`')
    
    def __init__(self):
        """Initialize the markdown code extractor."""
        self.stats = {
            'total_blocks': 0,
            'fenced_blocks': 0,
            'indented_blocks': 0,
            'html_blocks': 0,
            'languages_found': set()
        }
    
    def extract_code_blocks(self, content: str, source_url: str) -> List[SimpleCodeBlock]:
        """
        Extract all code blocks from markdown content.
        
        Args:
            content: Markdown content
            source_url: Source URL/path for reference
            
        Returns:
            List of SimpleCodeBlock objects with extracted code and context
        """
        blocks = []
        lines = content.split('\n')
        
        # First, build document structure (headings and sections)
        sections = self._build_section_hierarchy(content)
        
        # Extract fenced code blocks
        fenced_blocks = self._extract_fenced_blocks(content, lines, sections, source_url)
        blocks.extend(fenced_blocks)
        
        # Extract HTML code blocks
        html_blocks = self._extract_html_blocks(content, lines, sections, source_url)
        blocks.extend(html_blocks)
        
        # Extract indented code blocks (only if no fenced blocks found in section)
        if len(blocks) < 5:  # Only look for indented blocks if we found few fenced ones
            indented_blocks = self._extract_indented_blocks(content, lines, sections, blocks, source_url)
            blocks.extend(indented_blocks)
        
        # Update stats
        self.stats['total_blocks'] = len(blocks)
        logger.info(f"Extracted {len(blocks)} code blocks from {source_url}")
        logger.debug(f"Extraction stats: {self.stats}")
        
        return blocks
    
    def _build_section_hierarchy(self, content: str) -> List[MarkdownSection]:
        """Build a hierarchy of sections from markdown headings."""
        sections = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            match = self.HEADING_PATTERN.match(line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                sections.append(MarkdownSection(
                    level=level,
                    title=title,
                    line_number=i
                ))
        
        return sections
    
    def _get_section_for_line(self, line_num: int, sections: List[MarkdownSection]) -> Optional[MarkdownSection]:
        """Find the section that contains a given line number."""
        current_section = None
        for section in sections:
            if section.line_number <= line_num:
                current_section = section
            else:
                break
        return current_section
    
    def _extract_context(self, content: str, start_line: int, end_line: int, 
                        lines: List[str], sections: List[MarkdownSection]) -> Tuple[List[str], List[str], Optional[str]]:
        """
        Extract context before and after a code block.
        
        Returns:
            Tuple of (context_before, context_after, section_title)
        """
        context_before = []
        context_after = []
        
        # Get section title
        section = self._get_section_for_line(start_line, sections)
        section_title = section.title if section else None
        
        # Extract context before (up to 5 lines or until another code block/heading)
        for i in range(max(0, start_line - 5), start_line):
            line = lines[i].strip()
            if line and not self.HEADING_PATTERN.match(line):
                # Remove inline code for cleaner context
                line = self.INLINE_CODE_PATTERN.sub('', line).strip()
                if line:
                    context_before.append(line)
        
        # Extract context after (up to 3 lines or until another code block/heading)
        for i in range(end_line + 1, min(len(lines), end_line + 4)):
            line = lines[i].strip()
            if line and not self.HEADING_PATTERN.match(line) and not line.startswith('```'):
                # Remove inline code for cleaner context
                line = self.INLINE_CODE_PATTERN.sub('', line).strip()
                if line:
                    context_after.append(line)
                    
        return context_before, context_after, section_title
    
    def _extract_fenced_blocks(self, content: str, lines: List[str], 
                              sections: List[MarkdownSection], source_url: str) -> List[SimpleCodeBlock]:
        """Extract fenced code blocks (```language ... ```)."""
        blocks = []
        
        for match in self.FENCED_CODE_PATTERN.finditer(content):
            language = match.group(1) or 'text'
            code = match.group(2).strip()
            
            # Skip empty blocks
            if not code:
                continue
            
            # Find line numbers
            start_pos = match.start()
            start_line = content[:start_pos].count('\n')
            end_line = start_line + match.group(0).count('\n')
            
            # Extract context
            context_before, context_after, section_title = self._extract_context(
                content, start_line, end_line, lines, sections
            )
            
            # Normalize language
            normalized_lang = normalize_language(language)
            
            # Create code block
            block = SimpleCodeBlock(
                code=code,
                language=normalized_lang,
                source_url=source_url,
                context_before=context_before,
                context_after=context_after
            )
            
            blocks.append(block)
            self.stats['fenced_blocks'] += 1
            self.stats['languages_found'].add(normalized_lang)
        
        return blocks
    
    def _extract_html_blocks(self, content: str, lines: List[str], 
                            sections: List[MarkdownSection], source_url: str) -> List[SimpleCodeBlock]:
        """Extract HTML code blocks (<pre><code>...</code></pre>)."""
        blocks = []
        
        for match in self.HTML_CODE_PATTERN.finditer(content):
            code = match.group(1).strip()
            
            # Skip empty blocks
            if not code:
                continue
                
            # Clean up HTML entities
            code = code.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
            
            # Find line numbers
            start_pos = match.start()
            start_line = content[:start_pos].count('\n')
            end_line = start_line + match.group(0).count('\n')
            
            # Extract context
            context_before, context_after, section_title = self._extract_context(
                content, start_line, end_line, lines, sections
            )
            
            # Try to detect language from context or default to text
            language = self._detect_language_from_context(context_before + context_after)
            
            # Create code block
            block = SimpleCodeBlock(
                code=code,
                language=language,
                source_url=source_url,
                context_before=context_before,
                context_after=context_after
            )
            
            blocks.append(block)
            self.stats['html_blocks'] += 1
            self.stats['languages_found'].add(language)
        
        return blocks
    
    def _extract_indented_blocks(self, content: str, lines: List[str], 
                                sections: List[MarkdownSection], 
                                existing_blocks: List[SimpleCodeBlock], source_url: str) -> List[SimpleCodeBlock]:
        """Extract indented code blocks (4 spaces or tab)."""
        blocks = []
        i = 0
        
        while i < len(lines):
            # Check if line is indented
            if lines[i].startswith(('    ', '\t')):
                # Start of indented block
                start_line = i
                code_lines = []
                
                # Collect all consecutive indented lines
                while i < len(lines) and (lines[i].startswith(('    ', '\t')) or lines[i].strip() == ''):
                    if lines[i].strip():  # Non-empty line
                        # Remove indentation
                        if lines[i].startswith('    '):
                            code_lines.append(lines[i][4:])
                        else:  # Tab
                            code_lines.append(lines[i][1:])
                    else:
                        code_lines.append('')
                    i += 1
                
                # Create block if we have content
                code = '\n'.join(code_lines).strip()
                if code and len(code_lines) > 1:  # At least 2 lines of code
                    # Check if this overlaps with existing blocks
                    overlaps = False
                    for existing in existing_blocks:
                        existing_start = existing.metadata.get('line_start', 0)
                        existing_end = existing.metadata.get('line_end', 0)
                        if start_line + 1 >= existing_start and start_line + 1 <= existing_end:
                            overlaps = True
                            break
                    
                    if not overlaps:
                        # Extract context
                        context_before, context_after, section_title = self._extract_context(
                            content, start_line, i - 1, lines, sections
                        )
                        
                        # Try to detect language
                        language = self._detect_language_from_context(context_before + context_after)
                        
                        # Create code block
                        block = SimpleCodeBlock(
                            code=code,
                            language=language,
                            source_url=source_url,
                            context_before=context_before,
                            context_after=context_after
                        )
                        
                        blocks.append(block)
                        self.stats['indented_blocks'] += 1
                        self.stats['languages_found'].add(language)
            else:
                i += 1
        
        return blocks
    
    def _detect_language_from_context(self, context: List[str]) -> str:
        """Try to detect language from surrounding context."""
        context_text = ' '.join(context).lower()
        
        # Common language indicators
        language_hints = {
            'python': ['python', 'py', 'django', 'flask', 'pip'],
            'javascript': ['javascript', 'js', 'node', 'npm', 'react', 'vue'],
            'typescript': ['typescript', 'ts', 'angular'],
            'java': ['java', 'spring', 'maven', 'gradle'],
            'csharp': ['c#', 'csharp', '.net', 'dotnet'],
            'go': ['go', 'golang'],
            'rust': ['rust', 'cargo'],
            'ruby': ['ruby', 'rails', 'gem'],
            'php': ['php', 'laravel', 'composer'],
            'swift': ['swift', 'ios', 'xcode'],
            'kotlin': ['kotlin', 'android'],
            'cpp': ['c++', 'cpp'],
            'c': ['c language', ' c '],
            'sql': ['sql', 'query', 'database', 'select', 'table'],
            'bash': ['bash', 'shell', 'terminal', 'command line', 'cli'],
            'yaml': ['yaml', 'yml', 'configuration'],
            'json': ['json', 'api response', 'configuration'],
            'xml': ['xml', 'markup'],
            'html': ['html', 'markup', 'web page'],
            'css': ['css', 'style', 'stylesheet']
        }
        
        for lang, hints in language_hints.items():
            if any(hint in context_text for hint in hints):
                return lang
        
        # Check for file extensions mentioned
        import re
        file_pattern = re.compile(r'\b\w+\.(\w+)\b')
        for match in file_pattern.finditer(context_text):
            ext = match.group(1)
            detected_lang = get_language_from_filename(f"file.{ext}")
            if detected_lang != 'text':
                return detected_lang
        
        return 'text'  # Default fallback