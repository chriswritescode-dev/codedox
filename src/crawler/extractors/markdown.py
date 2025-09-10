"""Markdown code extractor with semantic context extraction."""

import asyncio
import re
from typing import NamedTuple

from .base import BaseCodeExtractor
from .models import ExtractedCodeBlock, ExtractedContext
from .utils import extract_frontmatter


class CodeBlockInfo(NamedTuple):
    """Information about a code block."""
    code: str
    language: str | None
    start_line: int
    end_line: int
    is_fenced: bool


class MarkdownCodeExtractor(BaseCodeExtractor):
    """Extract code blocks from Markdown with semantic context."""
    
    async def extract_blocks(self, content: str, source_url: str | None = None, batch_size: int = 5) -> list[ExtractedCodeBlock]:
        """Extract code blocks with full semantic context."""
        # Remove frontmatter if present
        _, content = extract_frontmatter(content)
        
        lines = content.split('\n')
        
        # Get the main page title (first H1)
        main_title = self._get_main_title(lines)
        
        code_blocks = self._find_code_blocks(lines)
        extracted_blocks = []
        
        # Track previous code block for each heading
        previous_code_by_heading = {}
        
        for i, block_info in enumerate(code_blocks):
            # Yield control every batch_size blocks to prevent blocking
            if i > 0 and i % batch_size == 0:
                await asyncio.sleep(0)  # Let other coroutines run
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
                # Start after heading
                context_start = heading_line + 1
                # For setext headings, also skip the underline
                if context_start < len(lines):
                    line = lines[context_start].strip()
                    if re.match(r'^=+$', line) or re.match(r'^-+$', line):
                        context_start += 1
            else:
                # No heading, start from beginning
                context_start = 0
            
            # Extract context between heading/previous code and current code
            context = self.extract_context_between(lines, context_start, block_info.start_line)
            
            # Set the title combining section heading with page title
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
    
    def _get_main_title(self, lines: list[str]) -> str | None:
        """Get the main page title from the first H1 heading."""
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Check for ATX H1 heading (single #)
            if line.startswith('# ') and not line.startswith('## '):
                return line[2:].strip()
            
            # Check for Setext H1 heading (underlined with ===)
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and re.match(r'^=+$', next_line) and line:
                    return line
        
        return None
    
    def find_preceding_heading(self, lines: list[str], position: int) -> tuple[str | None, int]:
        """Find nearest heading before code block."""
        heading_text = None
        heading_line = -1
        
        # Search backwards from the code block
        for i in range(position - 1, -1, -1):
            line = lines[i].strip()
            
            # Check for ATX headings (# ## ###)
            if line.startswith('#'):
                match = re.match(r'^#+\s+(.+)$', line)
                if match:
                    heading_text = match.group(1).strip()
                    heading_line = i
                    break
            
            # Check for Setext headings (underlined with = or -)
            if i > 0:
                prev_line = lines[i - 1].strip()
                if prev_line and not prev_line.startswith('#'):
                    # Check if current line is all = or -
                    if re.match(r'^=+$', line) or re.match(r'^-+$', line):
                        heading_text = prev_line
                        heading_line = i - 1
                        break
        
        return heading_text, heading_line
    
    def extract_context_between(self, lines: list[str], start: int, end: int) -> ExtractedContext:
        """Extract paragraphs, lists, blockquotes between positions."""
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
            
            # Skip code blocks that we're not extracting
            if line.strip().startswith('```') or line.strip().startswith('~~~'):
                # Find end of fenced code block
                fence = line.strip()[:3]
                i += 1
                while i < end and i < len(lines):
                    if lines[i].strip().startswith(fence):
                        i += 1
                        break
                    i += 1
                continue
            
            # Check for indented code blocks (4 spaces or tab)
            if line.startswith('    ') or line.startswith('\t'):
                # Skip indented code blocks
                while i < end and i < len(lines):
                    if lines[i].startswith('    ') or lines[i].startswith('\t'):
                        i += 1
                    else:
                        break
                continue
            
            # This is content we want to keep
            stripped = line.strip()
            
            # Remove list markers but keep content
            stripped = re.sub(r'^[\*\-\+]\s+', '', stripped)
            stripped = re.sub(r'^\d+\.\s+', '', stripped)
            
            # Remove blockquote markers
            stripped = re.sub(r'^>\s*', '', stripped)
            
            if stripped:
                context_lines.append(stripped)
            
            i += 1
        
        # Join lines and clean up
        description = ' '.join(context_lines) if context_lines else None
        
        if description:
            # Filter noise (links, badges, etc.)
            description = self.filter_noise(description, 'markdown')
        
        # Build heading hierarchy (would need more context to build full hierarchy)
        hierarchy = []
        
        # Get title from the heading we found earlier
        title = None
        if start > 0:
            # Look back for the heading
            for i in range(start - 1, max(0, start - 10), -1):
                line = lines[i].strip()
                if line.startswith('#'):
                    match = re.match(r'^#+\s+(.+)$', line)
                    if match:
                        title = match.group(1).strip()
                        break
        
        return ExtractedContext(
            title=title,
            description=description,
            raw_content=raw_lines,
            hierarchy=hierarchy
        )
    
    def _find_code_blocks(self, lines: list[str]) -> list[CodeBlockInfo]:
        """Find all code blocks in the markdown content."""
        blocks = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check for fenced code blocks (``` or ~~~)
            if line.strip().startswith('```') or line.strip().startswith('~~~'):
                fence = line.strip()[:3]
                # Extract language if present
                language_match = re.match(r'^```\s*(\w+)', line.strip())
                language = language_match.group(1) if language_match else None
                
                # Find end of code block
                start_line = i
                i += 1
                code_lines = []
                
                while i < len(lines):
                    if lines[i].strip().startswith(fence):
                        end_line = i
                        code = '\n'.join(code_lines)
                        
                        blocks.append(CodeBlockInfo(
                            code=code,
                            language=language,
                            start_line=start_line,
                            end_line=end_line,
                            is_fenced=True
                        ))
                        break
                    code_lines.append(lines[i])
                    i += 1
                else:
                    # Handle unclosed fence block - extract until EOF
                    end_line = len(lines) - 1
                    code = '\n'.join(code_lines)
                    
                    blocks.append(CodeBlockInfo(
                        code=code,
                        language=language,
                        start_line=start_line,
                        end_line=end_line,
                        is_fenced=True
                    ))
            
            # Check for indented code blocks (4 spaces or tab)
            elif line.startswith('    ') or line.startswith('\t'):
                start_line = i
                code_lines = []
                
                # Collect all consecutive indented lines
                while i < len(lines) and (lines[i].startswith('    ') or lines[i].startswith('\t')):
                    # Remove indentation
                    if lines[i].startswith('    '):
                        code_lines.append(lines[i][4:])
                    else:
                        code_lines.append(lines[i][1:])  # Remove tab
                    i += 1
                
                end_line = i - 1
                code = '\n'.join(code_lines)
                
                blocks.append(CodeBlockInfo(
                    code=code,
                    language=None,  # Indented blocks don't specify language
                    start_line=start_line,
                    end_line=end_line,
                    is_fenced=False
                ))
                continue
            
            i += 1
        
        return blocks
