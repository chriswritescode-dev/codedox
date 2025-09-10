# Changelog

All notable changes to CodeDox will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.3.2 - 2025-09-10

### Added
- get_snippet() tool for direct snippet retrieval with token management
- Token utilities for smart truncation and chunking of large content
- Validation utilities for input sanitization and security

### Improved
- Search engine with better pagination and markdown fallback logic
- Documentation updated to emphasize HTTP MCP endpoints and enhanced workflows

## 0.3.1 - 2025-09-09

### 🔧 Performance Improvements

**Large Document Processing**
- Made code extractors async with batch processing to prevent blocking
- Added batch_size parameter to control processing intervals (default: 5)
- Optimized HTML element traversal for better performance with large documents

**Code Extraction Engine**
- Updated all extractors (HTML, Markdown, RST) to use async/await pattern
- Added performance monitoring for large document processing
- Improved memory efficiency during code block extraction
- Enhanced error handling for timeout scenarios

## 0.3.0 - 2025-09-07

### 🚀 Major Features & Improvements

**Unified Code Extraction System**
- Complete refactor to a unified extraction architecture with factory pattern
- New `ExtractedCodeBlock` model with semantic `ExtractedContext` for better code understanding
- Consolidated HTML, Markdown, and RST extraction into specialized extractors with shared base class
- Improved extraction rules: multi-line blocks always extracted, single-line with 3+ significant words
- Better handling of unclosed markdown fence blocks and HTML button elements

**Source-Scoped Duplicate Detection**
- **Breaking Change**: Duplicate detection now scoped to individual sources instead of global
- Same code snippets can exist across different documentation sources
- New composite unique constraint (document_id, code_hash) replaces global code_hash constraint
- Automatic database migration system with migration 008_remove_code_hash_unique
- Shared utility function `find_duplicate_snippet_in_source()` for consistent duplicate checking

**Enhanced Frontend Experience**
- Refactored DocumentDetail page with custom `useDocumentDetail` hook
- Improved search UX with better focus management and search result counts
- Enhanced language filtering with count display in dropdown

### 🔧 Technical Improvements

**Extraction Engine**
- Removed legacy SimpleCodeBlock and html_code_extractor.py systems
- Factory pattern for creating format-specific extractors
- Better context-aware HTML extraction with heading detection
- Improved title extraction combining section headings with page titles
- Enhanced RST support with better literal block detection

**Database & Migrations**
- Automatic migration application on app startup
- New migration check system that applies pending migrations automatically
- Updated SQLAlchemy models for new constraint structure

**Code Quality**
- Removed redundant wrapper functions and adapter layers
- Cleaned up 34 files with 2,805 additions and 1,921 deletions in main refactor
- Migrated all 269+ tests to new extraction API
- Added comprehensive test coverage for new extraction system

### 🐛 Bug Fixes

- Fixed UploadProcessor missing heartbeat tracking methods
- Removed pygame-specific corruption handling from RST extractor
- Fixed retry failed pages to maintain original source association

### 📝 Developer Experience

- Better extraction rules with semantic understanding
- Improved error handling and edge case coverage
- Enhanced test suite with dedicated extractor tests
- More consistent API across extraction formats

### 🔄 Migration Notes

**Automatic Migrations**: The database schema will be automatically updated when starting the application. The migration adds source-scoped duplicate detection.

**Breaking Changes**: 
- Code extraction now uses `ExtractedCodeBlock` model instead of dictionary-based approach
- Duplicate detection API changed from global to source-scoped
- Removed `container_type` field from extraction models

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
