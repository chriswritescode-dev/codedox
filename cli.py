#!/usr/bin/env python
"""Command-line interface for CodeDox."""

import click
import asyncio
import sys
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.config import get_settings
from src.database import init_db, get_db_manager
from src.crawler import CrawlManager, CrawlConfig
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


@cli.command()
@click.argument('name')
@click.argument('urls', nargs=-1, required=True)
@click.option('--depth', default=1, help='Maximum crawl depth (0-3)')
@click.option('--domain', help='Domain restriction pattern')
@click.option('--url-patterns', multiple=True, help='URL patterns to include (e.g., "*docs*", "*guide*")')
@click.option('--concurrent', default=20, help='Maximum concurrent crawl sessions (default: 20)')
def crawl(name: str, urls: tuple, depth: int, domain: Optional[str], url_patterns: tuple, 
          concurrent: int):
    """Start a new crawl job."""
    async def run_crawl():
        tools = MCPTools()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Starting crawl job '{name}'...", total=None)
            
            result = await tools.init_crawl(
                name=name,
                start_urls=list(urls),
                max_depth=depth,
                domain_filter=domain,
                url_patterns=list(url_patterns) if url_patterns else None,
                max_concurrent_crawls=concurrent
            )
            
            if "error" in result:
                console.print(f"[red]Error:[/red] {result['error']}")
                return
            
            console.print(f"[green]✓[/green] Crawl job started!")
            console.print(f"Job ID: [cyan]{result['job_id']}[/cyan]")
            console.print(f"URLs: {len(urls)}")
            console.print(f"Max depth: {depth}")
            if url_patterns:
                console.print(f"URL patterns: {', '.join(url_patterns)}")
    
    asyncio.run(run_crawl())


@cli.command()
def sources():
    """List available documentation sources."""
    async def list_sources():
        from src.database import get_db_manager
        from src.database.models import CrawlJob
        
        db_manager = get_db_manager()
        
        with db_manager.get_session() as session:
            jobs = session.query(CrawlJob).order_by(CrawlJob.created_at.desc()).all()
            
            if not jobs:
                console.print("No sources found.")
                return
            
            table = Table(title="Documentation Sources")
            table.add_column("Name", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Snippets", justify="right")
            table.add_column("URLs", justify="right")
            table.add_column("Last Update")
            
            for job in jobs:
                table.add_row(
                    job.name,
                    job.status,
                    str(job.snippets_extracted or 0),
                    str(job.processed_pages or 0),
                    job.updated_at.strftime('%Y-%m-%d %H:%M:%S') if job.updated_at else 'Never'
                )
            
            console.print(table)
    
    asyncio.run(list_sources())


@cli.command()
@click.argument('query')
@click.option('--source', help='Optional library/source name filter')
@click.option('--lang', help='Filter by language')
@click.option('--limit', default=10, help='Maximum results')
def search(query: str, source: Optional[str], lang: Optional[str], limit: int):
    """Search for code snippets across all sources or in a specific source."""
    async def run_search():
        tools = MCPTools()
        
        with console.status("[bold green]Searching..."):
            results = await tools.get_content(
                library_id=source or "",
                query=query,
                limit=limit
            )
        
        console.print(results)
    
    asyncio.run(run_search())


@cli.command()
@click.argument('job_id')
def status(job_id: str):
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
        console.print(f"[bold]Pages:[/bold] {result['pages_processed']}/{result['total_pages']}")
        console.print(f"[bold]Snippets:[/bold] {result['snippets_extracted']}")
    
    asyncio.run(check_status())


@cli.command()
@click.argument('job_id')
def cancel(job_id: str):
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
def upload(file_path: str, source_url: Optional[str]):
    """Upload a markdown file for processing."""
    from src.parser import CodeExtractor
    from src.language import LanguageDetector
    from src.config import settings
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if not source_url:
        source_url = f"file://{file_path}"
    
    extractor = CodeExtractor(
        use_tree_sitter=getattr(settings.code_extraction, 'use_tree_sitter_validation', True),
        min_quality_score=getattr(settings.code_extraction, 'min_ast_quality_score', 0.7)
    )
    detector = LanguageDetector()
    
    with console.status("[bold green]Processing markdown..."):
        blocks = extractor.extract_from_content(content, source_url, "markdown")
    
    console.print(f"[green]✓[/green] Found {len(blocks)} code blocks")
    
    for i, block in enumerate(blocks, 1):
        if block.language == 'unknown':
            detection = detector.detect(block.content)
            block.language = detection.language
        
        console.print(f"\n[bold]Block {i}:[/bold]")
        console.print(f"Language: [cyan]{block.language}[/cyan]")
        console.print(f"Lines: {block.lines_of_code}")
        if block.title:
            console.print(f"Title: {block.title}")


@cli.command()
def mcp():
    """Start the MCP server."""
    from src.mcp_server import MCPServer

    console.print("[bold green]Starting MCP server...[/bold green]")
    server = MCPServer()
    server.run()


@cli.command()
def api():
    """Start API server only."""
    import uvicorn

    console.print("[bold green]Starting CodeDox API server...[/bold green]")
    console.print("API: http://0.0.0.0:8000")
    console.print("API Docs: http://0.0.0.0:8000/docs")
    console.print("MCP Tools: http://0.0.0.0:8000/mcp")
    console.print("\nTo start the web UI, run: python cli.py ui")

    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.debug
    )


