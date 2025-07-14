"""Extract code blocks from markdown and HTML content while preserving context."""

import re
import hashlib
import logging
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass, field
from html.parser import HTMLParser

try:
    from ..language.detector import LanguageDetector, TREE_SITTER_AVAILABLE
except ImportError:
    # Fallback if language detector is not available
    TREE_SITTER_AVAILABLE = False
    
    class LanguageDetector:  # type: ignore
        """Placeholder for when language detector is not available."""
        pass

logger = logging.getLogger(__name__)


@dataclass
class CodeBlock:
    """Represents an extracted code block with full context."""
    
    language: str
    content: str
    title: Optional[str] = None
    description: Optional[str] = None
    context_before: str = ""
    context_after: str = ""
    line_start: int = 0
    line_end: int = 0
    source_url: str = ""
    extraction_metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def hash(self) -> str:
        """Generate MD5 hash of code content."""
        return hashlib.md5(self.content.encode('utf-8')).hexdigest()
    
    @property
    def lines_of_code(self) -> int:
        """Count non-empty lines of code."""
        return len([line for line in self.content.split('\n') if line.strip()])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'language': self.language,
            'content': self.content,
            'title': self.title,
            'description': self.description,
            'context_before': self.context_before,
            'context_after': self.context_after,
            'line_start': self.line_start,
            'line_end': self.line_end,
            'source_url': self.source_url,
            'hash': self.hash,
            'metadata': self.extraction_metadata
        }


