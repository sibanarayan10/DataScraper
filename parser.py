"""HTML and JSON-LD parsing engine for link discovery and JobPosting extraction."""

import html
import json
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup

from classifier import (
    detect_experience_level,
    detect_is_remote,
    extract_tech_stack,
    is_swe_role,
)
from models import JobPost


def clean_url(url: str) -> str:
    """Normalize URL by stripping fragments and unwanted tracking query parameters."""
    parsed = urlparse(url)
    # Strip tracking params (utm_*, ref, fbclid, etc.)
    filtered_query = [
        (k, v)
        for k, v in parse_qs(parsed.query, keep_blank_values=False).items()
        if not k.lower().startswith("utm_") and k.lower() not in ("ref", "fbclid", "gclid")
    ]
    flat_query = []
    for k, v_list in filtered_query:
        for val in v_list:
            flat_query.append((k, val))

    clean_query = urlencode(flat_query)
    clean_parts = (parsed.scheme, parsed.netloc, parsed.path.rstrip("/") or "/", parsed.params, clean_query, "")
    return urlunparse(clean_parts)


def extract_links(raw_html: str, base_url: str, restrict_domain: Optional[str] = None) -> List[str]:
    """Extract and normalize all HTTP/HTTPS links from HTML."""
    discovered: Set[str] = set()
    soup = BeautifulSoup(raw_html, "lxml")

    base_domain = restrict_domain or urlparse(base_url).netloc.lower()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue

        absolute_url = urljoin(base_url, href)
        parsed = urlparse(absolute_url)

        if parsed.scheme not in ("http", "https"):
            continue

        # If domain restriction is active, ensure same domain or subdomain
        target_domain = parsed.netloc.lower()
        if restrict_domain:
            if target_domain != base_domain and not target_domain.endswith("." + base_domain):
                continue

        # Skip obvious non-HTML media files
        if parsed.path.lower().endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".zip", ".tar", ".gz", ".mp4", ".css", ".js")
        ):
            continue

        discovered.add(clean_url(absolute_url))

    return sorted(list(discovered))


