"""Shared utilities for code extraction."""

import re


def remove_markdown_links(text: str) -> str:
    """Remove markdown links but keep text: [text](url) → text."""
    # Handle inline links [text](url)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Handle reference links [text][ref]
    text = re.sub(r'\[([^\]]+)\]\[[^\]]+\]', r'\1', text)
    # Handle standalone reference definitions [ref]: url
    text = re.sub(r'^\[[^\]]+\]:\s+.+$', '', text, flags=re.MULTILINE)
    return text


def remove_markdown_images(text: str) -> str:
    """Remove markdown image references: ![alt](url) → removed."""
    # Remove inline images
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', text)
    # Remove reference images
    text = re.sub(r'!\[([^\]]*)\]\[[^\]]+\]', '', text)
    return text


def remove_html_comments(text: str) -> str:
    """Remove HTML comments: <!-- comment --> → removed."""
    return re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)


def remove_badges(text: str) -> str:
    """Remove common badge patterns from text."""
    # Remove shields.io badges
    text = re.sub(r'https?://[^/]*shields\.io/[^\s\)]+', '', text)
    text = re.sub(r'https?://[^/]*badge[^\s\)]+', '', text)
    text = re.sub(r'https?://[^/]*travis-ci[^\s\)]+', '', text)
    text = re.sub(r'https?://[^/]*codecov[^\s\)]+', '', text)
    text = re.sub(r'https?://[^/]*coveralls[^\s\)]+', '', text)
    return text


def remove_rst_references(text: str) -> str:
    """Remove RST references: `text <url>`_ → text."""
    # Remove inline references
    text = re.sub(r'`([^<]+)\s+<[^>]+>`_', r'\1', text)
    # Remove footnotes [#]_ or [1]_
    text = re.sub(r'\[[#\d]+\]_', '', text)
    return text


def clean_rst_directives(text: str) -> str:
    """Clean RST directives while preserving important ones."""
    # Remove toctree and other navigation directives including their content
    # This handles both the directive line and any indented content below it
    lines = text.split('\n')
    cleaned_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        stripped_line = line.strip()
        
        # Check for navigation directives to remove
        if re.match(r'^\.\.\s+(toctree|contents|include)::', stripped_line):
            # Skip this line and any following indented lines
            i += 1
            # Get the indentation level of the next line to determine what's part of the directive
            base_indent = len(line) - len(line.lstrip())
            while i < len(lines):
                next_line = lines[i]
                if next_line.strip():  # Non-empty line
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent <= base_indent:
                        # Back to same or less indentation, directive is done
                        break
                i += 1
            continue
        
        # Check for important directives to keep content but remove syntax
        match = re.match(r'^\.\.\s+(note|warning|tip|important|caution)::\s*(.*)', stripped_line)
        if match:
            # Keep the indentation of the original line
            indent = line[:len(line) - len(stripped_line)]
            
            # Add any content on the same line
            if match.group(2):
                cleaned_lines.append(indent + match.group(2))
            i += 1
            
            # Get base indentation for content
            base_indent = len(line) - len(line.lstrip())
            
            # Keep the indented content but preserve relative indentation
            while i < len(lines):
                next_line = lines[i]
                if next_line.strip():  # Non-empty line
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent <= base_indent:
                        # Back to same or less indentation, directive is done
                        break
                    # Add content, removing the directive's indentation
                    cleaned_lines.append(indent + next_line.strip())
                else:
                    cleaned_lines.append('')  # Preserve empty lines
                i += 1
            continue
        
        cleaned_lines.append(line)
        i += 1
    
    return '\n'.join(cleaned_lines)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text."""
    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)
    # Replace multiple newlines with double newline
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Strip leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    return '\n'.join(lines).strip()


def is_navigation_text(text: str) -> bool:
    """Check if text is likely navigation content."""
    nav_patterns = [
        r'^(previous|next|back|forward|home|index|contents?|table of contents)$',
        r'^go to',
        r'^return to',
        r'^back to',
        r'^\[?(<|>|<<|>>|←|→)\]?$',
        r'^page \d+',
    ]
    text_lower = text.lower().strip()
    return any(re.match(pattern, text_lower) for pattern in nav_patterns)


def filter_noise(text: str, format_type: str = 'markdown') -> str:
    """Remove noise from text based on format type."""
    if format_type == 'markdown':
        text = remove_markdown_links(text)
        text = remove_markdown_images(text)
        text = remove_html_comments(text)
        text = remove_badges(text)
    elif format_type == 'rst':
        text = remove_rst_references(text)
        text = clean_rst_directives(text)
    elif format_type == 'html':
        # HTML noise filtering is handled by BeautifulSoup in html.py
        pass
    
    # Common cleanup for all formats
    text = normalize_whitespace(text)
    
    # Remove lines that are just navigation
    lines = text.split('\n')
    filtered_lines = [line for line in lines if not is_navigation_text(line)]
    
    return '\n'.join(filtered_lines).strip()


def extract_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML/TOML frontmatter from content."""
    frontmatter = {}
    remaining_content = content
    
    # Check for YAML frontmatter (---)
    if content.startswith('---'):
        match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if match:
            # We could parse the frontmatter here if needed
            remaining_content = content[match.end():]
    
    # Check for TOML frontmatter (+++)
    elif content.startswith('+++'):
        match = re.match(r'^\+\+\+\n(.*?)\n\+\+\+\n', content, re.DOTALL)
        if match:
            remaining_content = content[match.end():]
    
    return frontmatter, remaining_content
