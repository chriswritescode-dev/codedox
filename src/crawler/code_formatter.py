"""Code formatting utilities for extracted code blocks."""

import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import optional formatting libraries
try:
    import jsbeautifier
    JSBEAUTIFIER_AVAILABLE = True
except ImportError:
    JSBEAUTIFIER_AVAILABLE = False
    logger.info("jsbeautifier not available - using fallback JS/TS formatting")

try:
    import black
    BLACK_AVAILABLE = True
except ImportError:
    BLACK_AVAILABLE = False
    logger.info("black not available - using fallback Python formatting")


class CodeFormatter:
    """Formats extracted code blocks using language-specific rules."""
    
    def __init__(self):
        """Initialize the code formatter."""
        # Configure jsbeautifier options for better JSX formatting
        self.js_options = {
            'indent_size': 2,
            'indent_char': ' ',
            'max_preserve_newlines': 2,
            'preserve_newlines': True,
            'keep_array_indentation': False,
            'break_chained_methods': False,
            'indent_scripts': 'normal',
            'brace_style': 'collapse',
            'space_before_conditional': True,
            'unescape_strings': False,
            'jslint_happy': False,
            'end_with_newline': False,
            'wrap_line_length': 120,  # Increased to prevent breaking JSX tags
            'indent_inner_html': False,
            'comma_first': False,
            'e4x': True,  # Enable E4X support for JSX
            'indent_empty_lines': False,
            'unformatted': [],  # Don't preserve unformatted sections
            'extra_liners': []  # Don't add extra lines around certain elements
        }
    
    def format_code(self, code: str, language: Optional[str] = None) -> str:
        """
        Format code using appropriate formatter for the language.
        
        Args:
            code: Raw code text (potentially single-line or poorly formatted)
            language: Programming language (js, python, json, etc.)
            
        Returns:
            Properly formatted code with correct line breaks and indentation
        """
        if not code or not code.strip():
            return code
            
        # Normalize language
        lang = self._normalize_language(language) if language else None
        
        try:
            # Try language-specific formatters first
            if lang == 'javascript':
                return self._format_javascript(code)
            elif lang == 'typescript':
                return self._format_typescript(code)
            elif lang == 'python':
                return self._format_python(code)
            elif lang == 'json':
                return self._format_json(code)
            elif lang in ['bash', 'shell', 'sh']:
                return self._format_shell(code)
            elif lang in ['html', 'xml']:
                return self._format_html(code)
            elif lang == 'css':
                return self._format_css(code)
            else:
                # Use basic heuristic formatting for unknown languages
                return self._format_basic(code, lang)
                
        except Exception as e:
            logger.warning(f"Failed to format {lang} code: {e}")
            # Fallback to basic formatting
            try:
                return self._format_basic(code, lang)
            except Exception:
                # Ultimate fallback - return original code
                logger.error(f"All formatting attempts failed for {lang} code")
                return code
    
    def _normalize_language(self, language: str) -> str:
        """Normalize language name to standard format."""
        lang = language.lower().strip()
        
        # Handle common aliases
        aliases = {
            'js': 'javascript',
            'ts': 'typescript',
            'py': 'python',
            'sh': 'shell',
            'bash': 'shell',
            'zsh': 'shell',
            'fish': 'shell',
        }
        
        return aliases.get(lang, lang)
    
    def _format_javascript(self, code: str) -> str:
        """Format JavaScript code using jsbeautifier if available."""
        if JSBEAUTIFIER_AVAILABLE:
            try:
                return jsbeautifier.beautify(code, self.js_options)
            except Exception as e:
                logger.warning(f"jsbeautifier failed: {e}, using fallback")
                return self._format_c_like_fallback(code, 'javascript')
        else:
            return self._format_c_like_fallback(code, 'javascript')
    
    def _format_typescript(self, code: str) -> str:
        """Format TypeScript code using jsbeautifier if available."""
        if JSBEAUTIFIER_AVAILABLE:
            try:
                return jsbeautifier.beautify(code, self.js_options)
            except Exception as e:
                logger.warning(f"jsbeautifier failed: {e}, using fallback")
                return self._format_c_like_fallback(code, 'typescript')
        else:
            return self._format_c_like_fallback(code, 'typescript')
    
    def _format_python(self, code: str) -> str:
        """Format Python code using black if available."""
        if BLACK_AVAILABLE:
            try:
                # Use black to format the code
                formatted = black.format_str(code, mode=black.FileMode())
                return formatted.strip()
            except Exception as e:
                logger.warning(f"black formatting failed: {e}, using fallback")
                return self._format_python_fallback(code)
        else:
            return self._format_python_fallback(code)
    
    def _format_python_fallback(self, code: str) -> str:
        """Fallback Python formatting using basic rules."""
        lines = []
        indent_level = 0
        
        # Split on common Python separators
        parts = re.split(r'(;|\n)', code)
        current_line = ""
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            if part == ';':
                # End of statement
                if current_line:
                    lines.append('    ' * indent_level + current_line)
                    current_line = ""
            elif part == '\n':
                # Already a newline - keep it
                if current_line:
                    lines.append('    ' * indent_level + current_line)
                    current_line = ""
            else:
                # Check for indent changes
                if part.endswith(':'):
                    # Starting a block
                    current_line += part
                    lines.append('    ' * indent_level + current_line)
                    indent_level += 1
                    current_line = ""
                elif part in ['else:', 'elif', 'except:', 'finally:']:
                    # Block keywords
                    if current_line:
                        lines.append('    ' * indent_level + current_line)
                    current_line = part
                else:
                    if current_line:
                        current_line += " " + part
                    else:
                        current_line = part
        
        # Add final line
        if current_line:
            lines.append('    ' * indent_level + current_line)
        
        return '\n'.join(lines) if lines else code
    
    def _format_json(self, code: str) -> str:
        """Format JSON code with proper indentation."""
        try:
            # Try to parse and reformat
            parsed = json.loads(code)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            # Not valid JSON, try basic formatting
            return self._format_basic(code, 'json')
    
    def _format_shell(self, code: str) -> str:
        """Format shell/bash code."""
        lines = []
        
        # Split on common shell separators
        parts = re.split(r'(;|&&|\|\||\n)', code)
        current_line = ""
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            if part in [';', '&&', '||']:
                # Command separator
                if current_line:
                    lines.append(current_line)
                    current_line = ""
            elif part == '\n':
                # Newline
                if current_line:
                    lines.append(current_line)
                    current_line = ""
            else:
                if current_line:
                    current_line += " " + part
                else:
                    current_line = part
        
        # Add final line
        if current_line:
            lines.append(current_line)
        
        return '\n'.join(lines) if lines else code
    
    def _format_html(self, code: str) -> str:
        """Format HTML/XML code."""
        # Basic HTML formatting with indentation
        indent_level = 0
        lines = []
        
        # Split on tag boundaries
        parts = re.split(r'(<[^>]*>)', code)
        current_line = ""
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            if part.startswith('<'):
                # HTML tag
                if part.startswith('</'):
                    # Closing tag
                    indent_level = max(0, indent_level - 1)
                    if current_line:
                        lines.append('  ' * (indent_level + 1) + current_line)
                        current_line = ""
                    lines.append('  ' * indent_level + part)
                elif part.endswith('/>'):
                    # Self-closing tag
                    if current_line:
                        lines.append('  ' * indent_level + current_line + ' ' + part)
                        current_line = ""
                    else:
                        lines.append('  ' * indent_level + part)
                else:
                    # Opening tag
                    if current_line:
                        lines.append('  ' * indent_level + current_line)
                        current_line = ""
                    lines.append('  ' * indent_level + part)
                    indent_level += 1
            else:
                # Text content
                if current_line:
                    current_line += " " + part
                else:
                    current_line = part
        
        # Add final line
        if current_line:
            lines.append('  ' * indent_level + current_line)
        
        return '\n'.join(lines) if lines else code
    
    def _format_css(self, code: str) -> str:
        """Format CSS code."""
        lines = []
        indent_level = 0
        current_line = ""
        
        # Split on CSS separators
        parts = re.split(r'([{};":])', code)
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            if part == '{':
                # Start of CSS block
                current_line += ' {'
                lines.append('  ' * indent_level + current_line)
                indent_level += 1
                current_line = ""
            elif part == '}':
                # End of CSS block
                if current_line:
                    lines.append('  ' * indent_level + current_line)
                    current_line = ""
                indent_level = max(0, indent_level - 1)
                lines.append('  ' * indent_level + '}')
            elif part == ';':
                # End of CSS property
                current_line += ';'
                lines.append('  ' * indent_level + current_line)
                current_line = ""
            elif part == ':':
                # CSS property separator
                current_line += ':'
            else:
                if current_line:
                    current_line += " " + part
                else:
                    current_line = part
        
        # Add final line
        if current_line:
            lines.append('  ' * indent_level + current_line)
        
        return '\n'.join(lines) if lines else code
    
    def _format_c_like_fallback(self, code: str, language: str) -> str:
        """Format C-like languages (JavaScript, TypeScript, Java, C#, etc.) with cleaner formatting."""
        # Simpler but more reliable approach - focus on core formatting issues
        
        # Step 1: Clean up whitespace
        code = re.sub(r'\s+', ' ', code.strip())
        
        # Step 2: Add strategic line breaks
        formatted = code
        
        # Import/export statements
        formatted = re.sub(r'(import\s+[^}]+}\s*from\s+[^;]+;)', r'\1\n', formatted)
        formatted = re.sub(r'(export\s+[^{;]+[;}])', r'\1\n', formatted)
        
        # Function declarations
        formatted = re.sub(r'((?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+\w+[^{]*{)', r'\n\1', formatted)
        
        # Variable declarations at start of statements  
        formatted = re.sub(r'([;}]\s*)(const\s|let\s|var\s)', r'\1\n\2', formatted)
        
        # Add line breaks after opening braces when followed by content
        formatted = re.sub(r'{\s*([a-zA-Z_$])', r'{\n\1', formatted)
        
        # Add line breaks before closing braces when preceded by content
        formatted = re.sub(r'([a-zA-Z0-9_$;)\]}])\s*}', r'\1\n}', formatted)
        
        # Add line breaks after semicolons when followed by statements
        formatted = re.sub(r';\s*([a-zA-Z_$])', r';\n\1', formatted)
        
        # Step 3: Apply indentation
        lines = formatted.split('\n')
        result_lines = []
        indent_level = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Adjust indentation based on braces
            if line.startswith('}'):
                indent_level = max(0, indent_level - 1)
            
            # Apply current indentation
            indented_line = '  ' * indent_level + line
            
            # Basic spacing cleanup
            indented_line = self._basic_js_cleanup(indented_line)
            
            result_lines.append(indented_line)
            
            # Increase indentation after opening braces
            if line.endswith('{'):
                indent_level += 1
        
        return '\n'.join(result_lines) if result_lines else code
    
    def _basic_js_cleanup(self, line: str) -> str:
        """Basic cleanup for JavaScript/TypeScript lines."""
        # Add space after keywords
        line = re.sub(r'\b(const|let|var|if|for|while|function|return|async|await|export|import|from)\b(?!\s)', r'\1 ', line)
        
        # Add space around = operator
        line = re.sub(r'(\w)=([^=])', r'\1 = \2', line)
        
        # Add space after commas
        line = re.sub(r',(?!\s)', ', ', line)
        
        # Add space around : in object literals
        line = re.sub(r'(\w):(?!\s)', r'\1: ', line)
        
        # Clean up multiple spaces
        line = re.sub(r'\s+', ' ', line)
        
        return line
    
    
    def _format_basic(self, code: str, language: Optional[str] = None) -> str:
        """Basic formatting using simple heuristics."""
        if not code.strip():
            return code
            
        # If code already has reasonable line breaks, don't mess with it
        if '\n' in code and len(code.split('\n')) > 1:
            lines = code.split('\n')
            # Clean up each line but preserve structure
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            return '\n'.join(cleaned_lines)
        
        # Apply basic line break heuristics for single-line code
        formatted = code
        
        # Add line breaks after common statement terminators
        formatted = re.sub(r';(?!\s*$)', ';\n', formatted)
        
        # Add line breaks after opening braces
        formatted = re.sub(r'\{(?!\s*$)', '{\n', formatted)
        
        # Add line breaks before closing braces
        formatted = re.sub(r'(?<!^\s*)\}', '\n}', formatted)
        
        # Clean up multiple newlines
        formatted = re.sub(r'\n\s*\n', '\n', formatted)
        
        # Clean up each line
        lines = formatted.split('\n')
        cleaned_lines = [line.strip() for line in lines if line.strip()]
        
        return '\n'.join(cleaned_lines) if cleaned_lines else code