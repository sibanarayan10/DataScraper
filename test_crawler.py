"""Unit and integration tests for classifier, parser, and database."""

import json
from datetime import datetime
from pathlib import Path

from classifier import (
    detect_experience_level,
    detect_is_remote,
    extract_tech_stack,
    is_swe_role,
)
from database import Database
from models import JobPost
from parser import clean_url, extract_links, parse_jobs_from_html


def test_is_swe_role():
    assert is_swe_role("Senior Backend Engineer") is True
    assert is_swe_role("Staff Full Stack Developer") is True
    assert is_swe_role("DevOps / Site Reliability Engineer") is True
    assert is_swe_role("Machine Learning Engineer") is True
    assert is_swe_role("iOS Developer") is True

    # Negative tests
    assert is_swe_role("Account Executive - Enterprise Sales") is False
    assert is_swe_role("Registered Nurse") is False
    assert is_swe_role("Head of Human Resources") is False


def test_experience_and_remote():
    assert detect_experience_level("Senior Python Developer") == "Senior"
    assert detect_experience_level("Junior Frontend Engineer") == "Junior"
    assert detect_experience_level("Lead DevOps Engineer") == "Lead/Manager"
    assert detect_experience_level("Software Engineering Intern") == "Intern"

    assert detect_is_remote("Remote, US") is True
    assert detect_is_remote("New York, NY", title="Software Engineer (Remote)") is True
    assert detect_is_remote("San Francisco, CA") is False


def test_extract_tech_stack():
    text = (
        "We are looking for a Senior Backend Engineer proficient in Python, "
        "PostgreSQL, Docker, and Kubernetes with experience deploying to AWS."
    )
    stack = extract_tech_stack(text)
    assert "Python" in stack
    assert "PostgreSQL" in stack
    assert "Docker" in stack
    assert "Kubernetes" in stack
    assert "AWS" in stack


def test_clean_url_and_links():
    raw_url = "https://example.com/jobs/123/?utm_source=twitter&utm_medium=social&ref=feed#apply"
    cleaned = clean_url(raw_url)
    assert "utm_source" not in cleaned
    assert "#apply" not in cleaned
    assert cleaned == "https://example.com/jobs/123"

    sample_html = """
    <html>
        <body>
            <a href="/jobs/swe-1">Job 1</a>
            <a href="https://example.com/jobs/swe-2">Job 2</a>
            <a href="mailto:info@example.com">Email</a>
            <a href="https://otherdomain.com/ad">External</a>
        </body>
    </html>
    """
    links = extract_links(sample_html, "https://example.com", restrict_domain="example.com")
    assert "https://example.com/jobs/swe-1" in links
    assert "https://example.com/jobs/swe-2" in links
    assert not any("mailto" in l for l in links)
    assert not any("otherdomain.com" in l for l in links)


def test_schema_org_job_posting_parsing():
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": "Lead Software Engineer - Python",
            "hiringOrganization": {
                "@type": "Organization",
                "name": "Acme Tech"
            },
            "jobLocation": {
                "@type": "Place",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": "San Francisco",
                    "addressRegion": "CA"
                }
            },
            "jobLocationType": "TELECOMMUTE",
            "description": "We need a lead engineer with expertise in Python, FastAPI, React, and AWS.",
            "datePosted": "2026-11-01"
        }
        </script>
    </head>
    <body><h1>Job Details</h1></body>
    </html>
    """
    jobs = parse_jobs_from_html(sample_html, "https://acme.com/jobs/1")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Lead Software Engineer - Python"
    assert job.company == "Acme Tech"
    assert job.is_remote is True
    assert "Python" in job.tech_stack
    assert "FastAPI" in job.tech_stack
    assert "React" in job.tech_stack
    assert "AWS" in job.tech_stack
    assert job.experience_level == "Lead/Manager"


def test_database_crud(tmp_path: Path):
    db_file = tmp_path / "test_jobs.db"
    db = Database(db_file)

    # Test enqueue
    assert db.enqueue_url("https://example.com/careers", depth=0) is True
    assert db.enqueue_url("https://example.com/careers", depth=0) is False  # Duplicate

    pending = db.get_pending_urls(limit=5)
    assert len(pending) == 1
    assert pending[0].url == "https://example.com/careers"

    # Test save job
    job = JobPost(
        url="https://example.com/jobs/dev-1",
        source_domain="example.com",
        title="Senior Backend Engineer",
        company="Example Corp",
        location="Remote",
        is_remote=True,
        employment_type="Full-time",
        experience_level="Senior",
        tech_stack=["Python", "PostgreSQL"],
    )
    saved = db.save_job(job)
    assert saved is True

    # Query job
    results = db.fetch_jobs(limit=10, tech="Python")
    assert len(results) == 1
    assert results[0]["title"] == "Senior Backend Engineer"
    assert "Python" in results[0]["tech_stack"]

    stats = db.get_stats()
    assert stats["total_jobs"] == 1
    assert stats["remote_jobs"] == 1


if __name__ == "__main__":
    import tempfile
    print("Running test_is_swe_role()...")
    test_is_swe_role()
    print("Running test_experience_and_remote()...")
    test_experience_and_remote()
    print("Running test_extract_tech_stack()...")
    test_extract_tech_stack()
    print("Running test_clean_url_and_links()...")
    test_clean_url_and_links()
    print("Running test_schema_org_job_posting_parsing()...")
    test_schema_org_job_posting_parsing()
    print("Running test_database_crud()...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_database_crud(Path(tmp_dir))
    print("\n✓ ALL TESTS PASSED SUCCESSFULLY!")