class HTMLCodeParser(HTMLParser):
    """Parse HTML to extract code blocks from various HTML structures."""
    
    def __init__(self) -> None:
        super().__init__()
        self.code_blocks: List[Dict[str, Any]] = []
        self.current_block: Optional[Dict[str, Any]] = None
        self.in_pre = False
        self.in_code = False
        self.tag_stack: List[str] = []
        self.in_pre_code = False  # Track if we're in code inside pre
        self.in_custom_component = False  # Track custom code components
        self.custom_component_type: Optional[str] = None
    
    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        """Handle opening tags."""
        self.tag_stack.append(tag)
        attrs_dict = dict(attrs)
        
        # Check for custom code components
        if tag.lower() in ['codeblock', 'highlight', 'code-block']:
            self.in_custom_component = True
            self.custom_component_type = tag.lower()
            self.current_block = {
                'content': '',
                'language': attrs_dict.get('language', attrs_dict.get('lang', ''))
            }
        elif tag == 'pre':
            self.in_pre = True
            # Check if pre has language class directly
            language = self._extract_language(attrs_dict)
            self.current_block = {
                'content': '',
                'language': language
            }
            # Check if this is a pre without nested code (some docs do this)
            if language:
                # Assume content will be directly in pre
                self.in_pre_code = True
        elif tag == 'code':
            if self.in_pre:
                # Code inside pre - this is where the actual code content is
                self.in_pre_code = True
                # Update language if specified on code tag
                lang = self._extract_language(attrs_dict)
                if lang and self.current_block:
                    self.current_block['language'] = lang
            else:
                # Standalone code tag - could be inline or multi-line
                # We'll extract it and let _is_valid_code filter based on line count
                self.in_code = True
                self.current_block = {
                    'content': '',
                    'language': self._extract_language(attrs_dict)
                }
        elif tag == 'div':
            # Check for GitHub/Rouge/Prism style code blocks
            class_attr = attrs_dict.get('class', '')
            if class_attr and any(marker in class_attr for marker in ['highlight', 'highlighter-rouge', 'code-block']):
                # This might contain a code block
                self.current_block = {
                    'content': '',
                    'language': self._extract_language(attrs_dict)
                }
    
    def handle_endtag(self, tag: str) -> None:
        """Handle closing tags."""
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()
        
        if tag.lower() in ['codeblock', 'highlight', 'code-block'] and self.in_custom_component:
            self.in_custom_component = False
            self.custom_component_type = None
            if self.current_block and self.current_block['content']:  # Don't strip!
                self.code_blocks.append(self.current_block)
            self.current_block = None
        elif tag == 'code' and self.in_pre_code:
            self.in_pre_code = False
        elif tag == 'pre' and self.in_pre:
            self.in_pre = False
            self.in_pre_code = False
            if self.current_block and self.current_block['content']:  # Don't strip!
                self.code_blocks.append(self.current_block)
            self.current_block = None
        elif tag == 'code' and self.in_code and not self.in_pre:
            self.in_code = False
            if self.current_block and self.current_block['content']:  # Don't strip!
                self.code_blocks.append(self.current_block)
            self.current_block = None
    
    def handle_data(self, data: str) -> None:
        """Handle text data - preserve exactly as is."""
        if self.current_block is not None and (self.in_pre_code or (self.in_code and not self.in_pre) or self.in_custom_component):
            # IMPORTANT: Do not modify the data!
            self.current_block['content'] += data
    
    def handle_entityref(self, name: str) -> None:
        """Handle HTML entities like &lt; &gt; &amp;"""
        if self.current_block is not None and (self.in_pre_code or (self.in_code and not self.in_pre) or self.in_custom_component):
            # Convert common entities
            entities = {
                'lt': '<',
                'gt': '>',
                'amp': '&',
                'quot': '"',
                'apos': "'"
            }
            self.current_block['content'] += entities.get(name, f'&{name};')
    
    def handle_charref(self, name: str) -> None:
        """Handle numeric character references."""
        if self.current_block is not None and (self.in_pre_code or (self.in_code and not self.in_pre) or self.in_custom_component):
            try:
                if name.startswith('x'):
                    # Hex reference
                    char = chr(int(name[1:], 16))
                else:
                    # Decimal reference
                    char = chr(int(name))
                self.current_block['content'] += char
            except ValueError:
                self.current_block['content'] += f'&#{name};'
    
    def _extract_language(self, attrs_dict: Dict[str, Optional[str]]) -> str:
        """Extract language from class attribute."""
        class_attr = attrs_dict.get('class', '')
        # Handle various formats: language-js, lang-javascript, highlight-js, etc.
        for prefix in ['language-', 'lang-', 'highlight-']:
            if class_attr and prefix in class_attr:
                # Extract the language part
                parts = class_attr.split() if class_attr else []
                for part in parts:
                    if part.startswith(prefix):
                        return part[len(prefix):]
        return ''


