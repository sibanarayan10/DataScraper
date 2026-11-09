"""Classification and extraction utilities for Software Engineering jobs."""

import re
from typing import List, Optional, Set
from config import DISQUALIFYING_TITLE_KEYWORDS, SWE_TITLE_KEYWORDS, TECH_STACK_KEYWORDS

# Precompiled regex for experience levels
EXPERIENCE_PATTERNS = [
    (re.compile(r"\b(intern|internship|co-op)\b", re.IGNORECASE), "Intern"),
    (re.compile(r"\b(junior|jr\.?|entry[- ]level|associate)\b", re.IGNORECASE), "Junior"),
    (re.compile(r"\b(staff|principal|distinguished)\b", re.IGNORECASE), "Staff/Principal"),
    (re.compile(r"\b(lead|tech lead|team lead|head of|manager|director)\b", re.IGNORECASE), "Lead/Manager"),
    (re.compile(r"\b(senior|sr\.?)\b", re.IGNORECASE), "Senior"),
    (re.compile(r"\b(mid|intermediate)\b", re.IGNORECASE), "Mid"),
]

# Remote keywords
REMOTE_PATTERN = re.compile(r"\b(remote|work from home|wfh|anywhere|telecommute|distributed)\b", re.IGNORECASE)


def is_swe_role(title: str, description: Optional[str] = None) -> bool:
    """Determine if a job title (and optional description) qualifies as a Software Engineering role."""
    title_lower = title.lower()

    # 1. Immediate disqualification if strong non-tech keywords are present
    for bad_kw in DISQUALIFYING_TITLE_KEYWORDS:
        # Check as whole word match
        if re.search(rf"\b{re.escape(bad_kw)}\b", title_lower):
            # Exception if title explicitly says e.g. "Software Engineer - Sales Tech"
            if not any(good_kw in title_lower for good_kw in ["software engineer", "developer"]):
                return False

    # 2. Check for positive SWE title keywords
    for good_kw in SWE_TITLE_KEYWORDS:
        if good_kw in title_lower:
            return True

    # 3. Fallback: if description has high density of engineering tech keywords
    if description:
        desc_sample = description[:1500].lower()
        core_tokens = ["programming", "codebase", "git", "api", "software development"]
        matches = sum(1 for token in core_tokens if token in desc_sample)
        if matches >= 2 and any(term in title_lower for term in ["engineer", "developer", "architect", "programmer"]):
            return True

    return False


def detect_experience_level(title: str, text: Optional[str] = None) -> str:
    """Detect experience level (Junior, Mid, Senior, Lead, etc.) from title or text."""
    # Check title first (most authoritative)
    for pattern, level in EXPERIENCE_PATTERNS:
        if pattern.search(title):
            return level

    # Check text if available
    if text:
        first_chunk = text[:1000]
        for pattern, level in EXPERIENCE_PATTERNS:
            if pattern.search(first_chunk):
                return level

    return "Mid/Unspecified"


def detect_is_remote(location: Optional[str], title: Optional[str] = None, text: Optional[str] = None) -> bool:
    """Check if the role is Remote based on location, title, or description."""
    if location and REMOTE_PATTERN.search(location):
        return True
    if title and REMOTE_PATTERN.search(title):
        return True
    if text and REMOTE_PATTERN.search(text[:500]):
        return True
    return False


def extract_tech_stack(text: str) -> List[str]:
    """Scan job title and description to extract referenced programming languages, frameworks, and tools."""
    found: Set[str] = set()
    if not text:
        return []

    # Check each tech keyword with word boundaries
    for tech in TECH_STACK_KEYWORDS:
        # Special case for C++ and C#
        if tech in ("C++", "C#"):
            escaped = re.escape(tech)
            pattern = rf"(?:^|[\s,;/]){escaped}(?:[\s,;/]|$)"
        elif tech == "Go" or tech == "Golang":
            pattern = r"\b(golang|go\s+language|go\s+developer|go\s+backend)\b"
        elif tech == "R":
            pattern = r"\b(r\s+language|r\s+programming)\b"
        else:
            pattern = rf"\b{re.escape(tech)}\b"

        if re.search(pattern, text, re.IGNORECASE):
            found.add(tech)

    # Normalize 'Golang' to 'Go'
    if "Golang" in found:
        found.discard("Golang")
        found.add("Go")

    return sorted(list(found))
