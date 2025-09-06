#!/usr/bin/env python3
"""Command-line interface for CodeDox."""

import asyncio
import sys

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.config import get_settings
from src.crawler import CrawlManager
from src.database import get_db_manager, init_db
from src.mcp_server import MCPTools

console = Console()
settings = get_settings()


@click.group()
def cli():
    """CodeDox CLI - Extract and search code from documentation."""
    pass


@cli.command()
@click.option('--drop', is_flag=True, help='Drop existing tables')
def init(drop: bool):
    """Initialize the database."""
    with console.status("[bold green]Initializing database..."):
        init_db(drop_existing=drop)
    console.print("[green]✓[/green] Database initialized successfully!")


@cli.group()
def crawl():
    """Manage crawl jobs."""
    pass


@crawl.command("start")
@click.argument("name")
@click.argument("urls", nargs=-1, required=True)
@click.option("--depth", default=1, help="Maximum crawl depth (0-3)")
@click.option("--domain", help="Domain restriction pattern")
@click.option(
    "--url-patterns", multiple=True, help='URL patterns to include (e.g., "*docs*", "*guide*")'
)
@click.option(
    "--concurrent", default=None, help="Maximum concurrent crawl sessions (default: from config)"
)
def crawl_start(
    name: str, urls: tuple, depth: int, domain: str | None, url_patterns: tuple, concurrent: int
):
    """Start a new crawl job."""

    async def run_crawl():
        tools = MCPTools()

        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
        ) as progress:
            progress.add_task(f"Starting crawl job '{name}'...", total=None)

            result = await tools.init_crawl(
                name=name,
                start_urls=list(urls),
                max_depth=depth,
                domain_filter=domain,
                url_patterns=list(url_patterns) if url_patterns else None,
                max_concurrent_crawls=concurrent,
            )

            if "error" in result:
                console.print(f"[red]Error:[/red] {result['error']}")
                return

            console.print("[green]✓[/green] Crawl job started!")
            console.print(f"Job ID: [cyan]{result['job_id']}[/cyan]")
            console.print(f"URLs: {len(urls)}")
            console.print(f"Max depth: {depth}")
            if url_patterns:
                console.print(f"URL patterns: {', '.join(url_patterns)}")

    asyncio.run(run_crawl())