class CodeExtractor:
    """Extract code blocks from various content formats."""

    # Regex patterns for markdown code blocks
    # Enhanced pattern to support various fence formats and metadata
    FENCED_CODE_PATTERN = re.compile(
        r'^(?P<fence>```|~~~)(?P<lang>[a-zA-Z0-9_+-]*)(?P<meta>[^\n]*?)\n(?P<code>(?:(?!^```)(?!^~~~)[\s\S])*?)\n^(?P=fence)(?:\s*(?:Copy|copy))?$',
        re.MULTILINE
    )

    # Alternative patterns for specific documentation frameworks
    DOCUSAURUS_CODE_PATTERN = re.compile(
        r'^:::code(?:-group)?\s+(?P<lang>[a-zA-Z0-9_+-]+)(?P<meta>[^\n]*)\n(?P<code>.*?)\n:::$',
        re.DOTALL | re.MULTILINE
    )

    # Pattern for code blocks with tab labels (e.g., ```python [Python])
    TABBED_CODE_PATTERN = re.compile(
        r'```(?P<lang>[a-zA-Z0-9_+-]*)\s*\[(?P<label>[^\]]+)\]\s*(?P<meta>[^\n]*)\n(?P<code>.*?)\n```',
        re.DOTALL | re.MULTILINE
    )

    INDENTED_CODE_PATTERN = re.compile(
        r'^(?: {4}|\t)(.+)$',
        re.MULTILINE
    )

    # Pattern for structured format (TITLE, DESCRIPTION, etc.)
    STRUCTURED_PATTERN = re.compile(
        r'TITLE:\s*(.+?)\n'
        r'DESCRIPTION:\s*(.+?)\n'
        r'SOURCE:\s*(.+?)\n'
        r'(?:LANGUAGE:\s*(.+?)\n)?'
        r'CODE:\s*\n```(\w*)\n(.*?)\n```',
        re.DOTALL | re.MULTILINE
    )

    def __init__(self, context_chars: int = 2000, min_code_lines: int = 2, 
                 use_tree_sitter: bool = True, min_quality_score: float = 0.7):
        """Initialize the code extractor.
        
        Args:
            context_chars: Number of characters to extract before/after code
            min_code_lines: Minimum lines of code to consider valid (default: 2)
            use_tree_sitter: Whether to use tree-sitter for validation
            min_quality_score: Minimum AST quality score (0-1) to accept code block
        """
        self.context_chars = context_chars
        self.min_code_lines = min_code_lines
        self.use_tree_sitter = use_tree_sitter and TREE_SITTER_AVAILABLE
        self.min_quality_score = min_quality_score
        self.logger = logging.getLogger(__name__)

        # Initialize language detector if available
        self.language_detector = None
        if self.use_tree_sitter:
            try:
                self.language_detector = LanguageDetector()
                self.logger.info("Tree-sitter validation enabled for code extraction")
            except Exception as e:
                self.logger.warning(f"Failed to initialize language detector: {e}")
                self.use_tree_sitter = False

    def extract_from_content(self, content: str, source_url: str = "", 
                           content_type: str = "markdown", full_page_content: Optional[str] = None) -> List[CodeBlock]:
        """Extract all code blocks from content.
        
        Args:
            content: The content to extract from
            source_url: URL of the source document
            content_type: Type of content ('markdown', 'html', 'mixed')
            full_page_content: Optional full page content for enhanced context
            
        Returns:
            List of extracted CodeBlock objects
        """
        if not content:
            return []

        code_blocks = []

        # Try structured format first
        structured_blocks = self._extract_structured_blocks(content, source_url)
        if structured_blocks:
            code_blocks.extend(structured_blocks)

        # Extract based on content type
        if content_type == "html":
            code_blocks.extend(self._extract_html_blocks(content, source_url, full_page_content))
        else:
            # Extract markdown blocks
            code_blocks.extend(self._extract_markdown_blocks(content, source_url, full_page_content))

        # Remove duplicates based on content hash
        unique_blocks = {}
        for block in code_blocks:
            if block.hash not in unique_blocks:
                unique_blocks[block.hash] = block

        return list(unique_blocks.values())

    def _extract_structured_blocks(self, content: str, source_url: str) -> List[CodeBlock]:
        """Extract blocks in structured format (TITLE, DESCRIPTION, etc.)."""
        blocks = []

        for match in self.STRUCTURED_PATTERN.finditer(content):
            title = match.group(1).strip()
            description = match.group(2).strip()
            source = match.group(3).strip()
            language = match.group(4) or match.group(5) or 'unknown'
            code_content = match.group(6)  # DO NOT STRIP!

            if language:
                language = language.strip().lower()

            if self._is_valid_code(code_content, language):
                block = CodeBlock(
                    language=language,
                    content=code_content,
                    title=title,
                    description=description,
                    source_url=source or source_url,
                    extraction_metadata={'format': 'structured'}
                )
                blocks.append(block)

        return blocks

    def _extract_markdown_blocks(self, content: str, source_url: str, full_page_content: Optional[str] = None) -> List[CodeBlock]:
        """Extract code blocks from markdown content."""
        blocks = []

        # Log content sample for debugging
        self.logger.debug(f"Extracting from markdown content, length: {len(content)}")

        # Try all patterns
        all_patterns = [
            (self.FENCED_CODE_PATTERN, 'markdown_fenced'),
            (self.DOCUSAURUS_CODE_PATTERN, 'docusaurus'),
            (self.TABBED_CODE_PATTERN, 'markdown_tabbed'),
        ]

        for pattern, format_type in all_patterns:
            matches = list(pattern.finditer(content))
            self.logger.debug(f"Found {len(matches)} potential code blocks with {format_type} pattern")

            for match in matches:
                # Extract components based on pattern
                if format_type == 'markdown_fenced':
                    language = match.group('lang') or 'unknown'
                    code_content = match.group('code')
                    metadata = match.group('meta').strip() if match.group('meta') else ''
                elif format_type == 'docusaurus':
                    language = match.group('lang') or 'unknown' 
                    code_content = match.group('code')
                    metadata = match.group('meta').strip() if match.group('meta') else ''
                elif format_type == 'markdown_tabbed':
                    language = match.group('lang') or 'unknown'
                    code_content = match.group('code')
                    metadata = f"[{match.group('label')}] {match.group('meta')}".strip()

                # Parse metadata for title and other attributes
                title = self._extract_title_from_metadata(metadata)

                # IMPORTANT: Do not modify code content at all!
                # Preserve exactly as extracted

                # If language is unknown, try to detect from content
                if language == 'unknown' and self.language_detector:
                    try:
                        detection = self.language_detector.detect(code_content)
                        if detection.confidence > 0.8:
                            language = detection.language
                            self.logger.debug(f"Auto-detected language: {language} (confidence: {detection.confidence:.2f})")
                    except Exception as e:
                        self.logger.debug(f"Language detection failed: {e}")

                if self._is_valid_code(code_content, language):
                    # Debug log extracted code with detailed formatting info
                    self.logger.debug(f"Extracted {format_type} code block - Language: {language}, Length: {len(code_content)}")

                    # Find position in original content
                    start_pos = match.start()
                    end_pos = match.end()

                    # Extract context (but don't strip it from code)
                    context_before, context_after = self._extract_context(
                        content, start_pos, end_pos
                    )

                    # Calculate line numbers
                    line_start = content[:start_pos].count('\n') + 1
                    line_end = content[:end_pos].count('\n') + 1

                    # Extract section information
                    section_title, section_content = self._extract_section_context(
                        content, start_pos, end_pos
                    )

                    # Try to extract description from context if no title
                    if not title:
                        title, description = self._extract_metadata_from_context(
                            context_before, context_after
                        )
                    else:
                        _, description = self._extract_metadata_from_context(
                            context_before, context_after
                        )

                    # Build extraction metadata with section information
                    extraction_metadata = {
                        'format': format_type,
                        'metadata': metadata
                    }
                    
                    # Add section information if found
                    if section_title:
                        extraction_metadata['section_title'] = section_title
                    if section_content:
                        extraction_metadata['full_section_content'] = section_content
                    
                    # Add full page content if provided
                    if full_page_content:
                        extraction_metadata['full_page_content'] = full_page_content

                    block = CodeBlock(
                        language=language.lower(),
                        content=code_content,  # Preserved exactly as extracted
                        title=title,
                        description=description,
                        context_before=context_before,
                        context_after=context_after,
                        line_start=line_start,
                        line_end=line_end,
                        source_url=source_url,
                        extraction_metadata=extraction_metadata
                    )
                    blocks.append(block)

        return blocks

    def _extract_title_from_metadata(self, metadata: str) -> Optional[str]:
        """Extract title from code block metadata.
        
        Examples:
        - title="filename.py"
        - {highlight: [1,2], title: "Example"}
        """
        if not metadata:
            return None

        # Pattern for title="value" or title='value'
        title_match = re.search(r'title=[\'"](.*?)[\'"]', metadata)
        if title_match:
            return title_match.group(1)

        # Pattern for title: "value" (JSON-like)
        title_match = re.search(r'title:\s*[\'"](.*?)[\'"]', metadata)
        if title_match:
            return title_match.group(1)

        return None

    def _extract_html_blocks(self, content: str, source_url: str, full_page_content: Optional[str] = None) -> List[CodeBlock]:
        """Extract code blocks from HTML content."""
        parser = HTMLCodeParser()
        parser.feed(content)

        blocks = []
        for parsed_block in parser.code_blocks:
            language = parsed_block['language'] or 'unknown'
            if self._is_valid_code(parsed_block['content'], language):
                # Build extraction metadata
                extraction_metadata = {'format': 'html'}
                if full_page_content:
                    extraction_metadata['full_page_content'] = full_page_content
                    
                block = CodeBlock(
                    language=language,
                    content=parsed_block['content'],
                    source_url=source_url,
                    extraction_metadata=extraction_metadata
                )
                blocks.append(block)

        return blocks

    def _extract_context(self, content: str, start_pos: int, end_pos: int) -> Tuple[str, str]:
        """Extract context before and after a code block."""
        # Context before
        context_start = max(0, start_pos - self.context_chars)
        context_before = content[context_start:start_pos].strip()  # OK to strip context

        # Context after
        context_end = min(len(content), end_pos + self.context_chars)
        context_after = content[end_pos:context_end].strip()  # OK to strip context

        return context_before, context_after

    def _extract_metadata_from_context(self, context_before: str, 
                                     context_after: str) -> Tuple[Optional[str], Optional[str]]:
        """Try to extract title and description from surrounding context."""
        title = None
        description = None

        # Look for headers in context before
        header_patterns = [
            r'#+\s+(.+)$',  # Markdown headers
            r'<h[1-6]>(.+?)</h[1-6]>',  # HTML headers
            r'^(.+)\n[=-]+$',  # Underlined headers
        ]

        for pattern in header_patterns:
            match = re.search(pattern, context_before, re.MULTILINE | re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                break

        # Look for descriptive text
        # Take the last paragraph before code or first paragraph after
        paragraphs_before = [p.strip() for p in context_before.split('\n\n') if p.strip()]
        paragraphs_after = [p.strip() for p in context_after.split('\n\n') if p.strip()]

        if paragraphs_before:
            # Last non-header paragraph before code
            for para in reversed(paragraphs_before):
                if not re.match(r'^#+\s+', para) and len(para) > 20:
                    description = para
                    break

        if not description and paragraphs_after:
            # First paragraph after code that looks descriptive
            if paragraphs_after[0] and len(paragraphs_after[0]) > 20:
                description = paragraphs_after[0]

        return title, description

    def _is_valid_code(self, code: str, language: str = 'unknown') -> bool:
        """Check if extracted text is valid code - less aggressive filtering."""
        if not code:
            return False

        # Count actual lines (don't strip to preserve whitespace)
        lines = code.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]

        if len(non_empty_lines) < self.min_code_lines:
            return False

        # Use tree-sitter validation if available, but be more lenient
        if self.use_tree_sitter and self.language_detector and language != 'unknown':
            quality_score = self._calculate_code_quality(code, language)
            # Lower threshold for acceptance
            if quality_score < 0.3:  # Very low threshold
                self.logger.debug(f"Code block rejected - very low quality score {quality_score:.2f}")
                return False

        return True

    def _calculate_code_quality(self, code: str, hint_language: str = 'unknown') -> float:
        """Calculate quality score for code using tree-sitter AST analysis.
        
        Returns:
            Score between 0 and 1, where 1 is perfect code
        """
        if not self.language_detector:
            return 1.0  # Default to accepting if no detector

        try:
            # First detect the language if unknown
            if hint_language == 'unknown' or not hint_language:
                detection_result = self.language_detector.detect(code)
                language = detection_result.language
                confidence = detection_result.confidence
            else:
                # Verify the hint language is correct
                detection_result = self.language_detector.detect(code)
                if detection_result.language == hint_language:
                    language = hint_language
                    confidence = detection_result.confidence
                else:
                    # Trust detection over hint if they differ significantly
                    if detection_result.confidence > 0.8:
                        language = detection_result.language
                        confidence = detection_result.confidence
                    else:
                        language = hint_language
                        confidence = 0.5

            # If language is still unknown, use basic check
            if language == 'unknown':
                return self._basic_code_quality_check(code)

            # Get the parser for this language
            parser = self.language_detector.parsers.get(language)
            if not parser:
                # No parser available, use basic check
                return self._basic_code_quality_check(code)

            # Parse the code
            tree = parser.parse(code.encode('utf-8'))
            root = tree.root_node

            # Calculate quality metrics
            total_nodes = self._count_nodes(root)
            error_nodes = self._count_error_nodes(root)

            if total_nodes == 0:
                return 0.0

            # Base score from parse errors
            error_ratio = error_nodes / total_nodes
            base_score = 1.0 - error_ratio

            # Check if it's just comments
            if self._is_only_comments(code, language):
                return 0.2  # Very low score for comment-only code

            # Check for prose disguised as code
            if self._looks_like_prose(code) and error_nodes == 0:
                # If it parses without errors but looks like prose, it's probably prose
                return self._basic_code_quality_check(code)

            # Bonus for complete structures
            has_complete_structures = self._has_complete_structures(root, language)
            if has_complete_structures:
                base_score = min(1.0, base_score + 0.2)
            else:
                # Penalty for incomplete structures
                base_score *= 0.85

            # Penalty for too many errors
            if error_nodes > 5:
                base_score *= 0.8

            # Penalty if no meaningful code nodes
            if not self._has_code_nodes(root, language):
                base_score *= 0.5

            # Combine with language detection confidence
            final_score = base_score * 0.7 + confidence * 0.3

            return final_score

        except Exception as e:
            self.logger.debug(f"Error calculating code quality: {e}")
            return self._basic_code_quality_check(code)

    def _basic_code_quality_check(self, code: str) -> float:
        """Basic quality check without tree-sitter."""
        lines = [line for line in code.split('\n') if line.strip()]

        # Very short code is suspicious
        if len(lines) < 2:
            return 0.3

        score = 0.5  # Start at neutral

        # Check for common code patterns
        code_patterns = [
            (r'\b(def|function|class|struct|interface)\s+\w+', 0.2),
            (r'\b(if|for|while|switch)\s*[\(\{]', 0.1),
            (r'[{};]', 0.1),
            (r'^\s*(import|from|require|include|using)\s+', 0.2),
            (r'=\s*[^=]', 0.1),  # Assignment
        ]

        for pattern, boost in code_patterns:
            if re.search(pattern, code, re.MULTILINE):
                score += boost

        # Penalty for prose-like content
        prose_patterns = [
            (r'^[A-Z][a-z]+\s+[a-z]+\s+[a-z]+.*\.$', -0.2),  # Sentences
            (r'\b(the|this|that|these|those)\b', -0.15),
            (r'^(Here|This|The|It)\s', -0.1),  # Common prose starters
            (r'\b(returns|takes|uses|makes|does)\b', -0.1),  # Common prose verbs
            (r'\b(of|to|in|for|with)\b\s+\w+$', -0.1),  # Prepositional phrases
        ]

        for pattern, penalty in prose_patterns:
            if re.search(pattern, code, re.MULTILINE | re.IGNORECASE):
                score += penalty

        # Bonus for brackets/parentheses balance
        if code.count('(') == code.count(')') and code.count('{') == code.count('}'):
            score += 0.1

        return max(0.0, min(1.0, score))

    def _extract_section_context(self, content: str, start_pos: int, end_pos: int) -> Tuple[Optional[str], Optional[str]]:
        """Extract section title and full section content containing the code block.
        
        Args:
            content: Full markdown content
            start_pos: Start position of code block
            end_pos: End position of code block
            
        Returns:
            Tuple of (section_title, section_content)
        """
        try:
            # Find the markdown header that contains this code block
            section_header = self._find_containing_section(content, start_pos)
            
            if not section_header:
                return None, None
                
            header_start, header_end, header_level, header_title = section_header
            
            # Find the end of this section (next header of same or higher level)
            section_end = self._find_section_end(content, header_end, header_level)
            
            # Extract the full section content
            section_content = content[header_start:section_end].strip()
            
            return header_title, section_content
            
        except Exception as e:
            self.logger.debug(f"Error extracting section context: {e}")
            return None, None
    
    def _find_containing_section(self, content: str, code_pos: int) -> Optional[Tuple[int, int, int, str]]:
        """Find the markdown header that contains the given position.
        
        Args:
            content: Full markdown content
            code_pos: Position within content to find section for
            
        Returns:
            Tuple of (header_start, header_end, header_level, header_title) or None
        """
        # Pattern for markdown headers (H1-H6)
        header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        
        best_header = None
        
        for match in header_pattern.finditer(content):
            header_start = match.start()
            header_end = match.end()
            
            # Skip headers that come after our code block
            if header_start > code_pos:
                break
                
            # This header comes before our code block, so it's a candidate
            header_level = len(match.group(1))  # Number of # symbols
            header_title = match.group(2).strip()
            
            best_header = (header_start, header_end, header_level, header_title)
        
        return best_header
    
    def _find_section_end(self, content: str, section_start: int, section_level: int) -> int:
        """Find the end of a section by looking for the next header of same or higher level.
        
        Args:
            content: Full markdown content
            section_start: Start position of the current section
            section_level: Level of current section (1-6)
            
        Returns:
            End position of the section
        """
        # Pattern for markdown headers (H1-H6)
        header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        
        for match in header_pattern.finditer(content, section_start):
            # Skip the current section header itself
            if match.start() == section_start:
                continue
                
            header_level = len(match.group(1))
            
            # If we find a header of same or higher level (lower number), end here
            if header_level <= section_level:
                return match.start()
        
        # No more headers found, section goes to end of content
        return len(content)

    def _count_nodes(self, node: Any) -> int:
        """Count total nodes in AST."""
        count = 1
        for child in node.children:
            count += self._count_nodes(child)
        return count

    def _count_error_nodes(self, node: Any) -> int:
        """Count error nodes in AST."""
        count = 1 if node.type == 'ERROR' or node.is_error else 0
        for child in node.children:
            count += self._count_error_nodes(child)
        return count

    def _has_complete_structures(self, root: Any, language: str) -> bool:
        """Check if code has complete structures like functions or classes."""
        complete_types = {
            'python': ['function_definition', 'class_definition'],  # Removed 'module'
            'javascript': ['function_declaration', 'class_declaration', 'arrow_function'],
            'typescript': ['function_declaration', 'class_declaration', 'interface_declaration'],
            'java': ['method_declaration', 'class_declaration'],
            'go': ['function_declaration', 'type_declaration'],
            'rust': ['function_item', 'struct_item', 'impl_item'],
            'cpp': ['function_definition', 'class_specifier'],
            'c': ['function_definition', 'struct_specifier'],
        }

        target_types = complete_types.get(language, [])
        if not target_types:
            return False

        return self._has_node_types(root, target_types)

    def _has_node_types(self, node: Any, types: List[str]) -> bool:
        """Check if AST contains any of the specified node types."""
        if node.type in types:
            return True
        for child in node.children:
            if self._has_node_types(child, types):
                return True
        return False

    def _is_only_comments(self, code: str, language: str) -> bool:
        """Check if code contains only comments."""
        lines = code.split('\n')  # Don't strip the whole code
        non_empty_lines = [line.strip() for line in lines if line.strip()]

        if not non_empty_lines:
            return True

        comment_patterns = {
            'python': r'^\s*#',
            'javascript': r'^\s*(//|/\*|\*)',
            'typescript': r'^\s*(//|/\*|\*)',
            'java': r'^\s*(//|/\*|\*)',
            'go': r'^\s*//',
            'rust': r'^\s*//',
            'cpp': r'^\s*//',
            'c': r'^\s*//',
            'ruby': r'^\s*#',
            'php': r'^\s*(//|#|/\*|\*)',
        }

        pattern = comment_patterns.get(language, r'^\s*(#|//)')
        for line in non_empty_lines:
            if not re.match(pattern, line):
                return False
        return True

    def _has_code_nodes(self, root: Any, language: str) -> bool:
        """Check if AST has actual code nodes (not just comments/whitespace)."""
        # Define what constitutes "code" nodes for each language
        code_node_types = {
            'python': ['assignment', 'function_definition', 'class_definition', 'call', 'if_statement', 
                      'for_statement', 'while_statement', 'return_statement', 'import_statement'],
            'javascript': ['assignment', 'function_declaration', 'class_declaration', 'call_expression',
                          'if_statement', 'for_statement', 'while_statement', 'return_statement'],
            'typescript': ['assignment', 'function_declaration', 'class_declaration', 'call_expression',
                          'if_statement', 'for_statement', 'while_statement', 'return_statement'],
        }

        # Default code nodes for unknown languages
        default_nodes = ['assignment', 'call', 'declaration', 'statement', 'expression']

        target_types = code_node_types.get(language, default_nodes)

        # Check if any node type contains keywords from our target types
        return self._contains_node_types(root, target_types)

    def _contains_node_types(self, node: Any, keywords: List[str]) -> bool:
        """Check if AST contains nodes with types containing any of the keywords."""
        for keyword in keywords:
            if keyword in node.type.lower():
                return True

        for child in node.children:
            if self._contains_node_types(child, keywords):
                return True

        return False

    def _looks_like_prose(self, code: str) -> bool:
        """Check if code looks more like prose than actual code."""
        # Count indicators
        prose_indicators = 0
        code_indicators = 0

        # Check for common prose patterns
        if re.search(r'\b(the|this|that|these|those|a|an)\b', code, re.IGNORECASE):
            prose_indicators += 1
        if re.search(r'\b(is|are|was|were|has|have|had)\b', code, re.IGNORECASE):
            prose_indicators += 1
        if re.search(r'\b(returns?|takes?|uses?|makes?|does)\b', code, re.IGNORECASE):
            prose_indicators += 1
        if re.search(r'[.!?]\s*$', code):  # Ends with punctuation
            prose_indicators += 1

        # Check for code patterns
        if re.search(r'[(){}\[\];]', code):  # Brackets, braces, semicolons
            code_indicators += 1
        if re.search(r'[=<>!]=?|[+\-*/]', code):  # Operators
            code_indicators += 1
        if re.search(r'\b(def|function|class|if|for|while|return)\b', code):
            code_indicators += 1
        if re.search(r'^\s+', code, re.MULTILINE):  # Indentation
            code_indicators += 1

        # If more prose indicators than code indicators, it's probably prose
        return prose_indicators > code_indicators

    def group_related_blocks(self, blocks: List[CodeBlock]) -> List[List[CodeBlock]]:
        """Group related code blocks that should stay together."""
        if not blocks:
            return []

        groups = []
        current_group = [blocks[0]]

        for i in range(1, len(blocks)):
            prev_block = blocks[i-1]
            curr_block = blocks[i]

            # Group if blocks are close together (within 10 lines)
            if (curr_block.line_start - prev_block.line_end) <= 10:
                current_group.append(curr_block)
            else:
                groups.append(current_group)
                current_group = [curr_block]

        if current_group:
            groups.append(current_group)

        return groups
