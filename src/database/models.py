"""SQLAlchemy models for the code extraction database."""

from datetime import datetime
from typing import Dict, Any, List, TYPE_CHECKING
from uuid import uuid4
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, ForeignKey,
    ARRAY, CheckConstraint, UniqueConstraint,
    Index, func, Float
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

Base = declarative_base()


class CrawlJob(Base):  # type: ignore[misc,valid-type]
    """Represents a crawling job with configuration and progress tracking."""
    
    __tablename__ = 'crawl_jobs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    domain = Column(String, unique=True)
    start_urls: Column[List[str]] = Column(ARRAY(Text), nullable=False)
    max_depth = Column(Integer, default=1, nullable=False)
    domain_restrictions: Column[List[str]] = Column(ARRAY(Text))
    status = Column(String(20), default='pending', nullable=False)
    total_pages = Column(Integer, default=0)
    processed_pages = Column(Integer, default=0)
    snippets_extracted = Column(Integer, default=0)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    config = Column(JSONB, default={})
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # New tracking fields for recovery
    last_heartbeat = Column(DateTime)
    crawl_phase = Column(String(20))  # 'crawling', 'finalizing'
    crawl_completed_at = Column(DateTime)
    documents_crawled = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Relationships
    documents = relationship("Document", back_populates="crawl_job", cascade="all, delete-orphan")
    failed_pages = relationship("FailedPage", back_populates="crawl_job", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint('max_depth >= 0 AND max_depth <= 5', name='check_max_depth'),
        CheckConstraint(
            "status IN ('pending', 'running', 'paused', 'completed', 'failed', 'cancelled')",
            name='check_status'
        ),
        CheckConstraint(
            "crawl_phase IN ('crawling', 'finalizing') OR crawl_phase IS NULL",
            name='check_crawl_phase'
        ),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'id': str(self.id),
            'name': self.name,
            'domain': self.domain,
            'start_urls': self.start_urls,
            'max_depth': self.max_depth,
            'status': self.status,
            'total_pages': self.total_pages,
            'processed_pages': self.processed_pages,
            'snippets_extracted': self.snippets_extracted,
            'failed_pages_count': len(self.failed_pages) if hasattr(self, 'failed_pages') else 0,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat()
        }


class UploadJob(Base):  # type: ignore[misc,valid-type]
    """Represents an upload job for user-provided documentation."""
    
    __tablename__ = 'upload_jobs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    source_type = Column(String(20), default='upload', nullable=False)
    file_count = Column(Integer, default=0)
    status = Column(String(20), default='pending', nullable=False)
    processed_files = Column(Integer, default=0)
    snippets_extracted = Column(Integer, default=0)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    config = Column(JSONB, default={})
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = relationship("Document", back_populates="upload_job", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('upload', 'file', 'api')",
            name='check_source_type'
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name='check_upload_status'
        ),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'id': str(self.id),
            'name': self.name,
            'source_type': self.source_type,
            'file_count': self.file_count,
            'status': self.status,
            'processed_files': self.processed_files,
            'snippets_extracted': self.snippets_extracted,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'config': self.config,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class Document(Base):  # type: ignore[misc,valid-type]
    """Represents a crawled document/page."""
    
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True)
    url = Column(Text, unique=True, nullable=False, index=True)
    title = Column(Text)
    content_type = Column(String(50), default='html')
    content_hash = Column(String(64), index=True)
    crawl_job_id = Column(UUID(as_uuid=True), ForeignKey('crawl_jobs.id', ondelete='CASCADE'))
    upload_job_id = Column(UUID(as_uuid=True), ForeignKey('upload_jobs.id', ondelete='CASCADE'))
    source_type = Column(String(20), default='crawl')
    crawl_depth = Column(Integer, default=0)
    parent_url = Column(Text)
    last_crawled = Column(DateTime, default=datetime.utcnow)
    meta_data = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    crawl_job = relationship("CrawlJob", back_populates="documents")
    upload_job = relationship("UploadJob", back_populates="documents")
    code_snippets = relationship("CodeSnippet", back_populates="document", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_documents_crawl_job_id', 'crawl_job_id'),
        Index('idx_documents_upload_job_id', 'upload_job_id'),
        Index('idx_documents_source_type', 'source_type'),
        Index('idx_documents_crawl_depth', 'crawl_depth'),
        Index('idx_documents_created_at', 'created_at'),
        CheckConstraint(
            "source_type IN ('crawl', 'upload')",
            name='check_doc_source_type'
        ),
        CheckConstraint(
            "(crawl_job_id IS NOT NULL AND upload_job_id IS NULL AND source_type = 'crawl') OR "
            "(upload_job_id IS NOT NULL AND crawl_job_id IS NULL AND source_type = 'upload')",
            name='check_job_link'
        ),
    )


