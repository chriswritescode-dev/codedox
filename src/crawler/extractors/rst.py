"""ReStructuredText code extractor with semantic context extraction."""

import re
from typing import NamedTuple

from .base import BaseCodeExtractor
from .models import ExtractedCodeBlock, ExtractedContext


class CodeBlockInfo(NamedTuple):
    """Information about a code block."""
    code: str
    language: str | None
    start_line: int
    end_line: int
    block_type: str  # 'literal', 'code', 'code-block'


class RSTCodeExtractor(BaseCodeExtractor):
    """Extract code blocks from RST with semantic context."""
    
    def extract_blocks(self, content: str, source_url: str | None = None) -> list[ExtractedCodeBlock]:
        """Extract ONLY multi-line code blocks from RST."""
        lines = content.split('\n')
        code_blocks = self._find_code_blocks(lines)
        extracted_blocks = []
        
        # Track previous code block for each heading
        previous_code_by_heading = {}
        
        for block_info in code_blocks:
            # Check if we should extract this block
            if not self.should_extract_code_block(block_info.code):
                continue
            
            # Find preceding heading
            heading_text, heading_line = self.find_preceding_heading(lines, block_info.start_line)
            
            # Get previous code block end line for this heading
            prev_end_line = previous_code_by_heading.get((heading_text, heading_line))
            
            # Determine start line for context extraction
            if prev_end_line is not None:
                # Start after previous code block
                context_start = prev_end_line + 1
            elif heading_line >= 0:
                # Start after heading (skip underline if present)
                context_start = heading_line + 2  # +2 to skip heading and underline
            else:
                # No heading, start from beginning
                context_start = 0
            
            # Extract context between heading/previous code and current code
            context = self.extract_context_between(lines, context_start, block_info.start_line)
            
            # Update previous code block for this heading
            previous_code_by_heading[(heading_text, heading_line)] = block_info.end_line
            
            # Create extracted block
            extracted = ExtractedCodeBlock(
                code=block_info.code,
                language=block_info.language,
                context=context,
                source_url=source_url,
                line_start=block_info.start_line + 1,  # Convert to 1-based
                line_end=block_info.end_line + 1
            )
            
            extracted_blocks.append(extracted)
        
        return extracted_blocks
    
    def find_preceding_heading(self, lines: list[str], position: int) -> tuple[str | None, int]:
        """Find RST headings (overlined/underlined)."""
        heading_text = None
        heading_line = -1
        
        # RST heading characters in order of precedence
        heading_chars = '=-~^_*+#'
        
        # Search backwards from the code block
        for i in range(position - 1, -1, -1):
            if i >= len(lines) - 1:
                continue
                
            line = lines[i]
            next_line = lines[i + 1] if i + 1 < len(lines) else ''
            
            # Check for underlined heading
            if next_line and len(next_line.strip()) > 0:
                # Check if next line is all the same character
                char = next_line.strip()[0]
                if char in heading_chars and all(c == char for c in next_line.strip()):
                    # Check if underline is at least as long as the text
                    if len(next_line.strip()) >= len(line.strip()) and line.strip():
                        heading_text = line.strip()
                        heading_line = i
                        break
            
            # Check for overlined + underlined heading
            if i > 0:
                prev_line = lines[i - 1] if i > 0 else ''
                if prev_line and next_line:
                    # Check if both prev and next lines are the same character
                    if prev_line.strip() and next_line.strip():
                        char = prev_line.strip()[0]
                        if (char in heading_chars and
                            all(c == char for c in prev_line.strip()) and
                            all(c == char for c in next_line.strip()) and
                            len(prev_line.strip()) >= len(line.strip()) and
                            len(next_line.strip()) >= len(line.strip()) and
                            line.strip()):
                            heading_text = line.strip()
                            heading_line = i
                            break
        
        return heading_text, heading_line
    
    def extract_context_between(self, lines: list[str], start: int, end: int) -> ExtractedContext:
        """Extract RST directives, paragraphs, lists."""
        context_lines = []
        raw_lines = []
        
        i = start
        while i < end and i < len(lines):
            line = lines[i]
            raw_lines.append(line)
            
            # Skip empty lines
            if not line.strip():
                i += 1
                continue
            
            # Skip directive blocks we're not interested in
            if line.strip().startswith('.. ') and '::' in line:
                directive = line.strip().split('::')[0].replace('.. ', '')
                
                # Skip code-related directives (we handle those separately)
                if directive in ['code', 'code-block', 'sourcecode', 'literalinclude']:
                    # Find end of directive block
                    i += 1
                    while i < end and i < len(lines):
                        if lines[i] and not lines[i].startswith(' '):
                            break
                        i += 1
                    continue
                
                # Keep content from important directives
                if directive in ['note', 'warning', 'tip', 'important', 'caution']:
                    i += 1
                    # Extract directive content
                    while i < end and i < len(lines):
                        if lines[i] and not lines[i].startswith(' '):
                            break
                        if lines[i].strip():
                            context_lines.append(lines[i].strip())
                        i += 1
                    continue
            
            # Skip literal blocks (::)
            if line.rstrip().endswith('::'):
                # Skip the literal block
                i += 1
                while i < end and i < len(lines):
                    if lines[i] and not lines[i].startswith(' '):
                        break
                    i += 1
                continue
            
            # This is content we want to keep
            stripped = line.strip()
            
            # Remove list markers but keep content
            stripped = re.sub(r'^[\*\-\+]\s+', '', stripped)
            stripped = re.sub(r'^\d+\.\s+', '', stripped)
            
            # Handle definition lists
            if i + 1 < len(lines) and lines[i + 1].strip().startswith(':'):
                # This is a definition term
                context_lines.append(stripped)
                i += 1
                # Get the definition
                if i < len(lines) and lines[i].strip().startswith(':'):
                    def_text = lines[i].strip()[1:].strip()
                    if def_text:
                        context_lines.append(def_text)
            elif stripped:
                # Keep inline literals ``code`` in the text
                context_lines.append(stripped)
            
            i += 1
        
        # Join lines and clean up
        description = ' '.join(context_lines) if context_lines else None
        
        if description:
            # Filter noise (links, references, etc.)
            description = self.filter_noise(description, 'rst')
        
        # Build heading hierarchy (would need more context to build full hierarchy)
        hierarchy = []
        
        return ExtractedContext(
            title=None,  # Will be set from heading found earlier
            description=description,
            raw_content=raw_lines,
            hierarchy=hierarchy
        )
    
    def _find_code_blocks(self, lines: list[str]) -> list[CodeBlockInfo]:
        """Find all code blocks in RST content."""
        blocks = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check for code or code-block directives
            if line.strip().startswith('.. code') or line.strip().startswith('.. sourcecode'):
                # Extract language if present
                language = None
                if '::' in line:
                    parts = line.strip().split('::')
                    if len(parts) > 1 and parts[1].strip():
                        language = parts[1].strip()
                
                # Find the code content
                start_line = i
                i += 1
                code_lines = []
                
                # Skip any directive options
                while i < len(lines) and lines[i].strip().startswith(':'):
                    i += 1
                
                # Skip empty lines after options
                while i < len(lines) and not lines[i].strip():
                    i += 1
                
                # Collect indented code lines
                indent = None
                while i < len(lines):
                    if not lines[i].strip():
                        # Empty line in code block
                        code_lines.append('')
                        i += 1
                    elif lines[i].startswith(' ') or lines[i].startswith('\t'):
                        # Indented line (part of code block)
                        if indent is None and lines[i]:
                            # Determine the indent level from first non-empty line
                            indent = len(lines[i]) - len(lines[i].lstrip())
                        
                        # Remove the base indent
                        if indent and len(lines[i]) >= indent:
                            code_lines.append(lines[i][indent:])
                        else:
                            code_lines.append(lines[i].strip())
                        i += 1
                    else:
                        # Non-indented line, end of code block
                        break
                
                end_line = i - 1
                code = '\n'.join(code_lines).rstrip()
                
                if code:
                    blocks.append(CodeBlockInfo(
                        code=code,
                        language=language,
                        start_line=start_line,
                        end_line=end_line,
                        block_type='code-block'
                    ))
                continue
            
            # Check for literal blocks (::) but skip directives
            if line.rstrip().endswith('::') and not line.strip().startswith('..'):
                start_line = i
                i += 1
                code_lines = []
                
                # Skip empty lines
                while i < len(lines) and not lines[i].strip():
                    i += 1
                
                # Collect indented lines
                indent = None
                while i < len(lines):
                    if not lines[i].strip():
                        # Empty line in literal block
                        code_lines.append('')
                        i += 1
                    elif lines[i].startswith(' ') or lines[i].startswith('\t'):
                        # Indented line
                        if indent is None and lines[i]:
                            indent = len(lines[i]) - len(lines[i].lstrip())
                        
                        # Remove the base indent
                        if indent and len(lines[i]) >= indent:
                            code_lines.append(lines[i][indent:])
                        else:
                            code_lines.append(lines[i].strip())
                        i += 1
                    else:
                        # Non-indented line, end of literal block
                        break
                
                end_line = i - 1
                code = '\n'.join(code_lines).rstrip()
                
                if code:
                    blocks.append(CodeBlockInfo(
                        code=code,
                        language=None,
                        start_line=start_line,
                        end_line=end_line,
                        block_type='literal'
                    ))
                continue
            
            i += 1
        
        return blocks
