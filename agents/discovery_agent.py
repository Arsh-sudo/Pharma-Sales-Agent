"""
Discovery Agent — Fixed Version
════════════════════════════════
Sources:
  1. Google News RSS  — with strict company-name filtering (not headlines)
  2. TenderTiger      — scrapes tender listings
  3. IndiaMart        — scrapes supplier listings
  4. Fallback seed list — well-known Indian pharma companies with websites

Key fixes vs v1:
  - Google News regex tightened to reject headline-style extractions
  - Minimum name quality checks (no verbs, no stopwords, min 2 words)
  - Company blocklist for known false positives
  - Seed list ensures the pipeline always has real companies with websites
"""
import json
import logging
import random
import re
import time
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from langchain.tools import tool

from config.settings import (
    MAX_COMPANIES,
    PHARMA_KEYWORDS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    SCRAPE_DELAY_MIN,
    SCRAPE_DELAY_MAX,
)
from utils.db import init_sqlite, is_company_processed, mark_company_processed

logger = logging.getLogger(__name__)

# ── Blocklist: words/phrases that indicate a headline, not a company name ──────
HEADLINE_WORDS = {
    "how", "why", "what", "when", "where", "rise", "fall", "top", "best",
    "global", "india", "invites", "defining", "registering", "takes", "ai",
    "lakh", "crore", "trillion", "companies", "the companies", "new", "report",
    "update", "analysis", "announces", "launches", "expands", "growth",
}

# Suffix patterns that indicate a real company name
COMPANY_SUFFIXES = re.compile(
    r"\b(Pharma(?:ceuticals?)?|Biotech|Biosciences?|Labs?|"
    r"Life\s*Sciences?|Drugs?|Healthcare|Remedies|Formulations?|"
    r"Meditech|Medicals?|Biologics?|Therapeutics?|Lifesciences?|"
    r"Industries|Enterprises|Limited|Ltd\.?|Pvt\.?|Inc\.?)\b",
    re.IGNORECASE,
)

# ── Seed list: real Indian pharma companies with verified websites ─────────────
# Used when scraping yields few results. Each has a known website for
# contact extraction to work on.
SEED_COMPANIES = [
    {"name": "Cipla Ltd",           "website": "https://www.cipla.com",         "source": "seed"},
    {"name": "Dr Reddys Laboratories","website": "https://www.drreddys.com",    "source": "seed"},
    {"name": "Lupin Pharmaceuticals", "website": "https://www.lupin.com",       "source": "seed"},
    {"name": "Aurobindo Pharma",      "website": "https://www.aurobindo.com",   "source": "seed"},
    {"name": "Cadila Healthcare",     "website": "https://www.zyduslife.com",   "source": "seed"},
    {"name": "Torrent Pharmaceuticals","website": "https://www.torrentpharma.com","source": "seed"},
    {"name": "Alkem Laboratories",    "website": "https://www.alkemlabs.com",   "source": "seed"},
    {"name": "Mankind Pharma",        "website": "https://www.mankindpharma.com","source": "seed"},
    {"name": "Glenmark Pharmaceuticals","website": "https://www.glenmarkpharma.com","source": "seed"},
    {"name": "Ipca Laboratories",     "website": "https://www.ipca.com",        "source": "seed"},
    {"name": "Abbott India",          "website": "https://www.abbott.co.in",    "source": "seed"},
    {"name": "Pfizer India",          "website": "https://www.pfizerindia.com", "source": "seed"},
    {"name": "Sanofi India",          "website": "https://www.sanofi.com",      "source": "seed"},
    {"name": "Novartis India",        "website": "https://www.novartis.in",     "source": "seed"},
    {"name": "Wockhardt Ltd",         "website": "https://www.wockhardt.com",   "source": "seed"},
    {"name": "Strides Pharma",        "website": "https://www.strides.com",     "source": "seed"},
    {"name": "Jubilant Pharmova",     "website": "https://www.jubilantpharmova.com","source": "seed"},
    {"name": "Granules India",        "website": "https://www.granulesindia.com","source": "seed"},
    {"name": "Suven Pharmaceuticals", "website": "https://www.suven.com",       "source": "seed"},
    {"name": "Eris Lifesciences",     "website": "https://www.erislifesciences.com","source": "seed"},
]


def _sleep() -> None:
    time.sleep(random.uniform(SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX))


def _get(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as exc:
        logger.warning("GET failed for %s: %s", url, exc)
        return None


def _is_pharma(text: str) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in PHARMA_KEYWORDS)


def _clean_name(raw: str) -> str:
    name = re.sub(r"\s+", " ", raw.strip()).title()
    # Remove trailing punctuation
    name = name.strip(".,;:-–—")
    return name


def _is_valid_company_name(name: str) -> bool:
    """
    Return True only if the string looks like a real company name:
      - At least 2 words
      - Contains a company-style suffix (Pharma, Ltd, Labs, etc.)
      - Does not start with a headline word
      - Not too long (headline sentences are long)
    """
    if not name or len(name) < 6 or len(name) > 60:
        return False

    words = name.lower().split()
    if len(words) < 2:
        return False

    # Reject if starts with a known headline/non-company word
    if words[0] in HEADLINE_WORDS:
        return False

    # Reject if more than 5 words (likely a headline phrase)
    if len(words) > 5:
        return False

    # Must contain a recognisable company suffix
    if not COMPANY_SUFFIXES.search(name):
        return False

    return True