@cli.command()
def ui():
    """Start the web UI development server."""
    import subprocess
    import os
    
    frontend_dir = os.path.join(os.path.dirname(__file__), 'frontend')
    
    # Check if node_modules exists
    if not os.path.exists(os.path.join(frontend_dir, 'node_modules')):
        console.print("[yellow]Installing frontend dependencies...[/yellow]")
        subprocess.run(['npm', 'install'], cwd=frontend_dir, check=True)
    
    console.print("[bold green]Starting Web UI development server...[/bold green]")
    console.print("Web UI: http://0.0.0.0:5173")
    
    try:
        subprocess.run(['npm', 'run', 'dev'], cwd=frontend_dir, check=True)
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down Web UI server...[/yellow]")


@cli.command()
@click.option('--coverage', is_flag=True, help='Run with coverage report')
@click.option('--verbose', is_flag=True, help='Verbose test output')
@click.option('--unit', is_flag=True, help='Run unit tests only')
@click.option('--integration', is_flag=True, help='Run integration tests only')
@click.argument('pattern', required=False)
def test(coverage: bool, verbose: bool, unit: bool, integration: bool, pattern: Optional[str]):
    """Run the test suite."""
    import subprocess
    
    cmd = ['pytest']
    
    if coverage:
        cmd.extend(['--cov=src', '--cov-report=html', '--cov-report=term'])
        console.print("[bold green]Running tests with coverage...[/bold green]")
    else:
        console.print("[bold green]Running tests...[/bold green]")
    
    if verbose:
        cmd.append('-vv')
    
    if unit:
        cmd.extend(['-m', 'not integration'])
    elif integration:
        cmd.extend(['-m', 'integration'])
    
    if pattern:
        cmd.extend(['-k', pattern])
    
    cmd.append('tests/')
    
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
def all():
    """Start API server and web UI (for MCP, use 'cli.py mcp' separately)."""
    import subprocess
    import concurrent.futures
    import time
    import signal
    import os

    console.print("[bold green]Starting CodeDox (API + Web UI)...[/bold green]")
    console.print("[dim]Note: MCP server should be run separately with 'python cli.py mcp'[/dim]")
    console.print("[dim]Press Ctrl+C to stop all services[/dim]\n")

    # Get API configuration to pass to frontend
    api_url = f"http://{settings.api.host}:{settings.api.port}"
    
    # Store process references
    processes = []

    def run_service(name, cmd, env_vars=None):
        """Run a service and return the process."""
        try:
            if name == "api":
                console.print(f"[green]✓[/green] Starting API server on {api_url}")
            else:
                console.print("[blue]✓[/blue] Starting Web UI on http://0.0.0.0:5173")

            # Set up environment variables for the process
            process_env = os.environ.copy()
            if env_vars:
                process_env.update(env_vars)

            process = subprocess.Popen(cmd, shell=True, env=process_env)
            processes.append(process)
            return process.wait()
        except Exception as e:
            console.print(f"[red]Error starting {name}: {e}[/red]")
            return 1

    def cleanup(signum=None, frame=None):
        """Clean up all processes."""
        console.print("\n[yellow]Shutting down all services...[/yellow]")
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=5)
            except:
                p.kill()
        sys.exit(0)

    # Set up signal handler
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Start services
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Start API first
        api_future = executor.submit(run_service, "api", f"{sys.executable} cli.py api")

        # Give API a moment to start
        time.sleep(2)

        # Start UI with dynamic API proxy target
        ui_env_vars = {
            "VITE_API_PROXY_TARGET": api_url
        }
        ui_future = executor.submit(run_service, "ui", f"{sys.executable} cli.py ui", ui_env_vars)

        try:
            # Wait for any to finish (shouldn't happen unless there's an error)
            concurrent.futures.wait(
                [api_future, ui_future], return_when=concurrent.futures.FIRST_COMPLETED
            )
        except KeyboardInterrupt:
            cleanup()


