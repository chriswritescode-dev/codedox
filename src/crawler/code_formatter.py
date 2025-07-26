"""Code formatter using Prettier for JavaScript/TypeScript and other formatters for different languages."""

import json
import logging
import re
from typing import Optional
import subprocess
import tempfile
import os

logger = logging.getLogger(__name__)

# Prettier configuration
PRETTIER_CONFIG = {
    "printWidth": 100,
    "tabWidth": 2,
    "useTabs": False,
    "semi": True,
    "singleQuote": True,
    "quoteProps": "as-needed",
    "jsxSingleQuote": False,
    "trailingComma": "es5",
    "bracketSpacing": True,
    "bracketSameLine": False,
    "arrowParens": "always",
    "endOfLine": "lf",
    "embeddedLanguageFormatting": "auto",
    "singleAttributePerLine": False
}


class CodeFormatter:
    """Formats code snippets based on their language using appropriate formatters."""
    
    def __init__(self):
        """Initialize the code formatter."""
        self.prettier_path = self._find_prettier_path()
        self.prettier_available = self.prettier_path is not None
        if not self.prettier_available:
            logger.warning("Prettier not found. Run 'npm install' in src/language_detector/")
    
    def _find_prettier_path(self) -> Optional[str]:
        """Find Prettier executable in various locations."""
        # Get the directory of this file
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_file_dir))
        
        # Check common locations
        possible_paths = [
            # Primary: language_detector node_modules
            os.path.join(project_root, "src", "language_detector", "node_modules", ".bin", "prettier"),
            # Fallback: System PATH
            "prettier",
            # npm global on Unix
            "/usr/local/bin/prettier",
            # Homebrew on Apple Silicon
            "/opt/homebrew/bin/prettier",
        ]
        
        # Add node_modules/.bin in current directory and parent directories
        current_dir = os.getcwd()
        while current_dir != os.path.dirname(current_dir):
            node_bin = os.path.join(current_dir, "node_modules", ".bin", "prettier")
            if os.path.exists(node_bin):
                possible_paths.append(node_bin)
            current_dir = os.path.dirname(current_dir)
        
        # Check each path
        for path in possible_paths:
            try:
                result = subprocess.run(
                    [path, "--version"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if result.returncode == 0:
                    logger.info(f"Prettier found at {path}: {result.stdout.strip()}")
                    return path
            except (subprocess.SubprocessError, FileNotFoundError):
                continue
        
        return None
    
    def format(self, code: str, language: str) -> str:
        """
        Format code based on its language.
        
        Args:
            code: The code to format
            language: The programming language
            
        Returns:
            Formatted code
        """
        if not code or not language:
            return code
        
        # Normalize language name
        lang_lower = language.lower()
        
        # JavaScript/TypeScript family
        if lang_lower in ['javascript', 'js', 'jsx', 'typescript', 'ts', 'tsx']:
            return self._format_with_prettier(code, lang_lower)
        
        # JSON
        elif lang_lower == 'json':
            return self._format_json(code)
        
        # Python
        elif lang_lower in ['python', 'py']:
            return self._format_python(code)
        
        # HTML/XML
        elif lang_lower in ['html', 'xml', 'svg']:
            return self._format_html(code)
        
        # CSS/SCSS
        elif lang_lower in ['css', 'scss', 'sass', 'less']:
            return self._format_with_prettier(code, 'css')
        
        # YAML
        elif lang_lower in ['yaml', 'yml']:
            return self._format_yaml(code)
        
        # SQL
        elif lang_lower == 'sql':
            return self._format_sql(code)
        
        # Default: minimal cleanup
        else:
            return self._basic_format(code)
    
    def _format_with_prettier(self, code: str, language: str) -> str:
        """Format code using Prettier."""
        if not self.prettier_available:
            return self._basic_format(code)
        
        # Map language to Prettier parser
        parser_map = {
            'javascript': 'babel',
            'js': 'babel',
            'jsx': 'babel',
            'typescript': 'typescript',
            'ts': 'typescript',
            'tsx': 'typescript',
            'css': 'css',
            'scss': 'scss',
            'less': 'less',
            'json': 'json',
            'markdown': 'markdown',
            'md': 'markdown',
            'html': 'html',
            'yaml': 'yaml',
            'yml': 'yaml'
        }
        
        parser = parser_map.get(language, 'babel')
        
        try:
            # Create temporary config file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as config_file:
                json.dump(PRETTIER_CONFIG, config_file)
                config_path = config_file.name
            
            # Run Prettier
            result = subprocess.run(
                [
                    self.prettier_path,
                    "--config", config_path,
                    "--parser", parser,
                    "--stdin-filepath", f"code.{language}"
                ],
                input=code,
                capture_output=True,
                text=True,
                check=False
            )
            
            # Clean up config file
            os.unlink(config_path)
            
            if result.returncode == 0:
                return result.stdout
            else:
                logger.warning(f"Prettier formatting failed: {result.stderr}")
                return self._basic_format(code)
                
        except Exception as e:
            logger.error(f"Error running Prettier: {e}")
            return self._basic_format(code)
    
    def _format_json(self, code: str) -> str:
        """Format JSON code."""
        if self.prettier_available:
            return self._format_with_prettier(code, 'json')
        
        try:
            # Parse and re-serialize with indentation
            parsed = json.loads(code)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            logger.debug("Invalid JSON, returning as-is")
            return code
    
    def _format_python(self, code: str) -> str:
        """Format Python code with basic indentation fixes."""
        lines = code.split('\n')
        formatted_lines = []
        indent_level = 0
        indent_size = 4
        
        for line in lines:
            stripped = line.strip()
            
            # Decrease indent for dedent keywords
            if stripped.startswith(('return', 'break', 'continue', 'pass', 'raise')):
                pass
            elif stripped.startswith(('elif', 'else:', 'except', 'finally', 'except:')):
                if indent_level > 0:
                    indent_level -= 1
            elif stripped.startswith(('def ', 'class ', 'if ', 'for ', 'while ', 'with ', 'try:')):
                pass
            elif stripped and not line[0].isspace() and indent_level > 0:
                # Reset indent for top-level code
                indent_level = 0
            
            # Format the line
            if stripped:
                formatted_lines.append(' ' * (indent_level * indent_size) + stripped)
            else:
                formatted_lines.append('')
            
            # Increase indent after colon
            if stripped.endswith(':'):
                indent_level += 1
            # Decrease indent after return/break/continue/pass
            elif stripped in ('return', 'break', 'continue', 'pass'):
                if indent_level > 0:
                    indent_level -= 1
        
        return '\n'.join(formatted_lines)
    
    def _format_html(self, code: str) -> str:
        """Format HTML/XML code."""
        if self.prettier_available:
            return self._format_with_prettier(code, 'html')
        
        # Basic HTML formatting
        return self._basic_format(code)
    
    def _format_yaml(self, code: str) -> str:
        """Format YAML code."""
        if self.prettier_available:
            return self._format_with_prettier(code, 'yaml')
        
        # Basic YAML formatting - preserve structure
        lines = code.split('\n')
        formatted_lines = []
        
        for line in lines:
            # Preserve YAML indentation
            stripped = line.rstrip()
            if stripped:
                formatted_lines.append(stripped)
            else:
                formatted_lines.append('')
        
        return '\n'.join(formatted_lines)
    
    def _format_sql(self, code: str) -> str:
        """Format SQL code with basic formatting."""
        # Basic SQL keywords to uppercase
        keywords = [
            'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
            'ON', 'AND', 'OR', 'NOT', 'IN', 'EXISTS', 'BETWEEN', 'LIKE', 'IS',
            'NULL', 'ORDER', 'BY', 'GROUP', 'HAVING', 'LIMIT', 'OFFSET',
            'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE', 'CREATE',
            'TABLE', 'ALTER', 'DROP', 'INDEX', 'VIEW', 'TRIGGER', 'PROCEDURE',
            'FUNCTION', 'AS', 'BEGIN', 'END', 'IF', 'THEN', 'ELSE', 'CASE',
            'WHEN', 'CAST', 'CONVERT', 'DISTINCT', 'COUNT', 'SUM', 'AVG',
            'MIN', 'MAX', 'UNION', 'ALL', 'ASC', 'DESC'
        ]
        
        formatted = code
        for keyword in keywords:
            # Replace keyword with uppercase, but preserve case in strings
            formatted = re.sub(
                r'\b' + keyword + r'\b',
                keyword,
                formatted,
                flags=re.IGNORECASE
            )
        
        return formatted
    
    def _basic_format(self, code: str) -> str:
        """Basic formatting: trim lines and remove excess blank lines."""
        lines = code.split('\n')
        
        # Trim whitespace from each line
        formatted_lines = [line.rstrip() for line in lines]
        
        # Remove leading and trailing blank lines
        while formatted_lines and not formatted_lines[0]:
            formatted_lines.pop(0)
        while formatted_lines and not formatted_lines[-1]:
            formatted_lines.pop()
        
        # Reduce multiple blank lines to single blank lines
        result = []
        prev_blank = False
        for line in formatted_lines:
            if not line:
                if not prev_blank:
                    result.append(line)
                prev_blank = True
            else:
                result.append(line)
                prev_blank = False
        
        return '\n'.join(result)