# ── Source: Google News RSS ────────────────────────────────────────────────────

def _scrape_google_news() -> list[dict]:
    results: list[dict] = []
    queries = [
        "pharmaceutical company India new",
        "pharma manufacturer India",
        "drug company India IPO",
    ]

    # Match only proper company names — must end with a known suffix
    company_pattern = re.compile(
        r"\b([A-Z][A-Za-z&\s\.]{2,35}"
        r"(?:Pharma(?:ceuticals?)?|Biotech|Biosciences?|Labs?|"
        r"Life\s*Sciences?|Drugs?|Healthcare|Remedies|Formulations?|"
        r"Meditech|Medicals?|Biologics?|Therapeutics?|Limited|Ltd\.?))"
        r"\b"
    )

    for q in queries:
        url = (
            "https://news.google.com/rss/search?q="
            + quote_plus(q)
            + "&hl=en-IN&gl=IN&ceid=IN:en"
        )
        soup = _get(url)
        if not soup:
            continue

        for item in soup.select("item"):
            text = item.get_text(" ", strip=True)
            for match in company_pattern.finditer(text):
                name = _clean_name(match.group(1))
                if _is_valid_company_name(name):
                    results.append({"name": name, "website": "", "source": "news"})

        _sleep()

    logger.info("Google News yielded %d raw results", len(results))
    return results


# ── Source: TenderTiger ────────────────────────────────────────────────────────

def _scrape_tendertiger() -> list[dict]:
    results: list[dict] = []
    for term in ["pharmaceutical", "medicine"]:
        url = f"https://www.tendertiger.net/search?q={term}"
        soup = _get(url)
        if not soup:
            continue
        for row in soup.select("table tr, .tender-item, .result-row"):
            cells = row.find_all("td")
            for cell in cells:
                raw = cell.get_text(strip=True)
                name = _clean_name(raw)
                if _is_valid_company_name(name) and _is_pharma(name):
                    link = cell.find("a", href=True)
                    website = link["href"] if link else ""
                    results.append({"name": name, "website": website, "source": "tendertiger"})
        _sleep()
    logger.info("TenderTiger yielded %d raw results", len(results))
    return results


# ── Source: IndiaMart ─────────────────────────────────────────────────────────

def _scrape_indiamart() -> list[dict]:
    results: list[dict] = []
    url = "https://dir.indiamart.com/industry/pharmaceutical-drugs.html"
    soup = _get(url)
    if soup:
        for card in soup.select("div.company-name, h2.name a, .listing-card .title"):
            raw = card.get_text(strip=True)
            name = _clean_name(raw)
            if _is_valid_company_name(name):
                link = card.find("a", href=True) if card.name != "a" else card
                website = link["href"] if link and link.get("href") else ""
                results.append({"name": name, "website": website, "source": "indiamart"})
        _sleep()
    logger.info("IndiaMart yielded %d raw results", len(results))
    return results


# ── Deduplication ─────────────────────────────────────────────────────────────

def _deduplicate(raw: list[dict]) -> list[dict]:
    seen: set[str] = set()
    clean: list[dict] = []
    for entry in raw:
        name = entry.get("name", "").strip()
        if not name:
            continue
        norm = name.lower()
        if norm in seen or is_company_processed(name):
            continue
        seen.add(norm)
        clean.append(entry)
    return clean


# ── Fill with seeds if not enough scraped companies ───────────────────────────

def _fill_with_seeds(companies: list[dict], target: int) -> list[dict]:
    """
    If scraping yielded fewer than target companies, top up from SEED_COMPANIES
    (skipping any already processed).
    """
    if len(companies) >= target:
        return companies

    logger.info(
        "Only %d scraped companies — filling remainder from seed list", len(companies)
    )
    for seed in SEED_COMPANIES:
        if len(companies) >= target:
            break
        name = seed["name"]
        norm = name.lower()
        already = any(c["name"].lower() == norm for c in companies)
        if already or is_company_processed(name):
            continue
        companies.append(seed)

    return companies


# ── LangChain Tool ────────────────────────────────────────────────────────────

@tool
def discover_pharma_companies(dummy_input: str = "") -> str:
    """
    Discover new pharma companies from public sources (TenderTiger, IndiaMart,
    Google News) plus a seed list of verified Indian pharma companies.
    Returns JSON list of {name, website, source}. Up to MAX_COMPANIES entries.
    Call with no arguments.
    """
    init_sqlite()

    raw: list[dict] = []
    raw.extend(_scrape_tendertiger())
    raw.extend(_scrape_indiamart())
    raw.extend(_scrape_google_news())

    new_companies = _deduplicate(raw)

    # Always ensure we have real companies with websites
    new_companies = _fill_with_seeds(new_companies, MAX_COMPANIES)
    new_companies = new_companies[:MAX_COMPANIES]

    for company in new_companies:
        mark_company_processed(company["name"], company.get("website", ""))

    logger.info(
        "Discovery complete: %d new companies (from %d raw + seeds)",
        len(new_companies), len(raw),
    )
    return json.dumps(new_companies, ensure_ascii=False)