@cli.command("crawl-resume")
@click.argument("job_id")
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




@cli.command("crawl-health")
def crawl_health():
    """Check health status of all crawl jobs."""
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


@cli.command("server-api-mcp")
def serve_all():
    """Start both API/Web server and MCP server ."""
    import subprocess
    import concurrent.futures
    import signal
    import sys
    from multiprocessing import Process

    console.print("[bold green]=== CodeDox Starting ===[/bold green]")
    console.print("This will start both the API/Web server and MCP server")

    # Check database connection
    try:
        db_manager = get_db_manager()
        with db_manager.session_scope() as session:
            from sqlalchemy import text

            session.execute(text("SELECT 1"))
        console.print("[green]✅ Database connection verified[/green]")
    except Exception as e:
        console.print(f"[red]❌ Database connection failed: {e}[/red]")
        console.print("[red]Please ensure PostgreSQL is running and configured correctly[/red]")
        sys.exit(1)

    # Store process references
    processes = []

    def run_api_server():
        """Run the FastAPI server."""
        import uvicorn

        uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")

    def run_mcp_server():
        """Run the MCP server."""
        from src.mcp_server.server import main as mcp_main

        asyncio.run(mcp_main())

    def cleanup(signum=None, frame=None):
        """Clean up all processes."""
        console.print("\n[yellow]Shutting down all services...[/yellow]")
        for p in processes:
            try:
                p.terminate()
                p.join(timeout=5)
            except:
                try:
                    p.kill()
                    p.join()
                except:
                    pass
        console.print("[green]Services stopped[/green]")
        sys.exit(0)

    # Set up signal handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Create processes
    api_process = Process(target=run_api_server)
    mcp_process = Process(target=run_mcp_server)
    processes = [api_process, mcp_process]

    try:
        # Start both processes
        api_process.start()
        mcp_process.start()

        console.print("\n" + "=" * 60)
        console.print("[bold green]🚀 CodeDox is running![/bold green]")
        console.print("=" * 60)
        console.print("📡 API/Web UI: http://localhost:8000")
        console.print("🔌 MCP Server: localhost:8899")
        console.print("=" * 60)
        console.print("Press Ctrl+C to stop all services\n")

        # Wait for both processes
        api_process.join()
        mcp_process.join()

    except KeyboardInterrupt:
        cleanup()
    except Exception as e:
        console.print(f"[red]Error running services: {e}[/red]")
        cleanup()




if __name__ == '__main__':
    cli()