@crawl.command('list')
def crawl_list():
    """List all crawl jobs and their status."""
    async def list_sources():
        from src.database import get_db_manager
        from src.database.models import CrawlJob

        db_manager = get_db_manager()

        with db_manager.get_session() as session:
            jobs = session.query(CrawlJob).order_by(CrawlJob.created_at.desc()).all()

            if not jobs:
                console.print("No crawl jobs found.")
                return

            table = Table(title="Crawl Jobs")
            table.add_column("Name", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Snippets", justify="right")
            table.add_column("Pages", justify="right")
            table.add_column("Last Update")

            for job in jobs:
                table.add_row(
                    job.name,
                    job.status,
                    str(job.snippets_extracted or 0),
                    str(job.processed_pages or 0),
                    job.updated_at.strftime("%Y-%m-%d %H:%M:%S") if job.updated_at else "Never",
                )

            console.print(table)

    asyncio.run(list_sources())


@cli.command()
@click.argument("query")
@click.option("--source", help="Optional library/source name filter")
@click.option("--lang", help="Filter by language")
@click.option("--limit", default=10, help="Maximum results")
def search(query: str, source: str | None, lang: str | None, limit: int):
    """Search for code snippets."""

    async def run_search():
        tools = MCPTools()

        with console.status("[bold green]Searching..."):
            results = await tools.get_content(library_id=source or "", query=query, limit=limit)

        console.print(results)

    asyncio.run(run_search())


@crawl.command('status')
@click.argument('job_id')
def crawl_status(job_id: str):
    """Check status of a crawl job."""

    async def check_status():
        tools = MCPTools()
        result = await tools.get_crawl_status(job_id)

        if "error" in result:
            console.print(f"[red]Error:[/red] {result['error']}")
            return

        console.print(f"[bold]Job:[/bold] {result['name']}")
        console.print(f"[bold]Status:[/bold] {result['status']}")
        console.print(f"[bold]Progress:[/bold] {result['progress']}")
        console.print(f"[bold]Pages:[/bold] {result['processed_pages']}/{result['total_pages']}")
        console.print(f"[bold]Snippets:[/bold] {result['snippets_extracted']}")

    asyncio.run(check_status())


@crawl.command('cancel')
@click.argument('job_id')
def crawl_cancel(job_id: str):
    """Cancel a running crawl job."""

    async def cancel_job():
        tools = MCPTools()
        result = await tools.cancel_crawl(job_id)

        if "error" in result:
            console.print(f"[red]Error:[/red] {result['error']}")
            return

        console.print(f"[green]✓[/green] {result['message']}")

    asyncio.run(cancel_job())


@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--source-url', help='Source URL for the content')
@click.option('--name', help='Name for the uploaded content')
def upload(file_path: str, source_url: str | None, name: str | None):
    """Upload a markdown file for processing."""
    import os

    from src.crawler import UploadConfig, UploadProcessor

    async def run_upload():
        with open(file_path, encoding='utf-8') as f:
            content = f.read()

        final_source_url = source_url if source_url else f"file://{os.path.abspath(file_path)}"
        final_name = name if name else os.path.basename(file_path)

        # Determine content type from extension
        content_type = "markdown"
        if file_path.endswith(".rst"):
            content_type = "restructuredtext"
        elif file_path.endswith(".adoc"):
            content_type = "asciidoc"
        elif file_path.endswith(".txt"):
            content_type = "text"

        processor = UploadProcessor()

        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
        ) as progress:
            task = progress.add_task(f"Uploading '{final_name}'...", total=None)

            config = UploadConfig(
                name=final_name,
                files=[
                    {
                        "content": content,
                        "source_url": final_source_url,
                        "content_type": content_type,
                    }
                ],
                metadata={"uploaded_via": "cli", "original_path": file_path},
            )

            job_id = await processor.process_upload(config)

            console.print("[green]✓[/green] Upload job started!")
            console.print(f"Job ID: [cyan]{job_id}[/cyan]")
            console.print(f"File: {file_path}")
            console.print(f"Name: {name}")

            # Wait for completion
            progress.update(task, description="Processing file...")

            while True:
                await asyncio.sleep(1)
                status = processor.get_job_status(job_id)
                if status and status["status"] in ["completed", "failed"]:
                    break

            if status["status"] == "completed":
                console.print("[green]✓[/green] Processing completed!")
                console.print(f"Snippets extracted: {status.get('snippets_extracted', 0)}")
            else:
                console.print(
                    f"[red]✗[/red] Processing failed: {status.get('error_message', 'Unknown error')}"
                )

    asyncio.run(run_upload())


