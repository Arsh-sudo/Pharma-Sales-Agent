"""
Discovery Agent
═══════════════
Scrapes TenderTiger, IndiaMart, and Google News for pharma companies.
Deduplicates against SQLite and returns up to MAX_COMPANIES new entries.

Exposed as a LangChain @tool so the Orchestrator agent can call it naturally.
"""
import json
import logging
import random
import re
import time
from typing import Any

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sleep() -> None:
    """Polite random delay between HTTP requests."""
    time.sleep(random.uniform(SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX))


def _get(url: str) -> BeautifulSoup | None:
    """GET a URL and return a BeautifulSoup object, or None on failure."""
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as exc:
        logger.warning("GET failed for %s: %s", url, exc)
        return None


def _is_pharma(text: str) -> bool:
    """Return True if any pharma keyword appears in text (case-insensitive)."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in PHARMA_KEYWORDS)


def _clean_name(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip()).title()


def _extract_domain(url: str) -> str:
    """Try to extract bare domain from a URL."""
    match = re.search(r"https?://(?:www\.)?([^/\s]+)", url)
    return match.group(1) if match else ""


# ── Source scrapers ───────────────────────────────────────────────────────────

def _scrape_tendertiger() -> list[dict]:
    """
    Scrape TenderTiger search results for pharmaceutical tenders.
    Returns list of {'name': ..., 'website': ..., 'source': 'tendertiger'}.
    """
    results: list[dict] = []
    search_terms = ["pharmaceutical", "medicine", "drug", "API formulation"]

    for term in search_terms:
        url = f"https://www.tendertiger.net/tender/search-tenders.aspx?key={term.replace(' ', '+')}"
        soup = _get(url)
        if not soup:
            continue

        # TenderTiger tender listing — adjust selectors if their HTML changes
        # Primary: rows in the results table
        for row in soup.select("table.tenderlist tr, div.tender-row, li.tender-item"):
            name_el = (
                row.select_one(".org-name, .company, td:nth-child(3)")
            )
            if not name_el:
                continue

            raw_name = name_el.get_text(strip=True)
            if not raw_name or len(raw_name) < 4:
                continue

            # Only keep pharma-relevant entries
            row_text = row.get_text(" ", strip=True)
            if not _is_pharma(row_text) and not _is_pharma(raw_name):
                continue

            link_el = row.select_one("a[href]")
            website = link_el["href"] if link_el else ""
            if website.startswith("/"):
                website = "https://www.tendertiger.net" + website

            results.append({
                "name":    _clean_name(raw_name),
                "website": website,
                "source":  "tendertiger",
            })

        _sleep()

    logger.info("TenderTiger yielded %d raw results", len(results))
    return results


def _scrape_indiamart() -> list[dict]:
    """
    Scrape IndiaMart supplier listings for pharmaceutical companies.
    Returns list of {'name': ..., 'website': ..., 'source': 'indiamart'}.
    """
    results: list[dict] = []
    categories = [
        "pharmaceutical-drugs",
        "pharmaceutical-machinery",
        "active-pharmaceutical-ingredients",
    ]

    for cat in categories:
        url = f"https://dir.indiamart.com/industry/{cat}.html"
        soup = _get(url)
        if not soup:
            continue

        # IndiaMart company cards
        for card in soup.select(
            "div.company-name, div.companyName, h2.name a, "
            "div.listing-card .title, li.supplier-name"
        ):
            raw_name = card.get_text(strip=True)
            if not raw_name or len(raw_name) < 4:
                continue

            website = ""
            if card.name == "a" and card.get("href"):
                website = card["href"]
            elif card.find("a"):
                website = card.find("a").get("href", "")

            results.append({
                "name":    _clean_name(raw_name),
                "website": website,
                "source":  "indiamart",
            })

        _sleep()

    logger.info("IndiaMart yielded %d raw results", len(results))
    return results


def _scrape_google_news() -> list[dict]:
    """
    Pull pharma company names from Google News RSS.
    Returns list of {'name': ..., 'website': '', 'source': 'news'}.
    """
    results: list[dict] = []
    queries = [
        "new pharmaceutical company India",
        "pharma company expansion India",
        "pharmaceutical manufacturer registered India",
    ]

    # Company name patterns in news headlines
    company_pattern = re.compile(
        r"\b([A-Z][a-zA-Z&\s]{3,40}(?:Pharma|Pharmaceuticals?|Biotech|"
        r"Biosciences?|Labs?|Life\s*Sciences?|Drugs?|Healthcare|Remedies|"
        r"Formulations?))\b"
    )

    for q in queries:
        url = (
            "https://news.google.com/rss/search?q="
            + q.replace(" ", "+")
            + "&hl=en-IN&gl=IN&ceid=IN:en"
        )
        soup = _get(url)
        if not soup:
            continue

        for item in soup.select("item"):
            text = item.get_text(" ", strip=True)
            for match in company_pattern.finditer(text):
                name = _clean_name(match.group(1))
                results.append({"name": name, "website": "", "source": "news"})

        _sleep()

    logger.info("Google News yielded %d raw results", len(results))
    return results


# ── Deduplication + Normalisation ─────────────────────────────────────────────

def _deduplicate(raw: list[dict]) -> list[dict]:
    """
    1. Remove entries already in SQLite (previously processed).
    2. Remove duplicates within this batch (by normalised name).
    """
    seen_names: set[str] = set()
    clean: list[dict] = []

    for entry in raw:
        name = entry.get("name", "").strip()
        if not name:
            continue

        norm = name.lower()
        if norm in seen_names:
            continue
        if is_company_processed(name):
            logger.debug("Skipping already-processed: %s", name)
            continue

        seen_names.add(norm)
        clean.append(entry)

    return clean


# ── LangChain Tool ────────────────────────────────────────────────────────────

@tool
def discover_pharma_companies(dummy_input: str = "") -> str:
    """
    Scrape TenderTiger, IndiaMart, and Google News to discover new pharma
    companies that have not been processed before.

    Returns a JSON string — a list of dicts with keys:
      name (str), website (str), source (str)
    Up to MAX_COMPANIES entries.

    Call this tool with no arguments (or an empty string).
    """
    init_sqlite()

    raw: list[dict] = []
    raw.extend(_scrape_tendertiger())
    raw.extend(_scrape_indiamart())
    raw.extend(_scrape_google_news())

    new_companies = _deduplicate(raw)[:MAX_COMPANIES]

    # Mark all as processed immediately to prevent re-processing if pipeline
    # is interrupted and re-run on the same day
    for company in new_companies:
        mark_company_processed(company["name"], company.get("website", ""))

    logger.info(
        "Discovery complete: %d new companies (from %d raw results)",
        len(new_companies), len(raw),
    )

    return json.dumps(new_companies, ensure_ascii=False)
