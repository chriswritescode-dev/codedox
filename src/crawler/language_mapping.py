"""Shared language mapping module for consistent language normalization across the codebase."""


# Language normalization mapping
LANGUAGE_ALIASES: dict[str, str] = {
    # JavaScript variants
    'js': 'javascript',
    # Keep JSX separate for proper formatting
    # 'jsx': 'jsx',  # Don't normalize jsx - keep it for formatter
    'mjs': 'javascript',
    'cjs': 'javascript',

    # TypeScript variants
    'ts': 'typescript',
    # Keep TSX separate for proper formatting
    # 'tsx': 'tsx',  # Don't normalize tsx - keep it for formatter

    # Python variants
    'py': 'python',
    'py3': 'python',
    'python3': 'python',
    'pyw': 'python',
    'pyx': 'python',
    'pxd': 'python',
    'pyi': 'python',

    # Shell variants
    'sh': 'bash',
    'shell': 'bash',
    'zsh': 'bash',
    'fish': 'bash',
    'shellscript': 'shell',

    # YAML variants
    'yml': 'yaml',

    # C++ variants
    'c++': 'cpp',
    'cxx': 'cpp',
    'cc': 'cpp',
    'hpp': 'cpp',
    'hxx': 'cpp',
    'hh': 'cpp',

    # C# variants
    'c#': 'csharp',
    'cs': 'csharp',

    # Objective-C variants
    'objective-c': 'objc',
    'objectivec': 'objc',
    'm': 'objc',
    'mm': 'objc',

    # Go variants
    'golang': 'go',

    # HTML/XML variants
    'htm': 'html',
    'xhtml': 'html',
    'xml': 'xml',

    # Ruby variants
    'rb': 'ruby',

    # Perl variants
    'pl': 'perl',

    # PowerShell variants
    'ps1': 'powershell',
    'psm1': 'powershell',
    'psd1': 'powershell',

    # Kotlin variants
    'kt': 'kotlin',
    'kts': 'kotlin',

    # Rust variants
    'rs': 'rust',

    # Markdown variants
    'md': 'markdown',
    'mdx': 'mdx',

    # LaTeX variants
    'tex': 'latex',

    # R language
    'r': 'r',
    'R': 'r',

    # SQL variants
    'sql': 'sql',
    'postgresql': 'sql',
    'mysql': 'sql',
    'sqlite': 'sql',
    'psql': 'sql',

    # Batch/CMD variants
    'bat': 'batch',
    'cmd': 'batch',

    # F# variants
    'fs': 'fsharp',

    # VB.NET variants
    'vb': 'vbnet',

    # Julia variants
    'jl': 'julia',

    # Elixir variants
    'ex': 'elixir',
    'exs': 'elixir',

    # Erlang variants
    'erl': 'erlang',
    'hrl': 'erlang',

    # Nim variants
    'nim': 'nim',
    'nims': 'nim',

    # Pascal variants
    'pas': 'pascal',
    'pp': 'pascal',

    # Assembly variants
    'asm': 'asm',
    's': 'asm',

    # Config files
    'conf': 'conf',
    'cfg': 'ini',
    'ini': 'ini',
    'toml': 'toml',

    # React/Next.js specific mappings
    'react': 'jsx',
    'react.js': 'jsx',
    'reactjs': 'jsx',
    'next': 'jsx',
    'next.js': 'jsx',
    'nextjs': 'jsx',

    # Others
    'dart': 'dart',
    'lua': 'lua',
    'php': 'php',
    'swift': 'swift',
    'scala': 'scala',
    'clj': 'clojure',
    'cljs': 'clojure',
    'groovy': 'groovy',
    'java': 'java',
    'zig': 'zig',
    'rst': 'rst',
    'adoc': 'asciidoc',
    'nginx': 'nginx',
    'htaccess': 'apache',
    'dockerfile': 'dockerfile',
    'makefile': 'makefile',
    'env': 'env',
    'gitignore': 'gitignore',
    'dockerignore': 'dockerignore',
}

