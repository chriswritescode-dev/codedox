"""Crawl job lifecycle management."""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..database import CrawlJob, get_db_manager
from .domain_utils import get_primary_domain

logger = logging.getLogger(__name__)


class JobManager:
    """Manages crawl job lifecycle operations."""

    def __init__(self):
        """Initialize job manager."""
        self.db_manager = get_db_manager()

    def create_job(
        self,
        name: str,
        start_urls: list[str],
        max_depth: int,
        domain_restrictions: list[str],
        config: dict[str, Any],
    ) -> str:
        """Create a new crawl job.

        Args:
            name: Job name
            start_urls: URLs to start crawling
            max_depth: Maximum crawl depth
            domain_restrictions: Domain restrictions
            config: Additional configuration

        Returns:
            Job ID
        """
        domain = get_primary_domain(start_urls)
        if not domain:
            raise ValueError("No valid domain found in start URLs")

        with self.db_manager.session_scope() as session:
            job = CrawlJob(
                name=name,
                domain=domain,
                start_urls=start_urls,
                max_depth=max_depth,
                domain_restrictions=domain_restrictions,
                status="running",
                started_at=datetime.utcnow(),
                last_heartbeat=datetime.utcnow(),
                crawl_phase="crawling",
                config=config,
            )
            session.add(job)
            session.commit()
            return str(job.id)

    def get_or_create_job(
        self,
        name: str,
        start_urls: list[str],
        max_depth: int,
        domain_restrictions: list[str],
        config: dict[str, Any],
    ) -> str:
        """Get existing job for domain or create new one.

        Args:
            name: Job name
            start_urls: URLs to start crawling
            max_depth: Maximum crawl depth
            domain_restrictions: Domain restrictions
            config: Additional configuration

        Returns:
            Job ID
        """
        domain = get_primary_domain(start_urls)
        if not domain:
            raise ValueError("No valid domain found in start URLs")

        with self.db_manager.session_scope() as session:
            # Check for existing job with same domain
            existing_job = session.query(CrawlJob).filter_by(domain=domain).first()

            if existing_job:
                # Reuse existing job - update it with new configuration
                logger.info(f"Reusing existing crawl job for domain '{domain}': {existing_job.id}")

                # Reset job for new crawl
                # Check if this is a retry job - if so, preserve the original name
                is_retry = config.get('metadata', {}).get('retry_of_job') is not None

                # Only update name if the existing one is auto-detect or if new name is not auto-detect
                # BUT: Never update name if this is a retry job
                if not is_retry and (existing_job.name.startswith("[Auto-detecting") or not name.startswith("[Auto-detecting")):
                    existing_job.name = name
                    # Clear name_detected flag if setting a new auto-detect name
                    if name.startswith("[Auto-detecting") and existing_job.config.get('name_detected'):
                        existing_job.config['name_detected'] = False

                existing_job.start_urls = start_urls
                existing_job.max_depth = max_depth
                existing_job.domain_restrictions = domain_restrictions
                existing_job.status = "running"
                existing_job.started_at = datetime.utcnow()
                existing_job.last_heartbeat = datetime.utcnow()
                existing_job.crawl_phase = "crawling"
                existing_job.error_message = None
                existing_job.retry_count = 0
                # Reset completion times
                existing_job.completed_at = None
                existing_job.crawl_completed_at = None
                existing_job.documents_crawled = 0
                existing_job.processed_pages = 0
                existing_job.total_pages = 0
                # Check if this is a recrawl vs a resume
                is_recrawl = config.get('metadata', {}).get('is_recrawl', False)

                if is_recrawl:
                    # For recrawls, start counting from 0
                    existing_job.snippets_extracted = 0
                    base_snippet_count = 0
                    logger.debug(f"Recrawl for job {existing_job.id}, starting count from 0")
                else:
                    # For resume operations, preserve existing count
                    from ..database.models import CodeSnippet, Document
                    existing_snippets = session.query(CodeSnippet).join(Document).filter(
                        Document.crawl_job_id == existing_job.id
                    ).count()
                    existing_job.snippets_extracted = existing_snippets
                    base_snippet_count = existing_snippets
                    logger.info(f"Resuming job {existing_job.id} with {existing_snippets} existing snippets")

                # Store base snippet count in config for tracking
                if not existing_job.config:
                    existing_job.config = {}
                existing_job.config.update(config)
                existing_job.config['base_snippet_count'] = base_snippet_count
                # Flag the config column as modified for SQLAlchemy
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(existing_job, 'config')
                logger.debug(f"Set base_snippet_count to {base_snippet_count} for job {existing_job.id}")

                session.commit()
                return str(existing_job.id)
            else:
                # Create new job
                return self.create_job(
                    name, start_urls, max_depth, domain_restrictions, config
                )

    def update_job_status(
        self,
        job_id: str,
        status: str | None = None,
        phase: str | None = None,
        error_message: str | None = None,
        **kwargs,
    ) -> bool:
        """Update job status and fields.

        Args:
            job_id: Job ID
            status: New status
            phase: Current phase
            error_message: Error message if failed
            **kwargs: Additional fields to update

        Returns:
            True if updated successfully
        """
        with self.db_manager.session_scope() as session:
            job = self.get_job(job_id, session)
            if not job:
                return False

            if status:
                job.status = status
            if phase is not None:
                job.crawl_phase = phase
            if error_message:
                job.error_message = error_message

            # Update any additional fields
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)

            # Update timestamps
            job.last_heartbeat = datetime.utcnow()

            session.commit()
            return True

    def update_job_progress(
        self,
        job_id: str,
        processed_pages: int | None = None,
        total_pages: int | None = None,
        snippets_extracted: int | None = None,
        documents_crawled: int | None = None,
    ) -> bool:
        """Update job progress metrics.

        Args:
            job_id: Job ID
            processed_pages: Number of processed pages
            total_pages: Total pages found
            snippets_extracted: Number of snippets extracted
            documents_crawled: Number of documents crawled

        Returns:
            True if updated successfully
        """
        with self.db_manager.session_scope() as session:
            job = self.get_job(job_id, session)
            if not job:
                return False

            if processed_pages is not None:
                job.processed_pages = processed_pages
            if total_pages is not None:
                job.total_pages = total_pages
            if snippets_extracted is not None:
                old_count = job.snippets_extracted
                job.snippets_extracted = snippets_extracted
                logger.debug(f"Job {job_id} snippets updated: {old_count} -> {snippets_extracted}")
            if documents_crawled is not None:
                job.documents_crawled = documents_crawled

            job.last_heartbeat = datetime.utcnow()
            session.commit()
            return True

    def complete_job(
        self, job_id: str, success: bool = True, error_message: str | None = None
    ) -> bool:
        """Mark job as completed.

        Args:
            job_id: Job ID
            success: Whether job completed successfully
            error_message: Error message if failed

        Returns:
            True if updated successfully
        """
        with self.db_manager.session_scope() as session:
            job = self.get_job(job_id, session)
            if not job:
                return False

            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.crawl_phase = None

            if error_message:
                job.error_message = error_message

            # Set completion timestamps
            if not job.crawl_completed_at:
                job.crawl_completed_at = datetime.utcnow()

            session.commit()
            return True

    def get_job(self, job_id: str, session: Session | None = None) -> CrawlJob | None:
        """Get job by ID.

        Args:
            job_id: Job ID (string or UUID)
            session: Optional database session

        Returns:
            CrawlJob or None
        """
        if session:
            return session.query(CrawlJob).filter_by(id=job_id).first()
        else:
            with self.db_manager.session_scope() as session:
                return session.query(CrawlJob).filter_by(id=job_id).first()

    def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get job status as dictionary.

        Args:
            job_id: Job ID

        Returns:
            Job status dictionary or None
        """
        with self.db_manager.session_scope() as session:
            job = self.get_job(job_id, session)
            if job:
                return job.to_dict()
        return None

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job.

        Args:
            job_id: Job ID

        Returns:
            True if cancelled successfully
        """
        return self.complete_job(
            job_id,
            success=True,
            error_message="Cancelled by user"
        )

    def is_job_active(self, job_id: str) -> bool:
        """Check if job is still active.

        Args:
            job_id: Job ID

        Returns:
            True if job is running
        """
        with self.db_manager.session_scope() as session:
            job = self.get_job(job_id, session)
            return bool(job is not None and job.status == "running")

    def update_heartbeat(self, job_id: str) -> bool:
        """Update job heartbeat timestamp.

        Args:
            job_id: Job ID

        Returns:
            True if updated successfully
        """
        with self.db_manager.session_scope() as session:
            job = self.get_job(job_id, session)
            if job:
                job.last_heartbeat = datetime.utcnow()
                session.commit()
                return True
        return False

    def mark_crawl_complete(self, job_id: str) -> bool:
        """Mark crawl as complete.

        Args:
            job_id: Job ID

        Returns:
            True if updated successfully
        """
        return self.complete_job(job_id, success=True)
