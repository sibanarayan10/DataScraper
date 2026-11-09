"""SQLite Database management and operations for job listings and crawler frontier."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from config import DATABASE_PATH
from models import CrawlQueueItem, JobPost


class Database:
    """SQLite database manager for jobs and crawl queue."""

    def __init__(self, db_path: Path = DATABASE_PATH):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database tables with optimal indexing."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    source_domain TEXT NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT,
                    location TEXT,
                    is_remote INTEGER DEFAULT 0,
                    employment_type TEXT,
                    experience_level TEXT,
                    tech_stack TEXT,              -- Stored as JSON array
                    salary_min REAL,
                    salary_max REAL,
                    salary_currency TEXT,
                    description_text TEXT,
                    date_posted TEXT,
                    crawled_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    raw_metadata TEXT              -- Stored as JSON object
                );
            """)

            # Queue table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crawl_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    depth INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending', -- pending, in_progress, completed, failed
                    retries INTEGER DEFAULT 0,
                    error TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Crawled pages log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crawled_pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    status_code INTEGER,
                    fetched_via TEXT,
                    elapsed_seconds REAL,
                    crawled_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Useful indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_domain ON jobs(source_domain);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_is_remote ON jobs(is_remote);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON crawl_queue(status);")

            conn.commit()

    # --- Queue Operations ---

    def enqueue_url(self, url: str, depth: int = 0) -> bool:
        """Add a URL to the crawl queue if not already present."""
        with self.get_connection() as conn:
            try:
                conn.execute(
                    "INSERT INTO crawl_queue (url, depth, status) VALUES (?, ?, 'pending')",
                    (url, depth)
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False  # Already queued or crawled

    def get_pending_urls(self, limit: int = 10) -> List[CrawlQueueItem]:
        """Fetch the next pending URLs to process."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, url, depth, status, retries, created_at
                FROM crawl_queue
                WHERE status = 'pending'
                ORDER BY depth ASC, id ASC
                LIMIT ?
                """,
                (limit,)
            )
            rows = cursor.fetchall()
            return [
                CrawlQueueItem(
                    id=row["id"],
                    url=row["url"],
                    depth=row["depth"],
                    status=row["status"],
                    retries=row["retries"],
                )
                for row in rows
            ]

    def update_queue_status(self, url: str, status: str, error: Optional[str] = None) -> None:
        """Update the status of a queued URL."""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE crawl_queue
                SET status = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE url = ?
                """,
                (status, error, url)
            )
            conn.commit()

    def is_url_visited(self, url: str) -> bool:
        """Check if a URL was already visited or successfully crawled."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM crawl_queue WHERE url = ? AND status IN ('completed', 'in_progress')",
                (url,)
            )
            return cursor.fetchone() is not None

    # --- Job Operations ---

    def save_job(self, job: JobPost) -> bool:
        """Insert or update a job posting in the database."""
        with self.get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO jobs (
                        url, source_domain, title, company, location,
                        is_remote, employment_type, experience_level,
                        tech_stack, salary_min, salary_max, salary_currency,
                        description_text, date_posted, crawled_at, raw_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        title = excluded.title,
                        company = excluded.company,
                        location = excluded.location,
                        is_remote = excluded.is_remote,
                        employment_type = excluded.employment_type,
                        experience_level = excluded.experience_level,
                        tech_stack = excluded.tech_stack,
                        salary_min = excluded.salary_min,
                        salary_max = excluded.salary_max,
                        salary_currency = excluded.salary_currency,
                        description_text = excluded.description_text,
                        date_posted = excluded.date_posted,
                        raw_metadata = excluded.raw_metadata
                    """,
                    (
                        job.url,
                        job.source_domain,
                        job.title,
                        job.company,
                        job.location,
                        1 if job.is_remote else 0,
                        job.employment_type,
                        job.experience_level,
                        json.dumps(job.tech_stack),
                        job.salary_min,
                        job.salary_max,
                        job.salary_currency,
                        job.description_text,
                        job.date_posted,
                        job.crawled_at.isoformat(),
                        json.dumps(job.raw_metadata) if job.raw_metadata else None,
                    )
                )
                conn.commit()
                return True
            except Exception as e:
                print(f"[DB Error] Failed to save job: {e}")
                return False

    def log_page_crawl(self, url: str, status_code: int, fetched_via: str, elapsed: float) -> None:
        """Record page crawl performance and status."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO crawled_pages (url, status_code, fetched_via, elapsed_seconds)
                VALUES (?, ?, ?, ?)
                """,
                (url, status_code, fetched_via, elapsed)
            )
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics of crawled jobs and queue status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            total_jobs = cursor.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            remote_jobs = cursor.execute("SELECT COUNT(*) FROM jobs WHERE is_remote = 1").fetchone()[0]
            queue_pending = cursor.execute("SELECT COUNT(*) FROM crawl_queue WHERE status = 'pending'").fetchone()[0]
            queue_completed = cursor.execute("SELECT COUNT(*) FROM crawl_queue WHERE status = 'completed'").fetchone()[0]
            queue_failed = cursor.execute("SELECT COUNT(*) FROM crawl_queue WHERE status = 'failed'").fetchone()[0]

            # Top 10 Tech Stack tags
            cursor.execute("SELECT tech_stack FROM jobs WHERE tech_stack IS NOT NULL")
            tech_counts: Dict[str, int] = {}
            for row in cursor.fetchall():
                try:
                    tags = json.loads(row[0])
                    for t in tags:
                        tech_counts[t] = tech_counts.get(t, 0) + 1
                except Exception:
                    pass

            top_tech = sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)[:10]

            return {
                "total_jobs": total_jobs,
                "remote_jobs": remote_jobs,
                "queue_pending": queue_pending,
                "queue_completed": queue_completed,
                "queue_failed": queue_failed,
                "top_tech": top_tech,
            }

    def fetch_jobs(
        self,
        limit: int = 50,
        keyword: Optional[str] = None,
        remote_only: bool = False,
        tech: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query jobs with optional filtering."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM jobs WHERE 1=1"
            params: List[Any] = []

            if remote_only:
                query += " AND is_remote = 1"

            if keyword:
                query += " AND (title LIKE ? OR company LIKE ? OR description_text LIKE ?)"
                kw_wildcard = f"%{keyword}%"
                params.extend([kw_wildcard, kw_wildcard, kw_wildcard])

            if tech:
                query += " AND tech_stack LIKE ?"
                params.append(f"%{tech}%")

            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            result = []
            for row in rows:
                item = dict(row)
                try:
                    item["tech_stack"] = json.loads(item["tech_stack"]) if item["tech_stack"] else []
                except Exception:
                    item["tech_stack"] = []
                result.append(item)
            return result
