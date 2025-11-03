"""LLM-based regeneration of code snippet metadata."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..api.websocket import ConnectionManager
from ..constants import WebSocketMessageType
from ..database import CodeSnippet, CrawlJob, Document
from .extractors.models import TITLE_AND_DESCRIPTION_PROMPT
from .language_mapping import normalize_language
from .llm_retry import LLMDescriptionGenerator

logger = logging.getLogger(__name__)


@dataclass
class RegenerationProgress:
    """Track regeneration progress."""
    total_snippets: int
    processed_snippets: int
    changed_snippets: int
    failed_snippets: int
    current_snippet: str | None = None
    error: str | None = None

    @property
    def percentage(self) -> float:
        """Get completion percentage."""
        if self.total_snippets == 0:
            return 0.0
        return (self.processed_snippets / self.total_snippets) * 100


@dataclass
class SnippetChange:
    """Represents a change to a snippet."""
    snippet_id: int
    original_title: str | None
    original_description: str | None
    original_language: str | None
    new_title: str | None
    new_description: str | None
    new_language: str | None

    @property
    def has_changes(self) -> bool:
        """Check if any changes were made."""
        return (
            self.original_title != self.new_title or
            self.original_description != self.new_description or
            self.original_language != self.new_language
        )


class LLMRegenerator(LLMDescriptionGenerator):
    """Handles regeneration of snippet metadata using LLM."""

    def __init__(self, model: str | None = None, custom_prompt: str | None = None, websocket_manager: ConnectionManager | None = None):
        """Initialize regenerator with optional custom model and prompt.
        
        Args:
            model: Optional LLM model to use (defaults to settings)
            custom_prompt: Optional custom prompt template
            websocket_manager: Optional WebSocket manager for progress updates
        """
        super().__init__()
        self.model = model or self.settings.code_extraction.llm_extraction_model
        self.custom_prompt = custom_prompt or TITLE_AND_DESCRIPTION_PROMPT
        self.websocket_manager = websocket_manager

    async def _send_progress_update(
        self,
        source_id: str,
        client_id: str | None,
        progress: RegenerationProgress
    ) -> None:
        """Send progress update via WebSocket if available."""
        if not self.websocket_manager or not client_id:
            return
            
        await self.websocket_manager.send_message(client_id, {
            "type": WebSocketMessageType.REGENERATION_PROGRESS,
            "source_id": source_id,
            "progress": {
                "total_snippets": progress.total_snippets,
                "processed_snippets": progress.processed_snippets,
                "changed_snippets": progress.changed_snippets,
                "failed_snippets": progress.failed_snippets,
                "percentage": progress.percentage,
                "current_snippet": progress.current_snippet
            }
        })

    async def regenerate_source_metadata(
        self,
        session: Session,
        source_id: str,
        preview_only: bool = True,
        progress_callback: Callable[[RegenerationProgress], None] | None = None,
        max_concurrent: int = 5,
        client_id: str | None = None
    ) -> dict[str, Any]:
        """Regenerate metadata for all snippets in a source.
        
        Args:
            session: Database session
            source_id: Source (crawl job) ID
            preview_only: If True, only preview changes without saving
            progress_callback: Optional callback for progress updates
            max_concurrent: Maximum concurrent LLM requests
            
        Returns:
            Dictionary with regeneration results
        """
        # Get source
        source = session.query(CrawlJob).filter_by(id=source_id).first()
        if not source:
            raise ValueError(f"Source {source_id} not found")

        # Get all snippets for the source
        snippets = (
            session.query(CodeSnippet)
            .join(Document)
            .filter(Document.crawl_job_id == source_id)
            .all()
        )

        if not snippets:
            return {
                "source_id": source_id,
                "source_name": source.name,
                "total_snippets": 0,
                "changed_snippets": 0,
                "failed_snippets": 0,
                "preview": [],
                "error": "No snippets found for this source"
            }

        # Initialize progress
        progress = RegenerationProgress(
            total_snippets=len(snippets),
            processed_snippets=0,
            changed_snippets=0,
            failed_snippets=0
        )

        # Process snippets
        changes: list[SnippetChange] = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_snippet(snippet: CodeSnippet) -> SnippetChange | None:
            async with semaphore:
                try:
                    progress.current_snippet = snippet.title or f"Snippet {snippet.id}"
                    if progress_callback:
                        progress_callback(progress)
                    await self._send_progress_update(source_id, client_id, progress)

                    change = await self._regenerate_snippet_metadata(snippet)

                    progress.processed_snippets += 1
                    if change and change.has_changes:
                        progress.changed_snippets += 1

                    if progress_callback:
                        progress_callback(progress)
                    await self._send_progress_update(source_id, client_id, progress)

                    return change

                except Exception as e:
                    logger.error(f"Failed to regenerate snippet {snippet.id}: {e}")
                    progress.processed_snippets += 1
                    progress.failed_snippets += 1
                    if progress_callback:
                        progress_callback(progress)
                    await self._send_progress_update(source_id, client_id, progress)
                    return None

        # Process all snippets concurrently
        tasks = [process_snippet(snippet) for snippet in snippets]
        results = await asyncio.gather(*tasks)

        # Filter out None results and collect changes
        changes = [r for r in results if r is not None]

        # Apply changes if not preview only
        if not preview_only and changes:
            for change in changes:
                if change.has_changes:
                    snippet = session.query(CodeSnippet).filter_by(id=change.snippet_id).first()
                    if snippet:
                        if change.new_title is not None:
                            snippet.title = change.new_title
                        if change.new_description is not None:
                            snippet.description = change.new_description
                        if change.new_language is not None:
                            snippet.language = change.new_language
                        snippet.updated_at = datetime.utcnow()

            session.commit()

        # Prepare preview (first 10 changes)
        preview_changes = [
            {
                "snippet_id": change.snippet_id,
                "original": {
                    "title": change.original_title,
                    "description": change.original_description,
                    "language": change.original_language
                },
                "new": {
                    "title": change.new_title,
                    "description": change.new_description,
                    "language": change.new_language
                }
            }
            for change in changes[:10]
            if change.has_changes
        ]

        return {
            "source_id": source_id,
            "source_name": source.name,
            "total_snippets": len(snippets),
            "processed_snippets": progress.processed_snippets,
            "changed_snippets": progress.changed_snippets,
            "failed_snippets": progress.failed_snippets,
            "preview": preview_changes,
            "preview_only": preview_only
        }

    async def _regenerate_snippet_metadata(self, snippet: CodeSnippet) -> SnippetChange | None:
        """Regenerate metadata for a single snippet.
        
        Args:
            snippet: Code snippet to regenerate
            
        Returns:
            SnippetChange object or None if failed
        """
        if not self.client:
            logger.error("LLM client not initialized")
            return None

        # Build context
        context_parts = []
        if snippet.context_before:
            context_parts.append(snippet.context_before)
        if snippet.context_after:
            context_parts.append(snippet.context_after)
        if snippet.section_title:
            context_parts.append(f"Section: {snippet.section_title}")

        context = " ".join(context_parts) if context_parts else "No additional context available"

        # Create the prompt
        prompt = self.custom_prompt.replace(
            "{url}", snippet.source_url or snippet.document.url
        ).replace(
            "{context}", context[:500]
        ).replace(
            "{code}", snippet.code_content[:2000]
        )

        try:
            # Make LLM call
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )

            # Parse response
            content = response.choices[0].message.content.strip()

            language = None
            title = None
            description = None

            for line in content.split('\n'):
                line = line.strip()
                if line.startswith("LANGUAGE:"):
                    language = normalize_language(line[9:].strip())
                elif line.startswith("TITLE:"):
                    title = line[6:].strip()
                elif line.startswith("DESCRIPTION:"):
                    description = line[12:].strip()

            # Create change object
            return SnippetChange(
                snippet_id=snippet.id,
                original_title=snippet.title,
                original_description=snippet.description,
                original_language=snippet.language,
                new_title=title,
                new_description=description,
                new_language=language
            )

        except Exception as e:
            logger.error(f"LLM regeneration error for snippet {snippet.id}: {e}")
            return None
