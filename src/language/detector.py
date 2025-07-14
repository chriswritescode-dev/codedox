"""Language detection using tree-sitter for high accuracy."""

import re
import logging
from typing import Dict, List, Optional, NamedTuple
from pathlib import Path

try:
    from tree_sitter import Language, Parser
    import tree_sitter_python
    import tree_sitter_javascript
    import tree_sitter_typescript
    import tree_sitter_java
    import tree_sitter_go
    import tree_sitter_rust
    import tree_sitter_cpp
    import tree_sitter_c_sharp
    import tree_sitter_ruby
    import tree_sitter_php
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logging.warning("tree-sitter not available. Language detection accuracy will be reduced.")

logger = logging.getLogger(__name__)


class DetectionResult(NamedTuple):
    """Result of language detection."""
    language: str
    confidence: float
    method: str  # 'tree-sitter', 'pattern', 'extension', 'fallback'
    details: Optional[Dict] = None


class LanguageDetector:
    """Detects programming language of code snippets using multiple methods."""

    def __init__(self):
        """Initialize the language detector."""
        self.parsers = {}
        self.language_patterns = {}
        self._init_tree_sitter()
        self._init_patterns()

    def _init_tree_sitter(self):
        """Initialize tree-sitter parsers for supported languages."""
        if not TREE_SITTER_AVAILABLE:
            return

        language_modules = {
            'python': tree_sitter_python,
            'javascript': tree_sitter_javascript,
            'typescript': tree_sitter_typescript,
            'java': tree_sitter_java,
            'go': tree_sitter_go,
            'rust': tree_sitter_rust,
            'cpp': tree_sitter_cpp,
            'c_sharp': tree_sitter_c_sharp,
            'ruby': tree_sitter_ruby,
            'php': tree_sitter_php,
        }

        for lang_name, module in language_modules.items():
            try:
                parser = Parser()
                # Handle different API versions
                if hasattr(module, 'language'):
                    lang = module.language()
                elif hasattr(module, 'LANGUAGE'):
                    lang = module.LANGUAGE

                # Wrap PyCapsule in Language object if needed
                if hasattr(Language, 'build_library'):
                    # Older API
                    parser.set_language(Language(lang))
                else:
                    # Newer API
                    from tree_sitter import Language as TSLanguage
                    parser.language = TSLanguage(lang)

                self.parsers[lang_name] = parser
                logger.debug(f"Initialized tree-sitter parser for {lang_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize {lang_name} parser: {e}")

    def _init_patterns(self):
        """Initialize regex patterns for fallback language detection."""
        self.language_patterns = {
            'python': {
                'keywords': r'\b(def|class|import|from|if|elif|else|for|while|with|return|yield|lambda|try|except|finally|raise|assert|pass|break|continue|async|await)\b',
                'syntax': r'(:\s*$|^[ \t]*(def|class)\s+\w+|^import\s+|^from\s+.+\s+import)',
                'extensions': ['.py', '.pyw'],
                'shebang': r'^#!.*python'
            },
            'javascript': {
                'keywords': r'\b(function|var|let|const|if|else|for|while|do|switch|case|break|continue|return|throw|try|catch|finally|new|this|typeof|instanceof|delete|void|async|await|class|extends|export|import|default)\b',
                'syntax': r'(function\s*\w*\s*\([^)]*\)\s*{|=>\s*{|const\s+\w+\s*=|let\s+\w+\s*=|var\s+\w+\s*=)',
                'extensions': ['.js', '.mjs', '.jsx'],
                'shebang': r'^#!.*node'
            },
            'typescript': {
                'keywords': r'\b(interface|type|enum|namespace|module|declare|implements|private|public|protected|readonly|abstract|static)\b',
                'syntax': r'(:\s*(string|number|boolean|any|void|never)|interface\s+\w+|type\s+\w+\s*=)',
                'extensions': ['.ts', '.tsx', '.d.ts'],
                'shebang': None
            },
            'java': {
                'keywords': r'\b(public|private|protected|static|final|abstract|synchronized|volatile|transient|native|strictfp|class|interface|enum|extends|implements|import|package|new|this|super|void|int|long|short|byte|float|double|char|boolean)\b',
                'syntax': r'(public\s+class|private\s+class|protected\s+class|public\s+static\s+void\s+main|@\w+)',
                'extensions': ['.java'],
                'shebang': None
            },
            'go': {
                'keywords': r'\b(package|import|func|var|const|type|struct|interface|map|chan|go|defer|if|else|for|range|switch|case|default|break|continue|return|fallthrough|select)\b',
                'syntax': r'(package\s+\w+|func\s+\w+|:=|<-)',
                'extensions': ['.go'],
                'shebang': None
            },
            'rust': {
                'keywords': r'\b(fn|let|mut|const|static|struct|enum|trait|impl|use|mod|pub|priv|crate|self|super|where|async|await|dyn|ref|move|box|unsafe|extern|type|match|if|else|for|while|loop|break|continue|return)\b',
                'syntax': r'(fn\s+\w+|let\s+(mut\s+)?\w+|impl\s+|use\s+|->)',
                'extensions': ['.rs'],
                'shebang': None
            },
            'cpp': {
                'keywords': r'\b(auto|break|case|char|const|continue|default|do|double|else|enum|extern|float|for|goto|if|int|long|register|return|short|signed|sizeof|static|struct|switch|typedef|union|unsigned|void|volatile|while|class|namespace|template|public|private|protected|friend|virtual|override|operator|new|delete|this|try|catch|throw|using|typename|bool|true|false|nullptr)\b',
                'syntax': r'(#include\s*[<"]|using\s+namespace|::|->|std::)',
                'extensions': ['.cpp', '.cc', '.cxx', '.c++', '.hpp', '.h', '.hh'],
                'shebang': None
            },
            'c': {
                'keywords': r'\b(auto|break|case|char|const|continue|default|do|double|else|enum|extern|float|for|goto|if|int|long|register|return|short|signed|sizeof|static|struct|switch|typedef|union|unsigned|void|volatile|while)\b',
                'syntax': r'(#include\s*[<"]|#define\s+|->)',
                'extensions': ['.c', '.h'],
                'shebang': None
            },
            'c_sharp': {
                'keywords': r'\b(abstract|as|base|bool|break|byte|case|catch|char|checked|class|const|continue|decimal|default|delegate|do|double|else|enum|event|explicit|extern|false|finally|fixed|float|for|foreach|goto|if|implicit|in|int|interface|internal|is|lock|long|namespace|new|null|object|operator|out|override|params|private|protected|public|readonly|ref|return|sbyte|sealed|short|sizeof|stackalloc|static|string|struct|switch|this|throw|true|try|typeof|uint|ulong|unchecked|unsafe|ushort|using|virtual|void|volatile|while|async|await|dynamic|var|yield)\b',
                'syntax': r'(using\s+System|namespace\s+|class\s+\w+|public\s+class)',
                'extensions': ['.cs'],
                'shebang': None
            },
            'ruby': {
                'keywords': r'\b(BEGIN|END|alias|and|begin|break|case|class|def|defined|do|else|elsif|end|ensure|false|for|if|in|module|next|nil|not|or|redo|rescue|retry|return|self|super|then|true|undef|unless|until|when|while|yield|require|include|extend|attr_reader|attr_writer|attr_accessor)\b',
                'syntax': r'(def\s+\w+|class\s+\w+|module\s+\w+|require\s+[\'"]|::\w+|@\w+)',
                'extensions': ['.rb'],
                'shebang': r'^#!.*ruby'
            },
            'php': {
                'keywords': r'\b(abstract|and|array|as|break|callable|case|catch|class|clone|const|continue|declare|default|die|do|echo|else|elseif|empty|enddeclare|endfor|endforeach|endif|endswitch|endwhile|eval|exit|extends|final|finally|for|foreach|function|global|goto|if|implements|include|include_once|instanceof|insteadof|interface|isset|list|namespace|new|or|print|private|protected|public|require|require_once|return|static|switch|throw|trait|try|unset|use|var|while|xor|yield)\b',
                'syntax': r'(<\?php|\$\w+|->|=>|function\s+\w+)',
                'extensions': ['.php', '.phtml'],
                'shebang': r'^#!.*php'
            },
            'sql': {
                'keywords': r'\b(SELECT|FROM|WHERE|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|DROP|ALTER|INDEX|VIEW|TRIGGER|PROCEDURE|FUNCTION|DATABASE|SCHEMA|GRANT|REVOKE|COMMIT|ROLLBACK|BEGIN|END|CASE|WHEN|THEN|ELSE|AND|OR|NOT|NULL|IS|IN|EXISTS|BETWEEN|LIKE|ORDER|BY|GROUP|HAVING|UNION|JOIN|INNER|LEFT|RIGHT|OUTER|ON|AS|DISTINCT|COUNT|SUM|AVG|MIN|MAX)\b',
                'syntax': r'(SELECT\s+.+\s+FROM|INSERT\s+INTO|UPDATE\s+.+\s+SET|CREATE\s+TABLE)',
                'extensions': ['.sql'],
                'shebang': None
            },
            'bash': {
                'keywords': r'\b(if|then|else|elif|fi|for|while|do|done|case|esac|function|return|break|continue|exit|export|source|alias|unset|shift|cd|ls|echo|printf|read|test)\b',
                'syntax': r'(#!/bin/(bash|sh)|^\s*\w+\(\)\s*{|\$\w+|\$\{|\$\()',
                'extensions': ['.sh', '.bash'],
                'shebang': r'^#!.*(bash|sh)'
            }
        }

    def detect(self, code: str, filename: Optional[str] = None) -> DetectionResult:
        """Detect the programming language of the given code.
        
        Args:
            code: The code snippet to analyze
            filename: Optional filename with extension for hints
            
        Returns:
            DetectionResult with detected language and confidence
        """
        if not code or not code.strip():
            return DetectionResult('unknown', 0.0, 'empty')

        # Try tree-sitter first (most accurate)
        if TREE_SITTER_AVAILABLE and self.parsers:
            result = self._detect_with_tree_sitter(code)
            if result.confidence >= 0.8:
                return result

        # Try extension-based detection
        if filename:
            result = self._detect_by_extension(filename)
            if result.confidence >= 0.9:
                return result

        # Try pattern-based detection
        result = self._detect_by_patterns(code)
        if result.confidence >= 0.7:
            return result

        # Return best guess or unknown
        return DetectionResult('unknown', 0.0, 'fallback')

    def _detect_with_tree_sitter(self, code: str) -> DetectionResult:
        """Use tree-sitter parsers to detect language."""
        best_language = None
        best_score = 0.0

        code_bytes = code.encode('utf-8')

        for language, parser in self.parsers.items():
            try:
                tree = parser.parse(code_bytes)
                root = tree.root_node

                # Calculate score based on parsing success
                error_count = self._count_errors(root)
                total_nodes = self._count_nodes(root)

                if total_nodes > 0:
                    score = 1.0 - (error_count / total_nodes)

                    # Bonus for no errors
                    if error_count == 0 and total_nodes > 10:
                        score = min(1.0, score + 0.1)

                    if score > best_score:
                        best_score = score
                        best_language = language

            except Exception as e:
                logger.debug(f"Tree-sitter parsing failed for {language}: {e}")
                continue

        if best_language and best_score >= 0.8:
            # Map tree-sitter names to our standard names
            language_map = {
                'c_sharp': 'csharp',
                'cpp': 'cpp',
                'javascript': 'javascript',
                'typescript': 'typescript'
            }
            mapped_language = language_map.get(best_language, best_language)

            return DetectionResult(
                mapped_language, 
                best_score, 
                'tree-sitter',
                {'error_rate': 1.0 - best_score}
            )

        return DetectionResult('unknown', 0.0, 'tree-sitter')

    def _count_errors(self, node: 'Node') -> int:
        """Count error nodes in the parse tree."""
        if node.type == 'ERROR' or node.is_missing:
            return 1

        count = 0
        for child in node.children:
            count += self._count_errors(child)
        return count

    def _count_nodes(self, node: 'Node') -> int:
        """Count total nodes in the parse tree."""
        count = 1
        for child in node.children:
            count += self._count_nodes(child)
        return count

    def _detect_by_extension(self, filename: str) -> DetectionResult:
        """Detect language by file extension."""
        path = Path(filename)
        ext = path.suffix.lower()

        for language, patterns in self.language_patterns.items():
            if 'extensions' in patterns and ext in patterns['extensions']:
                return DetectionResult(language, 0.95, 'extension', {'extension': ext})

        return DetectionResult('unknown', 0.0, 'extension')

    def _detect_by_patterns(self, code: str) -> DetectionResult:
        """Detect language using regex patterns."""
        scores = {}

        # Check for shebang
        first_line = code.split('\n')[0] if '\n' in code else code
        for language, patterns in self.language_patterns.items():
            if patterns.get('shebang') and re.match(patterns['shebang'], first_line):
                return DetectionResult(language, 0.9, 'pattern', {'method': 'shebang'})

        # Score each language based on pattern matches
        for language, patterns in self.language_patterns.items():
            score = 0.0
            matches = {}

            # Check keywords
            if 'keywords' in patterns:
                keyword_matches = len(re.findall(patterns['keywords'], code, re.IGNORECASE))
                if keyword_matches > 0:
                    score += min(0.5, keyword_matches * 0.05)
                    matches['keywords'] = keyword_matches

            # Check syntax patterns
            if 'syntax' in patterns:
                syntax_matches = len(re.findall(patterns['syntax'], code, re.MULTILINE))
                if syntax_matches > 0:
                    score += min(0.5, syntax_matches * 0.1)
                    matches['syntax'] = syntax_matches

            if score > 0:
                scores[language] = (score, matches)

        if scores:
            best_language = max(scores.keys(), key=lambda k: scores[k][0])
            best_score, matches = scores[best_language]

            # Normalize score
            confidence = min(0.95, best_score)

            return DetectionResult(
                best_language,
                confidence,
                'pattern',
                {'matches': matches}
            )

        return DetectionResult('unknown', 0.0, 'pattern')

    def extract_functions(self, code: str, language: str) -> List[str]:
        """Extract function names from code."""
        functions = []

        # Language-specific function patterns
        patterns = {
            'python': r'def\s+(\w+)\s*\(',
            'javascript': r'function\s+(\w+)\s*\(|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[^=]+)\s*=>',
            'typescript': r'function\s+(\w+)\s*\(|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[^=]+)\s*=>',
            'java': r'(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\(',
            'go': r'func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(',
            'rust': r'fn\s+(\w+)\s*[<(]',
            'cpp': r'(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*(?:const\s*)?(?:override\s*)?{',
            'c': r'(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*{',
            'csharp': r'(?:public|private|protected|internal|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\(',
            'ruby': r'def\s+(\w+)',
            'php': r'function\s+(\w+)\s*\(',
        }

        pattern = patterns.get(language)
        if pattern:
            matches = re.findall(pattern, code)
            for match in matches:
                if isinstance(match, tuple):
                    functions.extend([m for m in match if m])
                else:
                    functions.append(match)

        return list(set(functions))  # Remove duplicates

    def extract_imports(self, code: str, language: str) -> List[str]:
        """Extract import statements from code."""
        imports = []

        # Language-specific import patterns
        patterns = {
            'python': [
                r'import\s+([\w.]+)',
                r'from\s+([\w.]+)\s+import'
            ],
            'javascript': [
                r'import\s+.+\s+from\s+[\'"](.+)[\'"]',
                r'require\([\'"](.+)[\'"]\)'
            ],
            'typescript': [
                r'import\s+.+\s+from\s+[\'"](.+)[\'"]',
                r'require\([\'"](.+)[\'"]\)'
            ],
            'java': [
                r'import\s+([\w.]+);'
            ],
            'go': [
                r'import\s+"([^"]+)"',
                r'import\s+\(\s*"([^"]+)"'
            ],
            'rust': [
                r'use\s+([\w:]+);'
            ],
            'cpp': [
                r'#include\s*[<"]([^>"]+)[>"]'
            ],
            'c': [
                r'#include\s*[<"]([^>"]+)[>"]'
            ],
            'csharp': [
                r'using\s+([\w.]+);'
            ],
            'ruby': [
                r'require\s+[\'"]([^\'"]]+)[\'"]',
                r'require_relative\s+[\'"]([^\'"]]+)[\'"]'
            ],
            'php': [
                r'require\s+[\'"]([^\'"]]+)[\'"]',
                r'include\s+[\'"]([^\'"]]+)[\'"]',
                r'use\s+([\w\\]+);'
            ],
        }

        language_patterns = patterns.get(language, [])
        for pattern in language_patterns:
            matches = re.findall(pattern, code)
            imports.extend(matches)

        return list(set(imports))  # Remove duplicates
