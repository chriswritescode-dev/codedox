"""Tests for GitHub repository processor."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.crawler.github_processor import GitHubProcessor, GitHubRepoConfig


class TestGitHubProcessor:
    """Test GitHub repository processor."""

    @pytest.fixture
    def processor(self):
        """Create a GitHub processor instance."""
        return GitHubProcessor()

    @pytest.fixture
    def sample_config(self):
        """Create a sample repository configuration."""
        return GitHubRepoConfig(
            repo_url="https://github.com/example/test-repo",
            name="Test Repository",
            path="docs",
            branch="main",
            cleanup=True,
        )

    @pytest.mark.asyncio
    async def test_find_markdown_files(self, processor):
        """Test finding markdown files in a directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test structure
            (temp_path / "docs").mkdir()
            (temp_path / "docs" / "readme.md").write_text("# Test")
            (temp_path / "docs" / "guide.MD").write_text("# Guide")
            (temp_path / "docs" / "api.markdown").write_text("# API")
            (temp_path / "src").mkdir()
            (temp_path / "src" / "code.py").write_text("print('hello')")
            (temp_path / "test.txt").write_text("Not markdown")

            # Find all markdown files
            files = processor._find_markdown_files(temp_path)
            assert len(files) == 3

            # Check file paths
            file_names = {f.name for f in files}
            assert "readme.md" in file_names
            assert "guide.MD" in file_names
            assert "api.markdown" in file_names

    @pytest.mark.asyncio
    async def test_find_markdown_with_patterns(self, processor):
        """Test finding markdown files with include/exclude patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test structure
            (temp_path / "docs").mkdir()
            (temp_path / "docs" / "guide.md").write_text("# Guide")
            (temp_path / "docs" / "test").mkdir()
            (temp_path / "docs" / "test" / "test.md").write_text("# Test")
            (temp_path / "examples").mkdir()
            (temp_path / "examples" / "example.md").write_text("# Example")

            # Test with include pattern for nested files (docs/**/*.md matches docs/subdir/*.md)
            files = processor._find_markdown_files(temp_path, include_patterns=["docs/**/*.md"])
            assert len(files) == 1
            file_names = {f.name for f in files}
            assert "test.md" in file_names

            # Test with pattern that matches all files under docs
            files = processor._find_markdown_files(
                temp_path, include_patterns=["docs/*", "docs/**/*"]
            )
            assert len(files) == 2
            file_names = {f.name for f in files}
            assert "guide.md" in file_names
            assert "test.md" in file_names

            # Test with exclude pattern
            files = processor._find_markdown_files(temp_path, exclude_patterns=["**/test/*.md"])
            assert len(files) == 2
            assert all("test.md" not in str(f) for f in files)

    def test_generate_source_url(self, processor):
        """Test generating GitHub source URLs."""
        # Test HTTPS URL
        url = processor._generate_source_url(
            "https://github.com/owner/repo", Path("docs/readme.md"), "main"
        )
        assert url == "https://github.com/owner/repo/blob/main/docs/readme.md"

        # Test with .git suffix
        url = processor._generate_source_url(
            "https://github.com/owner/repo.git", Path("docs/readme.md"), "main"
        )
        assert url == "https://github.com/owner/repo/blob/main/docs/readme.md"

        # Test SSH URL
        url = processor._generate_source_url(
            "git@github.com:owner/repo.git", Path("docs/readme.md"), "main"
        )
        assert url == "https://github.com/owner/repo/blob/main/docs/readme.md"

    @pytest.mark.asyncio
    async def test_clone_repository(self, processor, sample_config):
        """Test cloning a repository (mocked)."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            # Mock successful clone
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            mock_subprocess.return_value = mock_process

            temp_dir = await processor._clone_repository(sample_config)

            # Verify clone command was called
            assert mock_subprocess.called
            # Check if any of the calls was for git clone
            calls = [call[0] for call in mock_subprocess.call_args_list]
            clone_call = next((call for call in calls if "clone" in call), None)
            assert clone_call is not None
            assert sample_config.repo_url in clone_call

            # Clean up
            await processor._cleanup_temp_dir(temp_dir)

    @pytest.mark.asyncio
    async def test_clone_with_path(self, processor):
        """Test cloning with specific path (sparse checkout)."""
        config = GitHubRepoConfig(
            repo_url="https://github.com/example/test-repo",
            name="Test",
            path="docs/api",
            branch="main",
        )

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            mock_subprocess.return_value = mock_process

            temp_dir = await processor._clone_repository(config)

            # Verify sparse checkout was used
            calls = mock_subprocess.call_args_list
            assert any("--sparse" in str(call) for call in calls)

            # Clean up
            await processor._cleanup_temp_dir(temp_dir)

    @pytest.mark.asyncio
    async def test_cleanup_temp_dir(self, processor):
        """Test cleaning up temporary directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_dir = temp_path / "test_repo"
            test_dir.mkdir()
            (test_dir / "file.txt").write_text("test")

            processor.temp_dirs.append(test_dir)

            # Clean up
            await processor._cleanup_temp_dir(test_dir)

            # Verify directory was removed
            assert not test_dir.exists()
            assert test_dir not in processor.temp_dirs

    @pytest.mark.asyncio
    async def test_cleanup_all(self, processor):
        """Test cleaning up all temporary directories."""
        temp_dirs = []
        for i in range(3):
            temp_dir = Path(tempfile.mkdtemp(prefix=f"test_{i}_"))
            temp_dirs.append(temp_dir)
            processor.temp_dirs.append(temp_dir)

        # Clean up all
        await processor.cleanup_all()

        # Verify all directories were removed
        for temp_dir in temp_dirs:
            assert not temp_dir.exists()
        assert len(processor.temp_dirs) == 0

    @pytest.mark.asyncio
    async def test_process_repository_integration(self, processor, sample_config):
        """Test full repository processing (mocked)."""
        with (
            patch("asyncio.create_subprocess_exec") as mock_subprocess,
            patch.object(processor.upload_processor, "process_upload") as mock_upload,
        ):
            # Mock successful clone
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            mock_subprocess.return_value = mock_process

            # Mock upload processor
            mock_upload.return_value = "test-job-id"

            # Create mock markdown files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                (temp_path / "docs").mkdir()
                (temp_path / "docs" / "readme.md").write_text("# Test Documentation")

                with patch.object(processor, "_clone_repository", return_value=temp_path):
                    job_id = await processor.process_repository(sample_config)

                    assert job_id == "test-job-id"
                    assert mock_upload.called

    @pytest.mark.asyncio
    async def test_process_repository_no_markdown_files(self, processor, sample_config):
        """Test processing repository with no markdown files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "docs").mkdir()
            (temp_path / "docs" / "code.py").write_text("print('hello')")

            with patch.object(processor, "_clone_repository", return_value=temp_path):
                with pytest.raises(ValueError, match="No markdown or HTML files found"):
                    await processor.process_repository(sample_config)

    @pytest.mark.asyncio
    async def test_process_repository_invalid_path(self, processor):
        """Test processing repository with invalid path."""
        config = GitHubRepoConfig(
            repo_url="https://github.com/example/test-repo",
            name="Test",
            path="nonexistent/path",
            branch="main",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch.object(processor, "_clone_repository", return_value=temp_path):
                with pytest.raises(FileNotFoundError, match="Path 'nonexistent/path' not found"):
                    await processor.process_repository(config)

    def test_github_url_parsing(self):
        """Test parsing of GitHub URLs with tree/blob paths."""
        # Test URL with tree and path
        config = GitHubRepoConfig(
            repo_url="https://github.com/sgl-project/sgl-project.github.io/tree/main/references/multi_node",
            name="Test",
        )
        assert config.repo_url == "https://github.com/sgl-project/sgl-project.github.io"
        assert config.branch == "main"
        assert config.path == "references/multi_node"

        # Test URL with blob (single file)
        config = GitHubRepoConfig(
            repo_url="https://github.com/owner/repo/blob/develop/README.md",
            name="Test",
        )
        assert config.repo_url == "https://github.com/owner/repo"
        assert config.branch == "develop"
        assert config.path == "README.md"

        # Test regular URL without path
        config = GitHubRepoConfig(
            repo_url="https://github.com/owner/repo",
            name="Test",
        )
        assert config.repo_url == "https://github.com/owner/repo"
        assert config.branch == "main"  # Default branch
        assert config.path is None
