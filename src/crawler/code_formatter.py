"""Code formatter using Prettier for JavaScript/TypeScript and other formatters for different languages."""

import json
import logging
import re
from typing import Optional, Tuple, Dict, Any
import subprocess
import tempfile
import os
import shlex
from contextlib import contextmanager

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


@contextmanager
def secure_temp_file(suffix=None, mode='w', delete=True):
    """Context manager for secure temporary file creation and cleanup."""
    temp_file = None
    try:
        temp_file = tempfile.NamedTemporaryFile(
            mode=mode,
            suffix=suffix,
            delete=False  # We'll handle deletion ourselves
        )
        temp_path = temp_file.name
        temp_file.close()  # Close immediately so subprocess can access it
        yield temp_path
    finally:
        if temp_file and os.path.exists(temp_path) and delete:
            try:
                os.unlink(temp_path)
            except OSError as e:
                logger.warning(f"Failed to delete temp file {temp_path}: {e}")


class CodeFormatter:
    """Formats code snippets based on their language using appropriate formatters."""
    
    def __init__(self):
        """Initialize the code formatter."""
        self.prettier_path = self._find_prettier_path()
        self.prettier_available = self.prettier_path is not None
        if not self.prettier_available:
            logger.warning("Prettier not found. Install it globally with 'npm install -g prettier'")
    
    def _find_prettier_path(self) -> Optional[str]:
        """Find Prettier executable in various locations with security validation."""
        # Get the directory of this file
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_file_dir))
        
        # Check common locations
        possible_paths = [
            # Primary: System PATH
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
        
        # Check each path with security validation
        for path in possible_paths:
            try:
                # Get absolute path for security checks
                abs_path = os.path.abspath(path) if not path.startswith('/') else path
                
                # For non-system paths, validate they're accessible
                if os.path.exists(abs_path) and os.access(abs_path, os.X_OK):
                    # Test execution with safe arguments
                    result = subprocess.run(
                        [abs_path, "--version"],
                        capture_output=True,
                        text=True,
                        check=False,
                        env={**os.environ, "NODE_ENV": "production"}  # Ensure safe environment
                    )
                    if result.returncode == 0:
                        logger.info(f"Prettier found at {abs_path}: {result.stdout.strip()}")
                        return abs_path
            except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
                logger.debug(f"Failed to check prettier at {path}: {e}")
                continue
        
        return None
    
    def format(self, code: str, language: Optional[str] = None) -> str:
        """
        Format code based on its language.
        
        Args:
            code: The code to format
            language: The programming language (optional, will auto-detect if not provided)
            
        Returns:
            Formatted code
        """
        if not code:
            return code
        
        # Try auto-detection if no language provided
        if not language:
            return self._format_with_auto_detection(code)
        
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
        
        # Default: for truly unknown languages, just use basic formatting
        # Don't try auto-detection for explicit unknown/text languages
        else:
            if lang_lower in ['unknown', 'text', 'plaintext']:
                return self._basic_format(code)
            # For other unrecognized languages, try auto-detection
            formatted = self._format_with_auto_detection(code)
            if formatted != code:
                return formatted
            return self._basic_format(code)
    
    def _format_with_prettier(self, code: str, language: str) -> str:
        """Format code using Prettier with secure temp file handling."""
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
            # Use secure temp file context manager
            with secure_temp_file(suffix='.json') as config_path:
                # Write config to temp file
                with open(config_path, 'w') as f:
                    json.dump(PRETTIER_CONFIG, f)
                
                # Validate prettier path still exists
                if not os.path.exists(self.prettier_path):
                    logger.error("Prettier executable not found")
                    return self._basic_format(code)
                
                # Run Prettier with validated arguments
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
                    check=False,
                    env={**os.environ, "NODE_ENV": "production"}  # Safe environment
                )
                
                if result.returncode == 0:
                    return result.stdout
                else:
                    logger.warning(f"Prettier formatting failed with parser '{parser}': {result.stderr}")
                    
                    # Try related parsers as fallback
                    fallback_parsers = self._get_fallback_parsers(parser)
                    for fallback_parser in fallback_parsers:
                        logger.debug(f"Trying fallback parser: {fallback_parser}")
                        fallback_result = self._try_prettier_with_parser(code, fallback_parser, config_path)
                        if fallback_result:
                            logger.info(f"Successfully formatted with fallback parser: {fallback_parser}")
                            return fallback_result
                    
                    # Try auto-detection as last resort
                    auto_formatted = self._try_prettier_auto_detect(code)
                    if auto_formatted:
                        return auto_formatted
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
        
        # Trim whitespace from each line (including leading whitespace)
        formatted_lines = [line.strip() for line in lines]
        
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
    
    def _format_with_auto_detection(self, code: str) -> str:
        """Try to format code by auto-detecting the language."""
        if not self.prettier_available:
            return self._basic_format(code)
        
        # First try to detect language from code patterns
        detected_lang = self._detect_language_from_patterns(code)
        if detected_lang:
            logger.debug(f"Detected language from patterns: {detected_lang}")
            formatted = self.format(code, detected_lang)
            if formatted != code:
                return formatted
        
        # Try common file extensions to trigger Prettier's auto-detection
        common_extensions = [
            'js',    # JavaScript
            'ts',    # TypeScript
            'jsx',   # React JSX
            'tsx',   # TypeScript JSX
            'json',  # JSON
            'css',   # CSS
            'scss',  # SCSS
            'html',  # HTML
            'md',    # Markdown
            'yaml',  # YAML
            'yml',   # YAML
            'xml',   # XML
        ]
        
        for ext in common_extensions:
            formatted = self._try_prettier_with_extension(code, ext)
            if formatted and formatted != code:
                logger.info(f"Auto-detected format as {ext}")
                return formatted
        
        # If all fail, try without extension (Prettier might detect from content)
        formatted = self._try_prettier_auto_detect(code)
        if formatted:
            return formatted
        
        return code
    
    def _try_prettier_with_extension(self, code: str, extension: str) -> Optional[str]:
        """Try formatting with Prettier using a specific file extension."""
        if not self.prettier_available:
            return None
        
        try:
            with secure_temp_file(suffix='.json') as config_path:
                with open(config_path, 'w') as f:
                    json.dump(PRETTIER_CONFIG, f)
                
                result = subprocess.run(
                    [
                        self.prettier_path,
                        "--config", config_path,
                        "--stdin-filepath", f"code.{extension}"
                    ],
                    input=code,
                    capture_output=True,
                    text=True,
                    check=False,
                    env={**os.environ, "NODE_ENV": "production"}
                )
                
                if result.returncode == 0:
                    return result.stdout
                
        except Exception as e:
            logger.debug(f"Failed to format with extension {extension}: {e}")
        
        return None
    
    def _try_prettier_auto_detect(self, code: str) -> Optional[str]:
        """Try formatting with Prettier without specifying parser or extension."""
        if not self.prettier_available:
            return None
        
        try:
            with secure_temp_file(suffix='.json') as config_path:
                with open(config_path, 'w') as f:
                    json.dump(PRETTIER_CONFIG, f)
                
                # Try without any parser or file extension hints
                result = subprocess.run(
                    [
                        self.prettier_path,
                        "--config", config_path
                    ],
                    input=code,
                    capture_output=True,
                    text=True,
                    check=False,
                    env={**os.environ, "NODE_ENV": "production"}
                )
                
                if result.returncode == 0:
                    return result.stdout
                
        except Exception as e:
            logger.debug(f"Failed to auto-detect format: {e}")
        
        return None
    
    def _get_fallback_parsers(self, parser: str) -> list[str]:
        """Get related parsers to try as fallbacks."""
        fallback_map = {
            'babel': ['typescript', 'babel-ts', 'espree'],
            'typescript': ['babel', 'babel-ts'],
            'babel-ts': ['typescript', 'babel'],
            'css': ['scss', 'less'],
            'scss': ['css', 'less'],
            'less': ['css', 'scss'],
            'json': ['json5', 'jsonc'],
            'yaml': ['yml'],
            'yml': ['yaml'],
        }
        return fallback_map.get(parser, [])
    
    def _try_prettier_with_parser(self, code: str, parser: str, config_path: str) -> Optional[str]:
        """Try formatting with a specific Prettier parser."""
        try:
            result = subprocess.run(
                [
                    self.prettier_path,
                    "--config", config_path,
                    "--parser", parser
                ],
                input=code,
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "NODE_ENV": "production"}
            )
            
            if result.returncode == 0:
                return result.stdout
                
        except Exception as e:
            logger.debug(f"Failed with parser {parser}: {e}")
        
        return None
    
    def _detect_language_from_patterns(self, code: str) -> Optional[str]:
        """Detect language from code patterns and syntax."""
        # Quick bail out for empty or very short code
        if not code or len(code) < 10:
            return None
        
        # JSON detection
        code_stripped = code.strip()
        if (code_stripped.startswith('{') and code_stripped.endswith('}')) or \
           (code_stripped.startswith('[') and code_stripped.endswith(']')):
            try:
                json.loads(code)
                return 'json'
            except:
                pass
        
        # HTML/XML detection
        if re.search(r'<\w+[^>]*>', code) and re.search(r'</\w+>', code):
            if '<!DOCTYPE html' in code or '<html' in code:
                return 'html'
            return 'xml'
        
        # Python detection
        if any(pattern in code for pattern in ['def ', 'class ', 'import ', 'from ', 'if __name__']):
            if re.search(r'\bdef\s+\w+\s*\([^)]*\):', code) or \
               re.search(r'\bclass\s+\w+\s*[\(:]', code):
                return 'python'
        
        # JavaScript/TypeScript detection
        # TypeScript specific patterns first
        if any(pattern in code for pattern in ['interface ', 'type ', ': string', ': number', ': boolean', '<T>', 'enum ', 'implements ']):
            return 'typescript'
        
        if any(pattern in code for pattern in ['function ', 'const ', 'let ', 'var ', '=>', 'export ', 'import ']):
            # React JSX
            if re.search(r'<[A-Z]\w+', code) or 'React' in code:
                return 'jsx'
            return 'javascript'
        
        # CSS detection
        if re.search(r'[.#]?\w+\s*{[^}]*}', code) and any(prop in code for prop in ['color:', 'background:', 'margin:', 'padding:', 'display:', 'position:']):
            # SCSS specific
            if '$' in code and ':' in code:
                return 'scss'
            return 'css'
        
        # YAML detection
        if re.search(r'^\s*\w+:\s*\S', code, re.MULTILINE) and not '{' in code:
            return 'yaml'
        
        # SQL detection
        sql_keywords = ['SELECT', 'FROM', 'WHERE', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'TABLE']
        if any(keyword in code.upper() for keyword in sql_keywords):
            return 'sql'
        
        return None
    
    def format_with_info(self, code: str, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Format code and return detailed information about the formatting process.
        
        Args:
            code: The code to format
            language: The programming language (optional, will auto-detect if not provided)
            
        Returns:
            Dict containing:
                - formatted: The formatted code
                - original_language: The language provided
                - detected_language: Language detected from patterns (if any)
                - formatter_used: Which formatter was ultimately used
                - changed: Whether the code was changed
        """
        if not code:
            return {
                'formatted': code,
                'original_language': language,
                'detected_language': None,
                'formatter_used': None,
                'changed': False
            }
        
        detected_lang = None
        formatter_used = None
        
        # If no language provided, detect it
        if not language:
            detected_lang = self._detect_language_from_patterns(code)
            language = detected_lang
            
        formatted = self.format(code, language)
        
        # Determine which formatter was used based on the result
        if formatted != code:
            if self.prettier_available and language and language.lower() in [
                'javascript', 'js', 'jsx', 'typescript', 'ts', 'tsx', 
                'json', 'css', 'scss', 'less', 'html', 'yaml', 'yml'
            ]:
                formatter_used = 'prettier'
            elif language and language.lower() in ['python', 'py']:
                formatter_used = 'python_basic'
            elif language and language.lower() == 'sql':
                formatter_used = 'sql_basic'
            else:
                formatter_used = 'basic'
        
        return {
            'formatted': formatted,
            'original_language': language,
            'detected_language': detected_lang,
            'formatter_used': formatter_used,
            'changed': formatted != code
        }