# Context Extraction Enhancement Plan

## Overview
Enhance code block context extraction across all file types (Markdown, RST, HTML, GitHub repos) to provide rich, semantic context without relying on LLM for basic descriptions. Each file type should extract title, description, and relevant context while filtering out noise like navigation links, badges, and UI elements.

## Goals
1. **Consistency**: All file types use the same semantic extraction approach
2. **Quality**: Extract meaningful titles and descriptions from document structure
3. **Cleanliness**: Filter out navigation, links, badges, and other noise
4. **Modularity**: Clean, reusable extraction methods for each file type
5. **Performance**: Work well without LLM enhancement (though LLM can still improve)

## Current State Analysis

### File Types Currently Supported
1. **Markdown** (.md, .mdx) - `MarkdownCodeExtractor`
2. **ReStructuredText** (.rst) - `RSTCodeExtractor`  
3. **HTML** (crawled pages) - `HTMLCodeExtractor`
4. **GitHub Repos** - Uses file-type specific extractors

### Current Problems
- **Markdown/RST**: Just grab arbitrary characters before code (not semantic)
- **Inconsistent**: HTML has rich extraction, others don't
- **Noise**: Links, badges, navigation not filtered in Markdown/RST
- **No structure**: Markdown/RST don't detect headings or hierarchy

## Proposed Architecture

### Base Class Design
```python
class BaseCodeExtractor(ABC):
    """Abstract base class for all code extractors."""
    
    @abstractmethod
    def extract_blocks(self, content: str, source_url: str = None) -> list[ExtractedCodeBlock]:
        """Extract code blocks with semantic context."""
        pass
    
    @abstractmethod
    def find_preceding_heading(self, content: str, position: int) -> tuple[str, int]:
        """Find the nearest preceding heading."""
        pass
    
    @abstractmethod
    def extract_context_between(self, content: str, start: int, end: int) -> ExtractedContext:
        """Extract and clean context between two positions."""
        pass
    
    def filter_noise(self, text: str) -> str:
        """Remove links, badges, navigation elements."""
        pass
```

### Unified Data Model
```python
@dataclass
class ExtractedContext:
    """Semantic context for a code block."""
    title: str | None          # From nearest heading
    description: str | None     # Cleaned paragraphs/lists between heading and code
    raw_content: list[str]      # Original content lines (for debugging)
    hierarchy: list[str]        # Heading hierarchy (h1 > h2 > h3)
    
@dataclass
class ExtractedCodeBlock:
    """Unified code block with context."""
    code: str
    language: str | None
    context: ExtractedContext
    source_url: str | None
    line_start: int | None
    line_end: int | None
```

## Implementation Plan

### Phase 1: Base Infrastructure (Week 1)

#### 1.1 Create Base Extractor Class
**File**: `src/crawler/extractors/base.py`
- Abstract base class with common methods
- Shared noise filtering logic
- Common text cleaning utilities
- Context boundary detection

#### 1.2 Create Unified Data Models  
**File**: `src/crawler/extractors/models.py`
- `ExtractedContext` dataclass
- `ExtractedCodeBlock` dataclass
- Remove duplicate models across codebase

#### 1.3 Implement Shared Utilities
**File**: `src/crawler/extractors/utils.py`
- Link removal (preserve sentence flow)
- Badge/image reference removal
- Navigation element detection
- Text normalization

### Phase 2: Markdown Extractor Enhancement (Week 1)

#### 2.1 Enhance MarkdownCodeExtractor
**File**: `src/crawler/extractors/markdown.py`
```python
class MarkdownCodeExtractor(BaseCodeExtractor):
    def extract_blocks(self, content: str, source_url: str = None) -> list[ExtractedCodeBlock]:
        """Extract code blocks with full semantic context."""
        # 1. Find all code blocks (fenced and indented)
        # 2. For each block:
        #    - Find preceding heading
        #    - Extract content between heading and code
        #    - Filter noise (links, badges, etc.)
        #    - Build ExtractedCodeBlock with context
        
    def find_preceding_heading(self, lines: list[str], block_line: int) -> tuple[str, int]:
        """Find nearest heading before code block."""
        # Search backwards for:
        # - ATX headings (# ## ###)
        # - Setext headings (underlined)
        # Return heading text and line number
        
    def extract_context_between(self, lines: list[str], start: int, end: int) -> ExtractedContext:
        """Extract paragraphs, lists, blockquotes between positions."""
        # Collect content while:
        # - Preserving lists and blockquotes
        # - Removing links (keep text)
        # - Removing badges/images
        # - Filtering navigation
```

#### 2.2 Implement Markdown-Specific Filters
- Remove markdown links but keep text: `[text](url)` → `text`
- Remove image references: `![alt](url)` → removed
- Remove HTML comments: `<!-- comment -->` → removed
- Remove frontmatter metadata
- Clean badge patterns
- Remove footnote references

### Phase 3: RST Extractor Enhancement (Week 2)

