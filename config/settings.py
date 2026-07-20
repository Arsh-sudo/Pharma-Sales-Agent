"""
Central configuration — loaded from .env
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Neo4j ─────────────────────────────────────────────────────────────────────
NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "mistral")

# ── Pipeline ──────────────────────────────────────────────────────────────────
MAX_COMPANIES  = int(os.getenv("MAX_COMPANIES_PER_RUN", "10"))
OUTPUT_DIR     = Path(os.getenv("OUTPUT_DIR", "./output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Scraping ──────────────────────────────────────────────────────────────────
PHARMA_KEYWORDS = [
    "pharmaceutical", "pharma", "drug", "medicine", "API",
    "formulation", "biotech", "vaccine", "CRO", "clinical",
    "dosage", "tablet", "capsule", "injection", "bulk drug",
]

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT  = 15   # seconds
SCRAPE_DELAY_MIN = 2.0  # seconds between requests
SCRAPE_DELAY_MAX = 5.0

# ── SQLite (deduplication) ────────────────────────────────────────────────────
SQLITE_PATH = "./pharma_pipeline.db"
