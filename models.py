"""Pydantic data models for crawler items and job postings."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl


class JobPost(BaseModel):
    """Normalized structured data representing a software engineering job opening."""
    url: str
    source_domain: str
    title: str
    company: Optional[str] = "Unknown"
    location: Optional[str] = "Unspecified"
    is_remote: bool = False
    employment_type: Optional[str] = None  # e.g., Full-time, Contract, Internship
    experience_level: Optional[str] = None  # Junior, Mid, Senior, Lead, Staff
    tech_stack: List[str] = Field(default_factory=list)
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    description_text: Optional[str] = None
    date_posted: Optional[str] = None
    raw_metadata: Optional[Dict[str, Any]] = None
    crawled_at: datetime = Field(default_factory=datetime.utcnow)


class CrawlQueueItem(BaseModel):
    """An item representing a URL in the crawl frontier queue."""
    id: Optional[int] = None
    url: str
    depth: int = 0
    status: str = "pending"  # pending, in_progress, completed, failed
    retries: int = 0
    created_at: Optional[datetime] = None


class FetchResponse(BaseModel):
    """Response returned by the fetching layer."""
    url: str
    status_code: int
    html: str
    elapsed_seconds: float = 0.0
    error: Optional[str] = None
    fetched_via: str = "httpx"  # "httpx" or "playwright"
