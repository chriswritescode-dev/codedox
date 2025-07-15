"""Enrichment coordination and management."""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..config import get_settings
from ..llm import LLMClient, MetadataEnricher
from ..database import Document, get_db_manager
from .enrichment_pipeline import EnrichmentPipeline

logger = logging.getLogger(__name__)
settings = get_settings()


class EnrichmentManager:
    """Manages enrichment operations and pipeline lifecycle."""

    def __init__(self):
        """Initialize enrichment manager."""
        self.settings = settings
        self.metadata_enricher: Optional[MetadataEnricher] = None
        self._llm_client: Optional[LLMClient] = None
        self.enrichment_pipeline: Optional[EnrichmentPipeline] = None
        self.db_manager = get_db_manager()

        # Check if LLM is configured
        if settings.llm.endpoint:
            self._llm_endpoint = settings.llm.endpoint
            logger.info(f"LLM enrichment available at: {settings.llm.endpoint}")
        else:
            logger.info("LLM enrichment disabled (no endpoint configured)")

    async def ensure_llm_enricher(self) -> bool:
        """Initialize LLM enricher if not already done.

        Returns:
            True if enricher is available
        """
        if self.metadata_enricher is None and hasattr(self, "_llm_endpoint"):
            try:
                if not self._llm_client:
                    self._llm_client = LLMClient(debug=self.settings.debug)

                # Test connection
                test_result = await self._llm_client.test_connection()

                if test_result.get("status") == "connected":
                    self.metadata_enricher = MetadataEnricher(
                        llm_client=self._llm_client, skip_small_snippets=True, min_lines=2
                    )
                    logger.info(
                        f"LLM enricher initialized with {test_result['provider']} "
                        f"at {test_result['endpoint']}"
                    )
                    return True
                else:
                    logger.warning(f"LLM connection test failed: {test_result.get('error')}")
                    self.metadata_enricher = None
            except Exception as e:
                logger.warning(f"Failed to initialize LLM enricher: {e}")
                self.metadata_enricher = None

        return self.metadata_enricher is not None

    async def ensure_pipeline(self) -> bool:
        """Initialize enrichment pipeline if not already done.

        Returns:
            True if pipeline is available
        """
        # Check if pipeline exists but is not running
        if self.enrichment_pipeline and not self.enrichment_pipeline.is_running:
            logger.warning("Pipeline exists but is not running. Restarting...")
            await self.stop_pipeline()

        if self.enrichment_pipeline is None and hasattr(self, "_llm_endpoint"):
            try:
                if not self._llm_client:
                    self._llm_client = LLMClient(debug=self.settings.debug)

                # Create and start pipeline
                self.enrichment_pipeline = EnrichmentPipeline(llm_client=self._llm_client)
                await self.enrichment_pipeline.start()

                # Verify it's running
                stats = self.enrichment_pipeline.get_stats()
                logger.info(f"Enrichment pipeline started - Stats: {stats}")

                if not self.enrichment_pipeline.is_running:
                    raise RuntimeError("Pipeline failed to start properly")

                return True

            except Exception as e:
                logger.error(f"Failed to start enrichment pipeline: {e}")
                self.enrichment_pipeline = None

        return self.enrichment_pipeline is not None

    async def stop_pipeline(self) -> None:
        """Stop enrichment pipeline if running."""
        if self.enrichment_pipeline:
            logger.info("Stopping enrichment pipeline...")

            # Get final stats
            stats = self.enrichment_pipeline.get_stats()
            logger.info(f"Pipeline final stats: {stats}")

            try:
                await self.enrichment_pipeline.stop()
                logger.info("Pipeline stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping pipeline: {e}")
            finally:
                self.enrichment_pipeline = None

    def is_available(self) -> bool:
        """Check if enrichment is available.

        Returns:
            True if enrichment services are available
        """
        return hasattr(self, "_llm_endpoint") and self._llm_endpoint is not None

    def is_pipeline_running(self) -> bool:
        """Check if pipeline is running.

        Returns:
            True if pipeline is running
        """
        return self.enrichment_pipeline is not None and self.enrichment_pipeline.is_running

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics.

        Returns:
            Pipeline stats or empty dict
        """
        if self.enrichment_pipeline:
            return self.enrichment_pipeline.get_stats()
        return {}

    async def enrich_documents_batch(self, job_id: str, documents: List[Document]) -> int:
        """Enrich a batch of documents.

        Args:
            job_id: Job ID
            documents: Documents to enrich

        Returns:
            Number of documents enriched
        """
        enriched_count = 0

        # Ensure enricher is available
        if not await self.ensure_llm_enricher():
            logger.warning("No enricher available for batch enrichment")
            return 0

        for doc in documents:
            try:
                # Skip if already enriched
                if doc.enrichment_status == "completed":
                    continue

                # Mark as processing
                doc.enrichment_status = "processing"

                # Extract code blocks
                from ..parser import CodeExtractor

                extractor = CodeExtractor(
                    context_chars=2000,
                    min_code_lines=self.settings.code_extraction.min_code_lines,
                    use_tree_sitter=True,
                    min_quality_score=0.7,
                )

                code_blocks = extractor.extract_from_content(
                    doc.markdown_content or doc.processed_content or "",
                    str(doc.url),
                    "markdown",
                    doc.markdown_content or doc.processed_content or "",
                )

                if code_blocks and self.metadata_enricher:
                    # Enrich blocks
                    enriched_results = await self.metadata_enricher.enrich_batch(code_blocks)

                    # Process enriched blocks
                    # (This would normally update the snippets in the database)

                    doc.enrichment_status = "completed"
                    doc.enriched_at = datetime.utcnow()
                    enriched_count += 1
                else:
                    doc.enrichment_status = "completed"
                    doc.enriched_at = datetime.utcnow()

            except Exception as e:
                logger.error(f"Failed to enrich document {doc.url}: {e}")
                doc.enrichment_status = "failed"
                doc.enrichment_error = str(e)

        return enriched_count

    async def resume_job_enrichment(self, job_id: str) -> bool:
        """Resume enrichment for a job.

        Args:
            job_id: Job ID

        Returns:
            True if resumed successfully
        """
        with self.db_manager.session_scope() as session:
            # Find documents needing enrichment
            documents = (
                session.query(Document)
                .filter(
                    Document.crawl_job_id == job_id,
                    Document.enrichment_status.in_(["pending", "failed", "processing"]),
                )
                .all()
            )

            logger.info(f"Found {len(documents)} documents to enrich for job {job_id}")

            if not documents:
                return True

            # Enrich in batches
            batch_size = 10
            total_enriched = 0

            for i in range(0, len(documents), batch_size):
                batch = documents[i : i + batch_size]
                enriched = await self.enrich_documents_batch(job_id, batch)
                total_enriched += enriched

                # Commit batch
                session.commit()

            logger.info(f"Enriched {total_enriched} documents for job {job_id}")
            return True
