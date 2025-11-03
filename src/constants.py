"""CodeDox constants and version information."""

__version__ = "0.3.5"
__author__ = "Chris Scott"
__description__ = "Documentation Code Extraction and Search System"
__app_name__ = "CodeDox"
__mcp_server_name__ = "codedox-mcp"

# File type configuration - single source of truth
SUPPORTED_FILE_TYPES = {
    'markdown': {
        'extensions': ('.md', '.markdown', '.mdx', '.mdown', '.mkd', '.mdwn'),
        'content_type': 'markdown',
        'description': 'Markdown files'
    },
    'restructuredtext': {
        'extensions': ('.rst', '.rest', '.restx', '.rtxt', '.rstx'),
        'content_type': 'restructuredtext',
        'description': 'reStructuredText files'
    },
    'html': {
        'extensions': ('.html', '.htm'),
        'content_type': 'html',
        'description': 'HTML files'
    },
    'text': {
        'extensions': ('.txt',),
        'content_type': 'text',
        'description': 'Plain text files'
    }
}

# Helper functions for file type operations
def get_all_supported_extensions():
    """Get a flat tuple of all supported file extensions."""
    extensions = []
    for file_type in SUPPORTED_FILE_TYPES.values():
        extensions.extend(file_type['extensions'])
    return tuple(extensions)

def get_content_type_for_extension(file_path):
    """Get the content type for a given file extension."""
    if isinstance(file_path, str):
        file_path_lower = file_path.lower()
        for file_type in SUPPORTED_FILE_TYPES.values():
            for ext in file_type['extensions']:
                if file_path_lower.endswith(ext):
                    return file_type['content_type']
    return None

# Pre-computed values for performance
ALL_SUPPORTED_EXTENSIONS = get_all_supported_extensions()

# WebSocket message types - single source of truth
class WebSocketMessageType:
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"
    REGENERATION_PROGRESS = "regeneration_progress"
    REGENERATION_COMPLETE = "regeneration_complete"
    REGENERATION_ERROR = "regeneration_error"
    CRAWL_UPDATE = "crawl_update"
    CRAWL_PROGRESS = "crawl_progress"
    CRAWL_COMPLETE = "crawl_complete"