@cli.command("upload-repo")
@click.argument("repo_url")
@click.option("--name", help="Name for this documentation source")
@click.option("--path", help="Specific path within the repository to process")
@click.option("--branch", default="main", help="Git branch to clone (default: main)")
@click.option(
    "--token", envvar="GITHUB_TOKEN", help="GitHub personal access token for private repos"
)
@click.option("--include", multiple=True, help='Include file patterns (e.g., "docs/**/*.md")')
@click.option("--exclude", multiple=True, help='Exclude file patterns (e.g., "**/test/*.md")')
@click.option("--no-cleanup", is_flag=True, help="Keep cloned repository after processing")
def upload_repo(repo_url, name, path, branch, token, include, exclude, no_cleanup):
    """Upload markdown documentation from a GitHub repository."""
    from src.crawler.github_processor import GitHubProcessor, GitHubRepoConfig

    async def run_upload_repo():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Cloning repository...", total=None)

            # Auto-generate name from repo URL if not provided
            if not name:
                import re

                match = re.search(r"/([^/]+?)(?:\.git)?$", repo_url)
                name = match.group(1) if match else "Repository Documentation"

            config = GitHubRepoConfig(
                repo_url=repo_url,
                name=name,
                path=path,
                branch=branch,
                token=token,
                include_patterns=list(include) if include else None,
                exclude_patterns=list(exclude) if exclude else None,
                cleanup=not no_cleanup,
            )

            processor = GitHubProcessor()

            try:
                job_id = await processor.process_repository(config)

                console.print("[green]✓[/green] Repository processing started!")
                console.print(f"Job ID: [cyan]{job_id}[/cyan]")
                console.print(f"Repository: {repo_url}")
                console.print(f"Name: {name}")
                if path:
                    console.print(f"Path: {path}")
                console.print(f"Branch: {branch}")

                # Wait for completion
                progress.update(task, description="Processing markdown files...")

                while True:
                    await asyncio.sleep(1)
                    status = processor.upload_processor.get_job_status(job_id)
                    if status and status["status"] in ["completed", "failed"]:
                        break

                if status["status"] == "completed":
                    console.print("[green]✓[/green] Processing completed!")
                    console.print(f"Files processed: {status.get('processed_files', 0)}")
                    console.print(f"Snippets extracted: {status.get('snippets_extracted', 0)}")
                else:
                    console.print(
                        f"[red]✗[/red] Processing failed: {status.get('error_message', 'Unknown error')}"
                    )

            except Exception as e:
                console.print(f"[red]✗[/red] Failed to process repository: {e}")
                sys.exit(1)
            finally:
                if not no_cleanup:
                    await processor.cleanup_all()

    asyncio.run(run_upload_repo())


@cli.command()
@click.option("--coverage", is_flag=True, help="Run with coverage report")
@click.option("--verbose", is_flag=True, help="Verbose test output")
@click.option("--unit", is_flag=True, help="Run unit tests only")
@click.option("--integration", is_flag=True, help="Run integration tests only")
@click.argument("pattern", required=False)
def test(coverage: bool, verbose: bool, unit: bool, integration: bool, pattern: str | None):
    """Run the test suite."""
    import subprocess

    cmd = ["pytest"]

    if coverage:
        cmd.extend(["--cov=src", "--cov-report=html", "--cov-report=term"])
        console.print("[bold green]Running tests with coverage...[/bold green]")
    else:
        console.print("[bold green]Running tests...[/bold green]")

    if verbose:
        cmd.append("-vv")

    if unit:
        cmd.extend(["-m", "not integration"])
    elif integration:
        cmd.extend(["-m", "integration"])

    if pattern:
        cmd.extend(["-k", pattern])

    cmd.append("tests/")

    try:
        result = subprocess.run(cmd, check=True)
        if coverage:
            console.print("\n[green]✓[/green] Coverage report generated in htmlcov/")
    except subprocess.CalledProcessError as e:
        console.print(f"\n[red]✗[/red] Tests failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        console.print("\n[yellow]Test run interrupted[/yellow]")
        sys.exit(1)


@cli.command()
@click.option("--api", is_flag=True, help="Start API server only (no UI)")
@click.option("--mcp", is_flag=True, help="Start MCP stdio server only")
def serve(api: bool, mcp: bool):
    """Start CodeDox services (default: API + Web UI)."""
    import concurrent.futures
    import os
    import signal
    import subprocess
    import time

    import uvicorn

    # Handle MCP stdio server mode
    if mcp:
        from src.mcp_server import MCPServer

        console.print("[bold green]Starting MCP stdio server...[/bold green]")
        server = MCPServer()
        server.run()
        return

    # Handle API-only mode
    if api:
        console.print("[bold green]Starting CodeDox API server...[/bold green]")
        console.print("API: http://0.0.0.0:8000")
        console.print("API Docs: http://0.0.0.0:8000/docs")
        console.print("MCP Tools: http://0.0.0.0:8000/mcp")

        uvicorn.run(
            "src.api.main:app",
            host=settings.api.host,
            port=settings.api.port,
            reload=settings.debug,
        )
        return

    # Default: Start both API and Web UI
    console.print("[bold green]Starting CodeDox (API + Web UI)...[/bold green]")
    console.print("[dim]Press Ctrl+C to stop all services[/dim]\n")

    # Get API configuration to pass to frontend
    api_url = f"http://{settings.api.host}:{settings.api.port}"

    # Store process references
    processes = []

    def run_api_server():
        """Run the API server directly."""
        console.print(f"[green]✓[/green] Starting API server on {api_url}")
        uvicorn.run(
            "src.api.main:app",
            host=settings.api.host,
            port=settings.api.port,
            reload=False,  # Don't use reload in multi-process mode
        )

    def run_ui_server():
        """Run the UI development server."""
        frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")

        # Check if node_modules exists
        if not os.path.exists(os.path.join(frontend_dir, "node_modules")):
            console.print("[yellow]Installing frontend dependencies...[/yellow]")
            subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)

        console.print("[blue]✓[/blue] Starting Web UI on http://0.0.0.0:5173")

        # Set up environment variables for the UI
        process_env = os.environ.copy()
        process_env["VITE_API_PROXY_TARGET"] = api_url

        process = subprocess.Popen(["npm", "run", "dev"], cwd=frontend_dir, env=process_env)
        processes.append(process)
        return process.wait()

    def cleanup(signum=None, frame=None):
        """Clean up all processes."""
        console.print("\n[yellow]Shutting down all services...[/yellow]")
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                p.kill()
        sys.exit(0)

    # Set up signal handler
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Start services
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Start API server
        api_future = executor.submit(run_api_server)

        # Give API a moment to start
        time.sleep(2)

        # Start UI server
        ui_future = executor.submit(run_ui_server)

        try:
            # Wait for any to finish (shouldn't happen unless there's an error)
            concurrent.futures.wait(
                [api_future, ui_future],
                return_when=concurrent.futures.FIRST_COMPLETED
            )
        except KeyboardInterrupt:
            cleanup()


