# Upload and Repository Update Functionality Plan

## Overview

This plan outlines the implementation of update functionality for uploaded content and GitHub repository content, similar to the existing crawl update feature implemented in commit `0ff3c26`.

## Current State Analysis

### Existing Update Crawl Implementation
- **API Endpoint**: `PATCH /sources/{source_id}/update-crawl` (sources.py:1195-1284)
- **Frontend**: `NewCrawlDialog` with dual modes (create/update)
- **Functionality**: Differential crawling with new URL patterns, exclusions, and settings updates
- **Metadata Tracking**: Stores update metadata and change summaries

### Current Limitations
- **Upload Jobs**: Explicitly blocked from updates (sources.py:1202-1203)
- **GitHub Repos**: Treated as uploads, no dedicated update mechanism
- **Content Source Types**: Only crawl jobs support updates

## Implementation Plan

### Phase 1: Database Schema Updates

#### 1.1 UploadJob Model Enhancements
```python
# Add to UploadJob model
source_url = Column(String, nullable=True)  # GitHub repo URL
update_history = Column(JSONB, default=[])   # Track update history
last_updated_at = Column(DateTime)          # Last update timestamp
content_hashes = Column(JSONB, default={})  # File content hashes for comparison
```

#### 1.2 Database Migrations
- Create migration script for new fields
- Add indexes for efficient update queries
- Update constraints and triggers

### Phase 2: Backend API Changes

#### 2.1 Upload Job Updates
**Endpoint**: `PATCH /sources/{source_id}/update-upload`

**Functionality**:
- Replace uploaded files with new versions
- Preserve existing snippets for unchanged content (using content hash comparison)
- Add new snippets for new/changed content
- Delete snippets for removed content
- Update version and metadata
- Track update history

**Request Model**:
```python
class UpdateUploadRequest(BaseModel):
    files: list[dict] = Field(..., description="New files to upload")
    version: str | None = Field(None, description="New version")
    replace_all: bool = Field(False, description="Replace all existing files")
    preserve_unchanged: bool = Field(True, description="Keep snippets for unchanged content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Update metadata")
```

#### 2.2 GitHub Repository Updates
**Endpoint**: `PATCH /sources/{source_id}/update-repo`

**Functionality**:
- Re-clone repository with latest changes
- Process only changed/new files (using git diff or content hash comparison)
- Preserve existing snippets for unchanged content
- Handle branch changes, path updates
- Update repository metadata
- Track update history

**Request Model**:
```python
class UpdateRepoRequest(BaseModel):
    repo_url: str | None = Field(None, description="New repository URL")
    branch: str | None = Field(None, description="New branch")
    path: str | None = Field(None, description="New path")
    version: str | None = Field(None, description="New version")
    include_patterns: list[str] | None = Field(None)
    exclude_patterns: list[str] | None = Field(None)
    preserve_unchanged: bool = Field(True, description="Keep snippets for unchanged content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Update metadata")
```

#### 2.3 Unified Update Endpoint
**Endpoint**: `PATCH /sources/{source_id}/update`

**Logic**:
```python
@router.patch("/sources/{source_id}/update")
async def update_source(source_id: str, request: dict, db: Session = Depends(get_db)):
    # Auto-detect source type and route to appropriate handler
    source = db.query(UploadJob).filter_by(id=source_id).first()
    if not source:
        source = db.query(CrawlJob).filter_by(id=source_id).first()
    
    if source and hasattr(source, 'source_type'):
        if source.source_type == 'upload':
            return await update_upload_source(source_id, UpdateUploadRequest(**request), db)
        elif source.source_url and 'github.com' in source.source_url:
            return await update_repo_source(source_id, UpdateRepoRequest(**request), db)
    
    # Fallback to crawl update
    return await update_source_crawl(source_id, UpdateSourceCrawlRequest(**request), db)
```

### Phase 3: Content Comparison Logic

#### 3.1 File Hash Comparison
```python
def generate_content_hash(content: str) -> str:
    """Generate SHA-256 hash of content for comparison."""
    return hashlib.sha256(content.encode()).hexdigest()

def compare_file_hashes(old_hashes: dict, new_files: list) -> dict:
    """Compare old and new file hashes to determine changes."""
    changes = {
        'new': [],
        'modified': [],
        'unchanged': [],
        'removed': []
    }
    
    new_hashes = {}
    for file in new_files:
        content = file['content']
        file_path = file.get('source_url', file.get('path'))
        content_hash = generate_content_hash(content)
        new_hashes[file_path] = content_hash
        
        if file_path not in old_hashes:
            changes['new'].append(file)
        elif old_hashes[file_path] != content_hash:
            changes['modified'].append(file)
        else:
            changes['unchanged'].append(file_path)
    
    # Find removed files
    for file_path in old_hashes:
        if file_path not in new_hashes:
            changes['removed'].append(file_path)
    
    return changes, new_hashes
```