class CodeSnippet(Base):  # type: ignore[misc,valid-type]
    """Represents an extracted code snippet with metadata."""
    
    __tablename__ = 'code_snippets'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'))
    title = Column(Text)
    description = Column(Text)
    language = Column(String(50), index=True)
    code_content = Column(Text, nullable=False)
    code_hash = Column(String(64), unique=True)
    line_start = Column(Integer)
    line_end = Column(Integer)
    context_before = Column(Text)
    context_after = Column(Text)
    
    # Enhanced context fields
    section_title = Column(Text)
    section_content = Column(Text)  # Full section containing the code
    
    functions: Column[List[str]] = Column(ARRAY(Text))
    imports: Column[List[str]] = Column(ARRAY(Text))
    keywords: Column[List[str]] = Column(ARRAY(Text))
    snippet_type = Column(String(20), default='code')
    source_url = Column(Text, index=True)
    meta_data = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Note: search_vector is generated in PostgreSQL
    
    # Relationships
    document = relationship("Document", back_populates="code_snippets")
    
    # Snippet relationships with cascade delete
    outgoing_relationships = relationship(
        "SnippetRelationship",
        foreign_keys="SnippetRelationship.source_snippet_id",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    incoming_relationships = relationship(
        "SnippetRelationship",
        foreign_keys="SnippetRelationship.target_snippet_id",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    
    __table_args__ = (
        CheckConstraint(
            "snippet_type IN ('function', 'class', 'example', 'config', 'code')",
            name='check_snippet_type'
        ),
        Index('idx_snippets_document_id', 'document_id'),
        Index('idx_snippets_functions', 'functions', postgresql_using='gin'),
        Index('idx_snippets_imports', 'imports', postgresql_using='gin'),
        Index('idx_snippets_snippet_type', 'snippet_type'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'language': self.language,
            'code_content': self.code_content,
            'source_url': self.source_url,
            'snippet_type': self.snippet_type,
            'functions': self.functions or [],
            'imports': self.imports or [],
            'created_at': self.created_at.isoformat()
        }
    
    def format_output(self) -> str:
        """Format snippet for search output in the required format."""
        return f"""TITLE: {self.title or 'Untitled'}
DESCRIPTION: {self.description or 'No description available'}
SOURCE: {self.source_url}

LANGUAGE: {self.language or 'unknown'}
CODE:
```
{self.code_content}
```

----------------------------------------"""




class FailedPage(Base):  # type: ignore[misc,valid-type]
    """Represents a page that failed to be crawled after all retries."""
    
    __tablename__ = 'failed_pages'
    
    id = Column(Integer, primary_key=True)
    crawl_job_id = Column(UUID(as_uuid=True), ForeignKey('crawl_jobs.id', ondelete='CASCADE'))
    url = Column(Text, nullable=False)
    error_message = Column(Text)
    failed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    crawl_job = relationship("CrawlJob", back_populates="failed_pages")
    
    __table_args__ = (
        UniqueConstraint('crawl_job_id', 'url', name='uq_failed_pages'),
        Index('idx_failed_pages_crawl_job_id', 'crawl_job_id'),
    )


class SnippetRelationship(Base):  # type: ignore[misc,valid-type]
    """Represents relationships between code snippets."""
    
    __tablename__ = 'snippet_relationships'
    
    id = Column(Integer, primary_key=True)
    source_snippet_id = Column(Integer, ForeignKey('code_snippets.id', ondelete='CASCADE'), nullable=False)
    target_snippet_id = Column(Integer, ForeignKey('code_snippets.id', ondelete='CASCADE'), nullable=False)
    relationship_type = Column(String(50), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships with proper cascade configuration
    source_snippet = relationship("CodeSnippet", foreign_keys=[source_snippet_id], overlaps="outgoing_relationships")
    target_snippet = relationship("CodeSnippet", foreign_keys=[target_snippet_id], overlaps="incoming_relationships")
    
    __table_args__ = (
        UniqueConstraint('source_snippet_id', 'target_snippet_id', 'relationship_type', name='uq_snippet_relationships'),
        CheckConstraint(
            "relationship_type IN ('imports', 'extends', 'implements', 'uses', 'example_of', 'configuration_for', 'related')",
            name='check_relationship_type'
        ),
        Index('idx_snippet_rel_source', 'source_snippet_id'),
        Index('idx_snippet_rel_target', 'target_snippet_id'),
        Index('idx_snippet_rel_type', 'relationship_type'),
    )