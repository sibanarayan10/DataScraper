# Software Engineering Job Crawler & Scraper

A high-performance, modular web crawler tailored for discovering, extracting, and indexing **Software Engineering job openings** across the internet and saving them into an SQLite database.

---

## Features

- **Hybrid Fetching Engine**:
  - **Fast Async HTTP (`httpx`)**: Rapidly crawls static career pages, sitemaps, and feeds.
  - **Headless Browser (`Playwright`)**: Handles dynamic single-page applications (React, Angular, Vue) requiring JavaScript execution and DOM hydration.
- **Universal Job Extraction (`Schema.org`)**:
  - Automatically parses `<script type="application/ld+json">` with `@type: "JobPosting"`.
  - Works across thousands of company career portals and tech job platforms out of the box.
- **Software Engineering Relevance Classifier**:
  - Distinguishes SWE roles (Frontend, Backend, Full Stack, DevOps, SRE, ML/AI, Mobile, Cloud) from non-engineering roles.
  - Extracts experience level (`Junior`, `Mid`, `Senior`, `Lead`, `Staff`).
  - Detects Remote work status.
- **Tech Stack Auto-Detection**:
  - Automatically identifies and tags 40+ languages, frameworks, databases, and cloud tools (Python, React, AWS, Docker, PostgreSQL, etc.).
- **SQLite Storage & Queue Management**:
  - Relational schema with index optimization.
  - Frontier queue tracking crawl depth, status (`pending`, `completed`, `failed`), and URL deduplication.
- **Rich Interactive CLI**:
  - View jobs, filter by technology or remote status, inspect top in-demand skills, and export to CSV/JSON.

---

## Project Structure

```
DataScraper/
├── .venv/               # Isolated Python virtual environment
├── config.py            # Global settings, concurrency, and tech keywords
├── database.py          # SQLite schema, queue operations, and CRUD
├── models.py            # Pydantic data schemas (JobPost, CrawlQueueItem)
├── fetcher.py           # Hybrid HTTP (httpx) + Browser (Playwright) engine
├── parser.py            # Link discovery + Schema.org JSON-LD extractor
├── classifier.py        # SWE relevance filter, experience detector & tech tagger
├── crawler.py           # Async crawler orchestrator & rate limiter
├── cli.py               # Typer & Rich command-line interface
├── test_crawler.py      # Unit test suite
├── requirements.txt     # Python dependencies
└── README.md            # Documentation
```

---

## Quickstart

### 1. Activate the Virtual Environment

```bash
source .venv/bin/activate
```

### 2. Crawl a Target Website

Crawl a seed website (e.g. a company's career page or job board) up to depth 2:

```bash
python cli.py crawl https://example-career-site.com
```

Options:
- `--playwright` or `-p`: Enable headless browser mode for JavaScript-heavy sites.
- `--depth` or `-d <N>`: Maximum link traversal depth (default: `2`).
- `--max-pages` or `-m <N>`: Maximum pages to crawl (default: `30`).
- `--concurrency` or `-c <N>`: Concurrent workers (default: `3`).
- `--all-domains`: Follow links across external domains (default: restricted to seed domain).

```bash
# Example: Crawling with headless browser support
python cli.py crawl https://example-career-site.com -p -d 2 -m 25
```

---

### 3. View & Filter Scraped Jobs

```bash
# Show the 20 most recent jobs
python cli.py jobs

# Filter by specific technology (e.g., Python, React, Docker)
python cli.py jobs --tech Python

# Filter for remote-only positions
python cli.py jobs --remote

# Search by keyword (title, company, description)
python cli.py jobs --search "Backend"
```

---

### 4. View Tech Trends & Crawler Stats

Inspect total jobs collected, queue progress, and the top most in-demand technologies:

```bash
python cli.py stats
```

---

### 5. Export Data to CSV or JSON

```bash
# Export to JSON (saved in exports/jobs_export.json)
python cli.py export --format json

# Export to CSV
python cli.py export --format csv
```

---

### 6. Run the Test Suite

```bash
python test_crawler.py
```
