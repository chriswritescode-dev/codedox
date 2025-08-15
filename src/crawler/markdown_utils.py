"""Utilities for processing markdown content."""

import re


def remove_markdown_links(content: str) -> str:
    """Remove lines containing markdown links (typically navigation/menu items).
    
    Only removes entire lines that contain markdown link syntax like:
    - * [text](url)
    - [text](url)
    - ![alt text](url)
    
    Preserves all other content including plain URLs and regular text.
    
    Args:
        content: Markdown content to clean
        
    Returns:
        Content with link lines removed
    """
    if not content:
        return content
    
    lines = content.split('\n')
    filtered_lines = []
    
    for line in lines:
        # Check if line contains markdown link pattern [text](url)
        # This includes lines starting with *, -, +, or numbers (list items)
        if re.search(r'\[[^\]]+\]\([^)]+\)', line):
            # Skip this line - it contains a markdown link
            continue
        # Also check for image links ![text](url)
        elif re.search(r'!\[[^\]]*\]\([^)]+\)', line):
            # Skip this line - it contains an image link
            continue
        # Also check for reference-style link definitions [ref]: url
        elif re.match(r'^\s*\[[^\]]+\]:\s*https?://', line):
            # Skip this line - it's a reference definition
            continue
        else:
            # Keep this line - no markdown links found
            filtered_lines.append(line)
    
    # Join lines back together
    content = '\n'.join(filtered_lines)
    
    # Clean up multiple consecutive blank lines (but keep some spacing)
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    return content.strip()