"""Core crawler engine that manages frontier queue, rate limiting, and extraction pipeline."""

import asyncio
import random
from typing import Callable, Optional, Set
from urllib.parse import urlparse

from config import DEFAULT_CONCURRENCY, RATE_LIMIT_DELAY_SECONDS
from database import Database
from fetcher import HybridFetcher
from models import JobPost
from parser import extract_links, parse_jobs_from_html


class JobCrawler:
    """Asynchronous crawler specialized in Software Engineering job discovery."""

    def __init__(
        self,
        db: Database,
        max_depth: int = 2,
        max_pages: int = 50,
        concurrency: int = DEFAULT_CONCURRENCY,
        use_playwright: bool = False,
        restrict_domain: bool = True,
        on_job_found: Optional[Callable[[JobPost], None]] = None,
        on_page_crawled: Optional[Callable[[str, int, int], None]] = None,
    ):
        self.db = db
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.concurrency = concurrency
        self.use_playwright = use_playwright
        self.restrict_domain = restrict_domain
        self.on_job_found = on_job_found
        self.on_page_crawled = on_page_crawled

        self.pages_crawled_count = 0
        self.jobs_found_count = 0
        self._visited_in_session: Set[str] = set()

    async def run(self, seed_urls: list[str]) -> None:
        """Execute the crawl pipeline starting with seed URLs."""
        # Enqueue seed URLs
        for url in seed_urls:
            self.db.enqueue_url(url, depth=0)

        # Determine domain scope if restricted
        allowed_domain = None
        if self.restrict_domain and seed_urls:
            allowed_domain = urlparse(seed_urls[0]).netloc.lower()

        async with HybridFetcher(use_playwright=self.use_playwright) as fetcher:
            semaphore = asyncio.Semaphore(self.concurrency)

            while self.pages_crawled_count < self.max_pages:
                # Fetch next batch of pending URLs from database
                pending_batch = self.db.get_pending_urls(limit=self.concurrency)
                if not pending_batch:
                    # No pending URLs left
                    break

                tasks = [
                    self._process_url(
                        item.url,
                        item.depth,
                        allowed_domain,
                        fetcher,
                        semaphore,
                    )
                    for item in pending_batch
                ]

                await asyncio.gather(*tasks)

    async def _process_url(
        self,
        url: str,
        depth: int,
        allowed_domain: Optional[str],
        fetcher: HybridFetcher,
        semaphore: asyncio.Semaphore,
    ) -> None:
        if self.pages_crawled_count >= self.max_pages:
            return

        if url in self._visited_in_session:
            self.db.update_queue_status(url, "completed")
            return

        self._visited_in_session.add(url)
        self.db.update_queue_status(url, "in_progress")

        async with semaphore:
            # Politeness delay with small jitter
            jitter = random.uniform(0.2, 0.8)
            await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS + jitter)

            # Fetch the page
            response = await fetcher.fetch(url)

            # Record page crawl log in SQLite
            self.db.log_page_crawl(
                url=response.url,
                status_code=response.status_code,
                fetched_via=response.fetched_via,
                elapsed=response.elapsed_seconds,
            )

            if response.status_code != 200 or not response.html:
                self.db.update_queue_status(url, "failed", error=response.error or f"HTTP {response.status_code}")
                return

            self.pages_crawled_count += 1
            self.db.update_queue_status(url, "completed")

            # 1. Parse jobs on the page
            jobs = parse_jobs_from_html(response.html, response.url)
            for job in jobs:
                if self.db.save_job(job):
                    self.jobs_found_count += 1
                    if self.on_job_found:
                        self.on_job_found(job)

            if self.on_page_crawled:
                self.on_page_crawled(response.url, response.status_code, len(jobs))

            # 2. Extract and enqueue child links if within depth limit
            if depth < self.max_depth:
                child_links = extract_links(
                    raw_html=response.html,
                    base_url=response.url,
                    restrict_domain=allowed_domain if self.restrict_domain else None,
                )
                for link in child_links:
                    if link not in self._visited_in_session:
                        self.db.enqueue_url(link, depth=depth + 1)