#### 3.2 Snippet Preservation Logic
```python
async def update_snippets_for_changes(
    db: Session, 
    source_id: str, 
    changes: dict, 
    preserve_unchanged: bool = True
):
    """Update snippets based on file changes."""
    
    # Delete snippets for removed files
    if changes['removed']:
        await delete_snippets_for_files(db, source_id, changes['removed'])
    
    # Delete snippets for modified files (will be recreated)
    if changes['modified']:
        await delete_snippets_for_files(db, source_id, [f['source_url'] for f in changes['modified']])
    
    # Process new and modified files
    new_content = changes['new'] + changes['modified']
    if new_content:
        await extract_snippets_from_files(db, source_id, new_content)
    
    # Update content hashes
    return changes.get('new_hashes', {})
```

### Phase 4: Frontend Updates

#### 4.1 Enhanced NewCrawlDialog
- Add "Update Upload" mode with file replacement interface
- Add "Update Repository" mode with repository settings
- Reuse existing components (SourceSelector, BasicFields, etc.)
- Add file upload/drag-drop interface for updates
- Add repository settings form (branch, path, patterns)

#### 4.2 Source Management UI Updates
- Add "Update" buttons to upload sources in Sources page
- Add "Update" buttons to repository sources
- Show update history and change summaries
- Progress indicators for update operations
- Confirmation dialogs for destructive operations

#### 4.3 New Components
```typescript
// UpdateUploadDialog.tsx
interface UpdateUploadDialogProps {
  source: Source;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: UpdateUploadRequest) => void;
}

// UpdateRepoDialog.tsx
interface UpdateRepoDialogProps {
  source: Source;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: UpdateRepoRequest) => void;
}
```

### Phase 5: Background Processing

#### 5.1 Update Job System
```python
class UpdateJob(Base):
    """Track update operations similar to CrawlJob."""
    __tablename__ = "update_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_id = Column(UUID, nullable=False)
    source_type = Column(String(20), nullable=False)  # 'upload', 'repo', 'crawl'
    status = Column(String(20), default="running")
    changes_summary = Column(JSONB, default={})
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    error_message = Column(Text)
```

#### 5.2 WebSocket Progress Updates
- Reuse existing WebSocket infrastructure
- Add update-specific message types
- Progress tracking for file processing
- Error reporting and recovery

### Phase 6: API Integration Points

#### 6.1 Upload Processor Updates
```python
# Extend UploadProcessor for updates
class UploadProcessor:
    async def update_upload(
        self, 
        source_id: str, 
        config: UpdateUploadConfig
    ) -> str:
        """Update existing upload with new files."""
        
    async def update_repository(
        self, 
        source_id: str, 
        config: UpdateRepoConfig
    ) -> str:
        """Update existing GitHub repository."""
```

#### 6.2 GitHub Processor Updates
```python
# Extend GitHubProcessor for updates
class GitHubProcessor:
    async def update_repository(
        self, 
        source_id: str, 
        config: UpdateRepoConfig
    ) -> dict:
        """Update repository with latest changes."""
        
    def get_repository_changes(self, old_commit: str, new_commit: str) -> list:
        """Get list of changed files between commits."""
```

### Phase 7: Testing Strategy

#### 7.1 Unit Tests
- Test content hash comparison logic
- Test snippet preservation/deletion
- Test upload update workflows
- Test repository update workflows
- Test error handling and rollback

#### 7.2 Integration Tests
- End-to-end update workflows
- WebSocket progress updates
- File upload and processing
- GitHub repository cloning and processing
- Database transaction handling

#### 7.3 Performance Tests
- Large repository updates
- Concurrent update operations
- Database performance with large datasets
- Memory usage during file processing

## Implementation Priority

### Phase 1 (High Priority)
1. Database schema updates
2. Upload update endpoint
3. Basic content comparison logic
4. Frontend upload update dialog

### Phase 2 (Medium Priority)
1. GitHub repository update endpoint
2. Repository update dialog
3. Background job processing
4. WebSocket progress updates

### Phase 3 (Low Priority)
1. Unified update endpoint
2. Advanced change tracking
3. Rollback functionality
4. Performance optimizations

## Key Design Decisions

### Backward Compatibility
- All existing APIs continue to work unchanged
- New functionality is additive
- Database migrations are backward compatible

### Performance Considerations
- Content hash comparison for efficient updates
- Process only changed files
- Background processing for large updates
- Database connection pooling

### Error Handling
- Graceful degradation on failures
- Rollback support for failed updates
- Detailed error messages
- WebSocket error notifications

### User Experience
- Clear progress indicators
- Confirmation dialogs for destructive operations
- Change summaries before and after updates
- Intuitive file replacement interface

## Success Metrics

- **Functionality**: Users can successfully update uploaded files and repositories
- **Performance**: Updates process only changed content efficiently
- **Reliability**: Updates can be rolled back on failure
- **Usability**: Clear interface and progress feedback
- **Compatibility**: No breaking changes to existing functionality

## Next Steps

1. Create database migration scripts
2. Implement upload update endpoint
3. Add content comparison logic
4. Create frontend update dialogs
5. Add comprehensive tests
6. Deploy to staging for validation
7. Production release with monitoring

This plan provides a comprehensive roadmap for implementing update functionality while maintaining consistency with existing patterns and ensuring robust error handling and user experience.