#### 3.1 Enhance RSTCodeExtractor
**File**: `src/crawler/extractors/rst.py`
```python
class RSTCodeExtractor(BaseCodeExtractor):
    def find_preceding_heading(self, lines: list[str], block_line: int) -> tuple[str, int]:
        """Find RST headings (overlined/underlined)."""
        # Detect RST heading patterns:
        # - Underlined headings
        # - Overlined + underlined headings
        
    def extract_context_between(self, lines: list[str], start: int, end: int) -> ExtractedContext:
        """Extract RST directives, paragraphs, lists."""
        # Handle RST-specific:
        # - Directives (.. note::, .. warning::)
        # - Definition lists
        # - Field lists
        # - Inline markup
```

#### 3.2 RST-Specific Filters
- Remove RST references: `` `text <url>`_ `` → `text`
- Remove footnotes: `[#]_` → removed
- Clean directives that are navigation
- Preserve important directives (note, warning, tip)

### Phase 4: HTML Extractor Refactoring (Week 2)

#### 4.1 Refactor HTMLCodeExtractor to Use Base Class
**File**: `src/crawler/extractors/html.py`
- Inherit from `BaseCodeExtractor`
- Adapt existing logic to new data model
- Add missing patterns (textarea, figure, custom elements)

#### 4.2 Enhance HTML Pattern Detection
- Add support for `<textarea>` code editors
- Detect `<figure>` with code
- Support custom web components
- Handle tables with code cells

### Phase 5: Integration with Upload Pipeline (Week 3)

#### 5.1 Update Upload Processor
**File**: `src/api/routes/upload_utils.py`
- Use new unified extractors
- Remove duplicate extraction logic
- Consistent handling across file types

#### 5.2 Update GitHub Processor
**File**: `src/crawler/github_processor.py`
- Use appropriate extractor based on file extension
- Apply consistent context extraction
- Handle mixed file types in repos

#### 5.3 Database Integration
- Ensure ExtractedContext maps to database fields
- Update `code_snippets` table if needed
- Preserve backward compatibility

### Phase 6: Testing & Validation (Week 3)

#### 6.1 Unit Tests for Each Extractor
**Files**: `tests/test_extractors/`
- Test heading detection
- Test context extraction
- Test noise filtering
- Test edge cases

#### 6.2 Integration Tests
- Test full upload pipeline
- Test GitHub repo processing
- Test crawled HTML pages
- Verify database storage

#### 6.3 Quality Validation
- Compare before/after extraction quality
- Verify no data loss
- Check context completeness
- Validate noise removal

## File Structure

```
src/crawler/extractors/
├── __init__.py
├── base.py          # BaseCodeExtractor abstract class
├── models.py        # ExtractedContext, ExtractedCodeBlock
├── utils.py         # Shared utilities (filtering, cleaning)
├── markdown.py      # MarkdownCodeExtractor
├── rst.py          # RSTCodeExtractor  
├── html.py         # HTMLCodeExtractor
└── factory.py      # Factory to create appropriate extractor

tests/test_extractors/
├── __init__.py
├── test_base.py
├── test_markdown.py
├── test_rst.py
├── test_html.py
├── test_utils.py
└── fixtures/       # Sample files for testing
```

## Migration Strategy

1. **Phase 1**: Implement new extractors alongside existing code
2. **Phase 2**: Add feature flag to switch between old/new
3. **Phase 3**: Gradually migrate endpoints to new extractors
4. **Phase 4**: Remove old extraction code after validation

## Success Metrics

1. **Context Quality**
   - 90%+ of code blocks have meaningful titles
   - 80%+ have useful descriptions without LLM
   - <5% contain navigation/badge noise

2. **Performance**
   - Extraction time remains under 100ms per file
   - Memory usage stays constant
   - No regression in throughput

3. **Compatibility**
   - All existing tests pass
   - Database schema compatible
   - API responses unchanged

## Example: Markdown Extraction (Before vs After)

### Before (Current)
```python
{
    'code': 'const api = new API()',
    'language': 'javascript',
    'context': '...last 300 chars...configure your API client:\n\n```javascript'
}
```

### After (Enhanced)
```python
{
    'code': 'const api = new API()',
    'language': 'javascript', 
    'context': {
        'title': 'API Client Configuration',
        'description': 'To connect to the API, you need to initialize the client with your credentials. The client handles authentication and request signing automatically.',
        'hierarchy': ['Getting Started', 'Setup', 'API Client Configuration']
    }
}
```

## Risk Mitigation

1. **Data Loss**: Keep original extraction as fallback
2. **Performance**: Profile and optimize hot paths
3. **Compatibility**: Extensive testing before migration
4. **Complexity**: Incremental implementation and testing

## Timeline

- **Week 1**: Base infrastructure + Markdown extractor
- **Week 2**: RST extractor + HTML refactoring
- **Week 3**: Integration + Testing
- **Week 4**: Deployment + Monitoring

## Next Steps

1. Review and approve plan
2. Create feature branch
3. Implement base infrastructure
4. Begin with Markdown extractor (most common format)
5. Iterate based on testing results