@crawl.command('resume')
@click.argument('job_id')
def crawl_resume(job_id: str):
    """Resume a failed or stalled crawl job."""

    async def run_resume():
        manager = CrawlManager()
        success = await manager.resume_failed_job(job_id)

        if success:
            console.print(f"[green]✓[/green] Job {job_id} resumed successfully")
        else:
            console.print(f"[red]✗[/red] Failed to resume job {job_id}")
            sys.exit(1)

    asyncio.run(run_resume())


@crawl.command("health")
def crawl_health():
    """Check health status of all running crawl jobs."""
    from src.crawler.health_monitor import get_health_monitor

    health_monitor = get_health_monitor()
    db_manager = get_db_manager()

    with db_manager.session_scope() as session:
        from src.database.models import CrawlJob

        running_jobs = session.query(CrawlJob).filter_by(status="running").all()

        if not running_jobs:
            console.print("No running jobs found")
            return

        table = Table(title="Crawl Job Health Status")
        table.add_column("Job ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Phase", style="blue")
        table.add_column("Health", style="green")
        table.add_column("Last Heartbeat", style="yellow")

        for job in running_jobs:
            health = health_monitor.check_job_health(str(job.id))

            health_status = health.get("health_status", "unknown")
            if health_status == "healthy":
                health_style = "[green]Healthy[/green]"
            elif health_status == "warning":
                health_style = "[yellow]Warning[/yellow]"
            elif health_status == "stalled":
                health_style = "[red]Stalled[/red]"
            else:
                health_style = health_status

            heartbeat_ago = ""
            if "seconds_since_heartbeat" in health:
                seconds = health["seconds_since_heartbeat"]
                heartbeat_ago = f"{seconds:.0f}s ago"

            table.add_row(
                str(job.id), job.name, job.crawl_phase or "N/A", health_style, heartbeat_ago
            )

        console.print(table)


if __name__ == "__main__":
    cli()