# File extension to language mapping
FILE_EXTENSION_MAP: dict[str, str] = {
    # JavaScript/TypeScript
    'js': 'javascript',
    'jsx': 'javascript',
    'mjs': 'javascript',
    'cjs': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',

    # Python
    'py': 'python',
    'pyw': 'python',
    'pyx': 'python',
    'pxd': 'python',
    'pyi': 'python',

    # Web
    'html': 'html',
    'htm': 'html',
    'xhtml': 'html',
    'xml': 'xml',
    'css': 'css',
    'scss': 'scss',
    'sass': 'sass',
    'less': 'less',

    # Data formats
    'json': 'json',
    'yaml': 'yaml',
    'yml': 'yaml',
    'toml': 'toml',
    'ini': 'ini',
    'cfg': 'ini',
    'conf': 'conf',

    # Shell
    'sh': 'shell',
    'bash': 'bash',
    'zsh': 'zsh',
    'fish': 'fish',
    'ps1': 'powershell',
    'psm1': 'powershell',
    'psd1': 'powershell',
    'bat': 'batch',
    'cmd': 'batch',

    # Systems languages
    'c': 'c',
    'h': 'c',
    'cpp': 'cpp',
    'cxx': 'cpp',
    'cc': 'cpp',
    'hpp': 'cpp',
    'hxx': 'cpp',
    'hh': 'cpp',
    'rs': 'rust',
    'go': 'go',
    'zig': 'zig',

    # JVM languages
    'java': 'java',
    'kt': 'kotlin',
    'kts': 'kotlin',
    'scala': 'scala',
    'clj': 'clojure',
    'cljs': 'clojure',
    'groovy': 'groovy',

    # .NET languages
    'cs': 'csharp',
    'fs': 'fsharp',
    'vb': 'vbnet',

    # Mobile
    'swift': 'swift',
    'm': 'objc',
    'mm': 'objc',

    # Database
    'sql': 'sql',
    'psql': 'sql',
    'mysql': 'sql',

    # Others
    'rb': 'ruby',
    'php': 'php',
    'pl': 'perl',
    'lua': 'lua',
    'r': 'r',
    'R': 'r',
    'jl': 'julia',
    'ex': 'elixir',
    'exs': 'elixir',
    'erl': 'erlang',
    'hrl': 'erlang',
    'nim': 'nim',
    'nims': 'nim',
    'dart': 'dart',
    'pas': 'pascal',
    'pp': 'pascal',
    'asm': 'asm',
    's': 'asm',

    # Documentation
    'md': 'markdown',
    'mdx': 'mdx',
    'rst': 'rst',
    'tex': 'latex',
    'adoc': 'asciidoc',

    # Config files
    'nginx': 'nginx',
    'htaccess': 'apache',
}

# Special filenames without extensions
SPECIAL_FILENAMES: dict[str, str] = {
    'dockerfile': 'dockerfile',
    'makefile': 'makefile',
    'gemfile': 'ruby',
    'rakefile': 'ruby',
    'gulpfile': 'javascript',
    'gruntfile': 'javascript',
    'vagrantfile': 'ruby',
    'jenkinsfile': 'groovy',
    'podfile': 'ruby',
    'cartfile': 'swift',
    'appfile': 'ruby',
    'fastfile': 'ruby',
    'snapfile': 'ruby',
    'scanfile': 'ruby',
    '.gitignore': 'gitignore',
    '.dockerignore': 'dockerignore',
    '.env': 'env',
    '.babelrc': 'json',
    '.eslintrc': 'json',
    '.prettierrc': 'json',
    'tsconfig.json': 'json',
    'package.json': 'json',
    'composer.json': 'json',
    'cargo.toml': 'toml',
    'pyproject.toml': 'toml',
    'go.mod': 'go',
    'go.sum': 'go',
    'requirements.txt': 'text',
    'readme.md': 'markdown',
    'changelog.md': 'markdown',
}


def normalize_language(language: str) -> str:
    """
    Normalize a language name to a standard format.
    
    Args:
        language: The language name to normalize
        
    Returns:
        The normalized language name
    """
    if not language:
        return 'text'

    lang_lower = language.lower().strip()
    return LANGUAGE_ALIASES.get(lang_lower, lang_lower)


def get_language_from_extension(extension: str) -> str | None:
    """
    Get language from file extension.
    
    Args:
        extension: File extension (without dot)
        
    Returns:
        Language name or None if not found
    """
    if not extension:
        return None

    ext_lower = extension.lower().strip()
    return FILE_EXTENSION_MAP.get(ext_lower)


def get_language_from_filename(filename: str) -> str | None:
    """
    Determine language from filename.
    
    Args:
        filename: The filename to analyze
        
    Returns:
        Language name or None if not found
    """
    if not filename:
        return None

    filename_lower = filename.lower().strip()

    # Check special filenames first
    if filename_lower in SPECIAL_FILENAMES:
        return SPECIAL_FILENAMES[filename_lower]

    # Extract extension
    import os
    _, ext = os.path.splitext(filename)
    if ext and ext.startswith('.'):
        ext = ext[1:]
        return get_language_from_extension(ext)

    return None
