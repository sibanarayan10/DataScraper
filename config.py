"""Configuration settings and constants for the Software Engineering Job Scraper."""

from pathlib import Path
from typing import List, Set

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "jobs.db"
EXPORTS_DIR = BASE_DIR / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

# Crawler Settings
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT_SECONDS = 15
DEFAULT_CONCURRENCY = 3
RATE_LIMIT_DELAY_SECONDS = 1.0  # Politeness interval between requests per domain

# Software Engineering Keywords for Relevance Filtering
SWE_TITLE_KEYWORDS: List[str] = [
    "software engineer",
    "software developer",
    "backend",
    "frontend",
    "full stack",
    "fullstack",
    "devops",
    "site reliability",
    "sre",
    "platform engineer",
    "systems engineer",
    "cloud engineer",
    "data engineer",
    "machine learning",
    "ml engineer",
    "ai engineer",
    "mobile engineer",
    "ios developer",
    "ios engineer",
    "android developer",
    "android engineer",
    "embedded",
    "firmware",
    "security engineer",
    "qa engineer",
    "qa automation",
    "infrastructure engineer",
    "tech lead",
    "engineering manager",
]

# Keywords that disqualify a role if it's on a general career page
DISQUALIFYING_TITLE_KEYWORDS: List[str] = [
    "sales",
    "account executive",
    "marketing",
    "recruiter",
    "talent acquisition",
    "human resources",
    "customer support",
    "customer success",
    "finance",
    "accountant",
    "legal",
    "office manager",
    "nurse",
    "medical",
    "operations manager",
]

# Tech Stack Dictionary for Auto-Tagging
TECH_STACK_KEYWORDS: Set[str] = {
    # Languages
    "Python", "JavaScript", "TypeScript", "Go", "Golang", "Java", "C++", "C#", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "Elixir", "SQL",
    # Frameworks & Libraries
    "React", "Vue", "Angular", "Next.js", "Nuxt", "Svelte", "Node.js", "Express",
    "Django", "FastAPI", "Flask", "Spring Boot", "Rails", "Ruby on Rails", "ASP.NET",
    # Databases & Caching
    "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis", "Elasticsearch", "DynamoDB", "Cassandra",
    # Cloud & DevOps
    "AWS", "GCP", "Google Cloud", "Azure", "Docker", "Kubernetes", "Terraform", "CI/CD",
    "GitHub Actions", "Ansible", "Linux", "Prometheus", "Grafana",
    # AI / ML / Data
    "PyTorch", "TensorFlow", "Pandas", "NumPy", "Scikit-Learn", "Spark", "Kafka",
    # Concepts & Protocols
    "REST", "GraphQL", "gRPC", "Microservices", "Kafka"
}
