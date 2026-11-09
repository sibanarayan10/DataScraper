"""Command-line interface (CLI) for the Software Engineering Job Scraper."""

import asyncio
import csv
import json
from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config import DATABASE_PATH, EXPORTS_DIR
from crawler import JobCrawler
from database import Database
from models import JobPost

app = typer.Typer(
    name="job-scraper",
    help="High-performance web crawler & scraper for Software Engineering job openings.",
    add_completion=False,
)
console = Console()
db = Database(DATABASE_PATH)


@app.command()
def crawl(
    seeds: List[str] = typer.Argument(
        ...,
        help="One or more seed URLs to begin crawling (e.g., https://remoteok.com or company career pages)",
    ),
    depth: int = typer.Option(2, "--depth", "-d", help="Maximum link traversal depth"),
    max_pages: int = typer.Option(30, "--max-pages", "-m", help="Maximum number of pages to crawl"),
    concurrency: int = typer.Option(3, "--concurrency", "-c", help="Number of concurrent crawler workers"),
    playwright: bool = typer.Option(
        False, "--playwright", "-p", help="Use headless Playwright browser for JavaScript-heavy pages"
    ),
    all_domains: bool = typer.Option(
        False, "--all-domains", help="Allow crawler to follow external domain links"
    ),
):
    """Start the crawler on target seed URLs."""
    console.print(
        Panel.fit(
            f"[bold cyan]Software Engineering Job Crawler[/bold cyan]\n"
            f"[dim]Seeds:[/dim] {', '.join(seeds)}\n"
            f"[dim]Max Depth:[/dim] {depth} | [dim]Max Pages:[/dim] {max_pages} | [dim]Mode:[/dim] {'Playwright (Headless)' if playwright else 'Fast HTTP (httpx)'}",
            title="Crawler Initialized",
            border_style="cyan",
        )
    )

    def on_job_found(job: JobPost):
        tech_badge = f"[cyan]{', '.join(job.tech_stack[:4])}[/cyan]" if job.tech_stack else "[dim]None detected[/dim]"
        remote_badge = "[bold green][Remote][/bold green] " if job.is_remote else ""
        console.print(
            f" [bold green]+ Job Saved:[/bold green] {remote_badge}[bold]{job.title}[/bold] @ {job.company} | Tech: {tech_badge}"
        )

    def on_page_crawled(url: str, status: int, jobs_count: int):
        console.print(f" [dim]-> Crawled ({status}):[/dim] {url} [dim]({jobs_count} job(s) found)[/dim]")

    crawler = JobCrawler(
        db=db,
        max_depth=depth,
        max_pages=max_pages,
        concurrency=concurrency,
        use_playwright=playwright,
        restrict_domain=not all_domains,
        on_job_found=on_job_found,
        on_page_crawled=on_page_crawled,
    )

    with console.status("[bold green]Crawling in progress..."):
        asyncio.run(crawler.run(seeds))

    console.print("\n[bold green]✓ Crawl completed![/bold green]")
    console.print(f"Total Pages Crawled: [cyan]{crawler.pages_crawled_count}[/cyan]")
    console.print(f"Total SWE Jobs Found: [cyan]{crawler.jobs_found_count}[/cyan]\n")
    console.print("Run [bold cyan]python cli.py jobs[/bold cyan] to inspect saved jobs.")


@app.command()
def jobs(
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Search keyword in title, company, or desc"),
    tech: Optional[str] = typer.Option(None, "--tech", "-t", help="Filter by technology (e.g. Python, React, AWS)"),
    remote: bool = typer.Option(False, "--remote", "-r", help="Show remote positions only"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of records to display"),
):
    """View and filter saved Software Engineering jobs in SQLite."""
    results = db.fetch_jobs(limit=limit, keyword=search, remote_only=remote, tech=tech)

    if not results:
        console.print("[yellow]No jobs found matching the criteria.[/yellow]")
        return

    table = Table(title=f"Saved Software Engineering Jobs ({len(results)} shown)", border_style="cyan")
    table.add_column("ID", justify="right", style="dim", width=4)
    table.add_column("Title", style="bold white", min_width=25)
    table.add_column("Company", style="cyan", min_width=15)
    table.add_column("Location / Remote", style="magenta", min_width=15)
    table.add_column("Experience", style="yellow", min_width=10)
    table.add_column("Tech Stack", style="green", min_width=20)
    table.add_column("URL", style="dim blue", min_width=25)

    for job in results:
        remote_tag = "[bold green]Remote[/bold green]" if job["is_remote"] else (job["location"] or "Unspecified")
        tech_tags = ", ".join(job["tech_stack"][:4]) if job["tech_stack"] else "-"
        table.add_row(
            str(job["id"]),
            job["title"][:35],
            (job["company"] or "Unknown")[:20],
            remote_tag[:20],
            job["experience_level"] or "Mid",
            tech_tags,
            job["url"][:40] + "...",
        )

    console.print(table)


@app.command()
def stats():
    """Display crawler progress and in-demand tech stack analytics."""
    data = db.get_stats()

    console.print(
        Panel.fit(
            f"[bold]Total Software Engineering Jobs Stored:[/bold] [cyan]{data['total_jobs']}[/cyan]\n"
            f"[bold]Remote Opportunities:[/bold] [green]{data['remote_jobs']}[/green]\n"
            f"[bold]Queue Status:[/bold] Pending: {data['queue_pending']} | Completed: {data['queue_completed']} | Failed: {data['queue_failed']}",
            title="Database Summary",
            border_style="green",
        )
    )

    if data["top_tech"]:
        table = Table(title="Top In-Demand Technologies", border_style="magenta")
        table.add_column("Rank", justify="center", width=6)
        table.add_column("Technology", style="bold cyan")
        table.add_column("Job Mentions", justify="right", style="green")

        for idx, (tech_name, count) in enumerate(data["top_tech"], start=1):
            table.add_row(str(idx), tech_name, str(count))

        console.print(table)


@app.command()
def export(
    output_format: str = typer.Option("json", "--format", "-f", help="Export format: json or csv"),
    destination: Optional[Path] = typer.Option(None, "--output", "-o", help="Custom destination path"),
):
    """Export all stored jobs to CSV or JSON file."""
    all_jobs = db.fetch_jobs(limit=10000)
    if not all_jobs:
        console.print("[yellow]No jobs in database to export.[/yellow]")
        return

    dest = destination or (EXPORTS_DIR / f"jobs_export.{output_format.lower()}")

    if output_format.lower() == "csv":
        fieldnames = [
            "id",
            "title",
            "company",
            "location",
            "is_remote",
            "experience_level",
            "tech_stack",
            "salary_min",
            "salary_max",
            "salary_currency",
            "url",
            "date_posted",
            "crawled_at",
        ]
        with open(dest, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in all_jobs:
                row_copy = dict(row)
                row_copy["tech_stack"] = ", ".join(row_copy["tech_stack"])
                writer.writerow(row_copy)
    else:
        with open(dest, mode="w", encoding="utf-8") as f:
            json.dump(all_jobs, f, indent=2, default=str)

    console.print(f"[bold green]✓ Successfully exported {len(all_jobs)} jobs to:[/bold green] [cyan]{dest}[/cyan]")


if __name__ == "__main__":
    app()
