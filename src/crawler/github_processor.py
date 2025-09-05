"""GitHub repository processor for extracting markdown documentation."""

import asyncio
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from ..config import get_settings
from .upload_processor import UploadConfig, UploadProcessor

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class GitHubRepoConfig:
    """Configuration for processing a GitHub repository."""

    repo_url: str
    name: str
    version: str | None = None
    path: str | None = None
    branch: str = "main"
    token: str | None = None
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None
    cleanup: bool = True

    def __post_init__(self):
        """Parse GitHub URL to extract branch and path if present."""
        # Parse URLs like:
        # https://github.com/owner/repo/tree/main/path/to/dir
        # https://github.com/owner/repo/blob/main/path/to/file.md
        if "/tree/" in self.repo_url or "/blob/" in self.repo_url:
            parts = self.repo_url.split("/")

            # Find the tree or blob index
            tree_idx = -1
            for i, part in enumerate(parts):
                if part in ["tree", "blob"]:
                    tree_idx = i
                    break

            if tree_idx > 0 and tree_idx + 1 < len(parts):
                # Extract base repo URL
                base_parts = parts[:tree_idx]
                self.repo_url = "/".join(base_parts)

                # Extract branch (next part after tree/blob)
                self.branch = parts[tree_idx + 1]

                # Extract path (everything after branch)
                if tree_idx + 2 < len(parts):
                    self.path = "/".join(parts[tree_idx + 2 :])
                    logger.info(f"Extracted from URL - branch: {self.branch}, path: {self.path}")


