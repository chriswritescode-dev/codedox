#!/usr/bin/env python
"""Test script for GitHub repository upload feature."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.crawler.github_processor import GitHubProcessor, GitHubRepoConfig


async def test_github_upload():
    """Test GitHub repository upload with a small test repo."""

    # Use a small public test repository
    config = GitHubRepoConfig(
        repo_url="https://github.com/github/docs",
        name="GitHub Docs Test",
        path="content/get-started/quickstart",  # Just process a small folder
        branch="main",
        cleanup=True,
    )

    processor = GitHubProcessor()

    try:
        print("Starting GitHub repository upload test...")
        print(f"Repository: {config.repo_url}")
        print(f"Path: {config.path}")
        print(f"Branch: {config.branch}")

        job_id = await processor.process_repository(config)

        print(f"\n✅ Upload job started successfully!")
        print(f"Job ID: {job_id}")

        # Check job status
        status = processor.upload_processor.get_job_status(job_id)
        if status:
            print(f"\nJob Status: {status['status']}")
            print(f"Files processed: {status.get('processed_files', 0)}")
            print(f"Snippets extracted: {status.get('snippets_extracted', 0)}")

            # Wait for completion
            print("\nWaiting for job to complete...")
            while status and status["status"] == "running":
                await asyncio.sleep(2)
                status = processor.upload_processor.get_job_status(job_id)
                if status:
                    print(f"Status: {status['status']} - Files: {status.get('processed_files', 0)}")

            if status and status["status"] == "completed":
                print(f"\n✅ Job completed successfully!")
                print(f"Total files processed: {status.get('processed_files', 0)}")
                print(f"Total snippets extracted: {status.get('snippets_extracted', 0)}")
            elif status:
                print(f"\n❌ Job failed: {status.get('error_message', 'Unknown error')}")
        else:
            print("\n⚠️ Could not get job status")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Clean up any remaining temp directories
        await processor.cleanup_all()
        print("\n🧹 Cleanup completed")


if __name__ == "__main__":
    print("=" * 50)
    print("GitHub Repository Upload Feature Test")
    print("=" * 50)
    asyncio.run(test_github_upload())
