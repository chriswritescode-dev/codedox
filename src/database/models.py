"""SQLAlchemy models for the code extraction database."""

from datetime import datetime
from typing import Dict, Any
from uuid import uuid4
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, ForeignKey,
    ARRAY, CheckConstraint, UniqueConstraint,
    Index, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

Base = declarative_base()


class CrawlJob(Base):
    """Represents a crawling job with configuration and progress tracking."""
    
    __tablename__ = 'crawl_jobs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    domain = Column(String, unique=True)
    start_urls = Column(ARRAY(Text), nullable=False)
    max_depth = Column(Integer, default=1, nullable=False)
    domain_restrictions = Column(ARRAY(Text))
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
    crawl_phase = Column(String(20))  # 'crawling', 'enriching', 'finalizing'
    crawl_completed_at = Column(DateTime)
    enrichment_started_at = Column(DateTime)
    enrichment_completed_at = Column(DateTime)
    documents_crawled = Column(Integer, default=0)
    documents_enriched = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Relationships
    documents = relationship("Document", back_populates="crawl_job", cascade="all, delete-orphan")
    page_links = relationship("PageLink", back_populates="crawl_job", cascade="all, delete-orphan")
    failed_pages = relationship("FailedPage", back_populates="crawl_job", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint('max_depth >= 0 AND max_depth <= 5', name='check_max_depth'),
        CheckConstraint(
            "status IN ('pending', 'running', 'paused', 'completed', 'failed', 'cancelled')",
            name='check_status'
        ),
        CheckConstraint(
            "crawl_phase IN ('crawling', 'enriching', 'finalizing') OR crawl_phase IS NULL",
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


class Document(Base):
    """Represents a crawled document/page."""
    
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True)
    url = Column(Text, unique=True, nullable=False, index=True)
    title = Column(Text)
    content_type = Column(String(50), default='html')
    markdown_content = Column(Text)
    content_hash = Column(String(64), index=True)
    crawl_job_id = Column(UUID(as_uuid=True), ForeignKey('crawl_jobs.id', ondelete='CASCADE'))
    crawl_depth = Column(Integer, default=0)
    parent_url = Column(Text)
    last_crawled = Column(DateTime, default=datetime.utcnow)
    meta_data = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Enrichment tracking
    enrichment_status = Column(String(20), default='pending')  # pending, processing, completed, failed, skipped
    enrichment_error = Column(Text)
    enriched_at = Column(DateTime)
    
    # Relationships
    crawl_job = relationship("CrawlJob", back_populates="documents")
    code_snippets = relationship("CodeSnippet", back_populates="document", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_documents_crawl_job_id', 'crawl_job_id'),
        Index('idx_documents_crawl_depth', 'crawl_depth'),
        Index('idx_documents_created_at', 'created_at'),
    )


class CodeSnippet(Base):
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
    related_snippets = Column(ARRAY(Integer))  # IDs of related code snippets
    
    functions = Column(ARRAY(Text))
    imports = Column(ARRAY(Text))
    keywords = Column(ARRAY(Text))
    snippet_type = Column(String(20), default='code')
    source_url = Column(Text, index=True)
    meta_data = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Note: search_vector is generated in PostgreSQL
    
    # Relationships
    document = relationship("Document", back_populates="code_snippets")
    
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
        return f"""ID: {self.id}
TITLE: {self.title or 'Untitled'}
DESCRIPTION: {self.description or 'No description available'}
SOURCE: {self.source_url}

LANGUAGE: {self.language or 'unknown'}
CODE:
```{self.language or ''}
{self.code_content}
```

----------------------------------------"""


class PageLink(Base):
    """Represents links discovered during crawling for depth tracking."""
    
    __tablename__ = 'page_links'
    
    id = Column(Integer, primary_key=True)
    source_url = Column(Text, nullable=False)
    target_url = Column(Text, nullable=False)
    link_text = Column(Text)
    crawl_job_id = Column(UUID(as_uuid=True), ForeignKey('crawl_jobs.id', ondelete='CASCADE'))
    depth_level = Column(Integer, default=1)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    crawl_job = relationship("CrawlJob", back_populates="page_links")
    
    __table_args__ = (
        UniqueConstraint('source_url', 'target_url', 'crawl_job_id', name='uq_page_links'),
        Index('idx_page_links_crawl_job_id', 'crawl_job_id'),
        Index('idx_page_links_depth_level', 'depth_level'),
    )


class FailedPage(Base):
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