class GitHubProcessor:
    """Processes GitHub repositories to extract markdown documentation."""

    def __init__(self):
        """Initialize the GitHub processor."""
        self.upload_processor = UploadProcessor()
        self.temp_dirs: list[Path] = []

    async def process_repository(self, config: GitHubRepoConfig) -> str:
        """
        Process a GitHub repository for markdown documentation.

        Args:
            config: Repository configuration

        Returns:
            Job ID for tracking progress
        """
        temp_dir = None
        try:
            temp_dir = await self._clone_repository(config)

            target_path = temp_dir
            if config.path:
                target_path = temp_dir / config.path
                if not target_path.exists():
                    raise FileNotFoundError(f"Path '{config.path}' not found in repository")
                if not target_path.is_dir():
                    raise ValueError(f"Path '{config.path}' is not a directory")

            markdown_files = self._find_markdown_files(
                target_path, config.include_patterns, config.exclude_patterns
            )

            if not markdown_files:
                raise ValueError(
                    f"No markdown or HTML files found in {'repository' if not config.path else config.path}"
                )

            logger.info(f"Found {len(markdown_files)} markdown files to process")

            files_data = []
            for file_path in markdown_files:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                relative_path = file_path.relative_to(temp_dir)
                source_url = self._generate_source_url(
                    config.repo_url, relative_path, config.branch
                )

                # Determine content type based on file extension
                content_type = (
                    "html" if file_path.suffix.lower() in {".html", ".htm"} else "markdown"
                )

                files_data.append(
                    {
                        "path": str(file_path),
                        "content": content,
                        "source_url": source_url,
                        "content_type": content_type,
                    }
                )

            upload_config = UploadConfig(
                name=config.name,
                version=config.version,
                files=files_data,
                metadata={
                    "source": "github",
                    "repository": config.repo_url,
                    "branch": config.branch,
                    "path": config.path,
                    "file_count": len(files_data),
                },
                extract_code_only=True,
                use_llm=True,
            )

            job_id = await self.upload_processor.process_upload(upload_config)

            return job_id

        finally:
            if temp_dir and config.cleanup:
                await self._cleanup_temp_dir(temp_dir)

    async def _clone_repository(self, config: GitHubRepoConfig) -> Path:
        """Clone a repository to a temporary directory."""
        temp_dir = Path(tempfile.mkdtemp(prefix="codedox_repo_"))
        self.temp_dirs.append(temp_dir)

        repo_url = config.repo_url
        if config.token and "github.com" in repo_url:
            parsed = urlparse(repo_url)
            if parsed.scheme == "https":
                repo_url = f"https://{config.token}@{parsed.netloc}{parsed.path}"

        if config.path:
            # Use sparse checkout for partial clones
            clone_cmd = [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                config.branch,
                "--single-branch",
                "--filter=blob:none",
                "--sparse",
                repo_url,
                str(temp_dir),
            ]
        else:
            # Full clone for entire repo
            clone_cmd = [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                config.branch,
                "--single-branch",
                repo_url,
                str(temp_dir),
            ]

        logger.info(
            f"Cloning repository: {config.repo_url} (branch: {config.branch}, path: {config.path})"
        )

        process = await asyncio.create_subprocess_exec(
            *clone_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            await self._cleanup_temp_dir(temp_dir)
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise RuntimeError(f"Failed to clone repository: {error_msg}")

        if config.path:
            # Initialize sparse-checkout and set the path
            init_cmd = [
                "git",
                "-C",
                str(temp_dir),
                "sparse-checkout",
                "init",
                "--cone",
            ]

            process = await asyncio.create_subprocess_exec(
                *init_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

            # Set the specific path
            sparse_checkout_cmd = [
                "git",
                "-C",
                str(temp_dir),
                "sparse-checkout",
                "set",
                config.path,
            ]

            process = await asyncio.create_subprocess_exec(
                *sparse_checkout_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            await process.communicate()

        logger.info(f"Repository cloned to: {temp_dir}")
        return temp_dir

    def _find_markdown_files(
        self,
        directory: Path,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[Path]:
        """Find all markdown and HTML files in a directory."""
        # Support both markdown and HTML files
        supported_extensions = {
            ".md",
            ".markdown",
            ".mdx",
            ".mdown",
            ".mkd",
            ".mdwn",  # Markdown
            ".html",
            ".htm",  # HTML
        }
        markdown_files = []

        default_excludes = {
            "node_modules",
            ".git",
            ".github",
            "vendor",
            "dist",
            "build",
            "target",
            ".tox",
            ".pytest_cache",
            "__pycache__",
        }

        for root, dirs, files in os.walk(directory):
            root_path = Path(root)

            dirs[:] = [d for d in dirs if d not in default_excludes]

            if exclude_patterns:
                for pattern in exclude_patterns:
                    dirs[:] = [d for d in dirs if not Path(d).match(pattern)]

            for file in files:
                file_path = root_path / file

                if file_path.suffix.lower() not in supported_extensions:
                    continue

                relative_path = file_path.relative_to(directory)

                if exclude_patterns:
                    if any(relative_path.match(pattern) for pattern in exclude_patterns):
                        continue

                if include_patterns:
                    if not any(relative_path.match(pattern) for pattern in include_patterns):
                        continue

                markdown_files.append(file_path)

        return sorted(markdown_files)

    def _generate_source_url(self, repo_url: str, relative_path: Path, branch: str) -> str:
        """Generate a GitHub source URL for a file."""
        from src.api.routes.upload_utils import GitHubURLParser

        try:
            return GitHubURLParser.generate_blob_url(repo_url, branch, relative_path.as_posix())
        except ValueError:
            # Fallback for non-GitHub repositories
            repo_url = repo_url.rstrip(".git")
            return f"{repo_url}/blob/{branch}/{relative_path.as_posix()}"

    async def _cleanup_temp_dir(self, temp_dir: Path) -> None:
        """Clean up a temporary directory."""
        try:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")

            if temp_dir in self.temp_dirs:
                self.temp_dirs.remove(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to clean up temporary directory {temp_dir}: {e}")

    async def cleanup_all(self) -> None:
        """Clean up all temporary directories."""
        for temp_dir in self.temp_dirs[:]:
            await self._cleanup_temp_dir(temp_dir)