def clean_html_text(raw_text_or_html: Optional[str]) -> str:
    """Remove HTML tags and collapse whitespace."""
    if not raw_text_or_html:
        return ""
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", raw_text_or_html)
    # Unescape HTML entities
    text = html.unescape(text)
    # Collapse multiple whitespace/newlines
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_json_ld(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Find and parse all JSON-LD script tags."""
    records: List[Dict[str, Any]] = []
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            payload = json.loads(script.string.strip())
            if isinstance(payload, list):
                records.extend(payload)
            elif isinstance(payload, dict):
                # Handle @graph schemas
                if "@graph" in payload and isinstance(payload["@graph"], list):
                    records.extend(payload["@graph"])
                else:
                    records.append(payload)
        except Exception:
            continue
    return records


def extract_job_from_schema(data: Dict[str, Any], page_url: str) -> Optional[JobPost]:
    """Convert Schema.org JobPosting dictionary into a normalized JobPost if it matches SWE criteria."""
    schema_type = data.get("@type")
    if not schema_type:
        return None

    # Handle single string or list of types
    types = [schema_type] if isinstance(schema_type, str) else schema_type
    if not any("JobPosting" in str(t) for t in types):
        return None

    title = data.get("title") or data.get("name")
    if not title or not isinstance(title, str):
        return None

    raw_desc = data.get("description", "")
    clean_desc = clean_html_text(raw_desc)

    # Relevance check: Is this a Software Engineering role?
    if not is_swe_role(title, clean_desc):
        return None

    # Company extraction
    company = "Unknown"
    org = data.get("hiringOrganization")
    if isinstance(org, dict):
        company = org.get("name", "Unknown")
    elif isinstance(org, str):
        company = org

    # Location extraction
    location_parts = []
    job_loc = data.get("jobLocation")
    if isinstance(job_loc, dict):
        addr = job_loc.get("address")
        if isinstance(addr, dict):
            for field in ["addressLocality", "addressRegion", "addressCountry"]:
                if addr.get(field):
                    location_parts.append(str(addr[field]))
        elif isinstance(addr, str):
            location_parts.append(addr)
    elif isinstance(job_loc, list):
        for loc in job_loc:
            if isinstance(loc, dict) and "address" in loc:
                location_parts.append(str(loc["address"]))

    location_str = ", ".join(location_parts) if location_parts else "Unspecified"

    # Remote detection
    job_location_type = str(data.get("jobLocationType", "")).upper()
    is_remote = "TELECOMMUTE" in job_location_type or detect_is_remote(location_str, title, clean_desc)

    # Salary extraction
    salary_min = None
    salary_max = None
    salary_curr = None
    base_sal = data.get("baseSalary")
    if isinstance(base_sal, dict):
        salary_curr = base_sal.get("currency")
        val = base_sal.get("value")
        if isinstance(val, dict):
            salary_min = val.get("minValue") or val.get("value")
            salary_max = val.get("maxValue") or val.get("value")
        elif isinstance(val, (int, float)):
            salary_min = float(val)

    # Tech stack extraction
    full_text = f"{title}\n{clean_desc}"
    tech_stack = extract_tech_stack(full_text)

    # Experience level
    experience_level = detect_experience_level(title, clean_desc)

    # Source domain
    source_domain = urlparse(page_url).netloc.lower()

    return JobPost(
        url=data.get("url") or page_url,
        source_domain=source_domain,
        title=title.strip(),
        company=str(company).strip(),
        location=location_str.strip() or "Unspecified",
        is_remote=is_remote,
        employment_type=str(data.get("employmentType")) if data.get("employmentType") else "Full-time",
        experience_level=experience_level,
        tech_stack=tech_stack,
        salary_min=float(salary_min) if salary_min else None,
        salary_max=float(salary_max) if salary_max else None,
        salary_currency=salary_curr,
        description_text=clean_desc[:4000] if clean_desc else None,
        date_posted=str(data.get("datePosted")) if data.get("datePosted") else None,
        raw_metadata={"schema_org": data},
    )


def parse_jobs_from_html(raw_html: str, page_url: str) -> List[JobPost]:
    """Universal parser that extracts software engineering jobs from HTML via Schema.org or DOM patterns."""
    soup = BeautifulSoup(raw_html, "lxml")
    jobs: List[JobPost] = []

    # 1. Primary Strategy: Schema.org JobPosting JSON-LD
    json_ld_schemas = parse_json_ld(soup)
    for schema in json_ld_schemas:
        job = extract_job_from_schema(schema, page_url)
        if job:
            jobs.append(job)

    if jobs:
        return jobs

    # 2. Secondary Strategy: Page-Level Meta Tags (if this page is a single job post)
    page_title = soup.title.string.strip() if soup.title and soup.title.string else ""
    if page_title and is_swe_role(page_title):
        # Extract main body text
        main_body = ""
        for tag in ["main", "article", "[role='main']", "#content", ".job-description", ".content"]:
            elem = soup.select_one(tag)
            if elem:
                main_body = clean_html_text(elem.get_text())
                break
        if not main_body and soup.body:
            main_body = clean_html_text(soup.body.get_text())

        full_text = f"{page_title}\n{main_body}"
        tech_stack = extract_tech_stack(full_text)
        is_remote = detect_is_remote(None, page_title, main_body)
        domain = urlparse(page_url).netloc.lower()

        jobs.append(
            JobPost(
                url=page_url,
                source_domain=domain,
                title=page_title,
                company=domain.split(".")[0].capitalize(),
                location="Remote" if is_remote else "Unspecified",
                is_remote=is_remote,
                experience_level=detect_experience_level(page_title, main_body),
                tech_stack=tech_stack,
                description_text=main_body[:3000] if main_body else None,
                raw_metadata={"strategy": "dom_meta_fallback"},
            )
        )

    return jobs
