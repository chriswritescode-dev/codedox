# Changelog

All notable changes to CodeDox will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.2.8

### Added

- **reStructuredText (RST) Support**: Complete RST document processing with intelligent code extraction
  - Support for `.. code-block::` directive with language specification
  - Support for `.. code::` and `.. sourcecode::` directives
  - Literal block extraction using `::` syntax
  - Automatic language detection from RST directives
  - Comprehensive test coverage with various RST formats
  - Integration with existing upload and processing pipeline

### Improved

- **Code Extraction Pipeline**: Enhanced to handle RST documents alongside existing formats

### Technical Details

- **RST Code Extraction**: Implemented `RSTCodeExtractor` class in `src/api/routes/upload_utils.py`
- **Supported RST Features**:
  - `.. code-block:: python` with language specification and options
  - `.. code:: javascript` for shorter syntax
  - `.. sourcecode:: ruby` for alternative directive format
  - Literal blocks using `::` syntax with preserved indentation
  - Automatic filtering of directive options and metadata
  - Context preservation around code blocks
- **Test Coverage**: Added comprehensive test suite in `tests/test_rst_extraction.py`
- **File Support**: RST files (.rst, .rest, .restx, .rtxt, .rstx) now fully supported in upload processing

## [0.2.7]

### Added

- **GitHub Repository Processing**: Direct cloning and processing of GitHub repositories
  - Clone entire repositories or specific folders
  - Support for private repositories with token authentication
  - Branch selection support
  - Include/exclude file patterns for selective processing
  - Automatic cleanup after processing
  - Source URL generation for each processed file
- **New CLI Command**: `upload-repo` command for GitHub repository processing
- **Comprehensive GitHub Documentation**: Added detailed documentation for GitHub features
- **Enhanced Search with Markdown Fallback**: Automatically searches documentation content when code snippet searches return limited results
- **Markdown Search with Highlighting**: Full-text search across markdown documentation with intelligent highlighting and auto-scroll to matches
- **Web UI Search Improvements**: Toggle between code-only and enhanced search modes in the UI
- **Comprehensive Documentation**: Added detailed feature documentation with screenshots

### Improved

- **Documentation Structure**: Better organization with dedicated GitHub processing section
- **Markdown Formatting**: Fixed list formatting issues for better mkdocs rendering
- **Code Quality**: Fixed import ordering, removed unused imports, and improved type hints throughout the codebase
- **Test Infrastructure**: Enhanced test fixtures and database cleanup procedures
- **Search Performance**: Optimized PostgreSQL full-text search with better indexing and query strategies
- **MCP Tools**: Improved error handling and response formatting for better AI assistant integration

### Fixed

- **Code Extraction**: Resolved issues with HTML code extraction and duplicate detection
- **Upload UI**: Fixed spacing and layout issues in the upload interface
- **Database Schema**: Cleaned up schema setup and migration handling

### Changed

- **Screenshot Organization**: Consolidated all screenshots into docs/screenshots directory for single source of truth
- **Search Defaults**: Changed default search behavior to use enhanced mode for better results

## [0.2.6]

### Added

- **Enhanced Search with Markdown Fallback**: Automatically searches documentation content when code snippet searches return limited results
- **Markdown Search with Highlighting**: Full-text search across markdown documentation with intelligent highlighting and auto-scroll to matches
- **Web UI Search Improvements**: Toggle between code-only and enhanced search modes in the UI
- **Comprehensive Documentation**: Added detailed feature documentation with screenshots

### Improved

- **Code Quality**: Fixed import ordering, removed unused imports, and improved type hints throughout the codebase
- **Test Infrastructure**: Enhanced test fixtures and database cleanup procedures
- **Search Performance**: Optimized PostgreSQL full-text search with better indexing and query strategies
- **MCP Tools**: Improved error handling and response formatting for better AI assistant integration

### Fixed

- **Code Extraction**: Resolved issues with HTML code extraction and duplicate detection
- **Upload UI**: Fixed spacing and layout issues in the upload interface
- **Database Schema**: Cleaned up schema setup and migration handling

### Changed

- **Screenshot Organization**: Consolidated all screenshots into docs/screenshots directory for single source of truth
- **Search Defaults**: Changed default search behavior to use enhanced mode for better results

## [0.2.5]

### Added

- Initial public release with core functionality
- Web crawling with depth control
- LLM-powered code extraction
- PostgreSQL full-text search
- MCP server integration
- React/TypeScript Web UI
- Upload support for markdown files
