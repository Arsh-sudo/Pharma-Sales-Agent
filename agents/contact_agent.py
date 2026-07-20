"""
Contact Agent
═════════════
Given a company website:
  1. Navigates to the site with Playwright (handles JS-rendered pages)
  2. Hunts for Team / About / Contact pages
  3. Sends the cleaned HTML to Ollama Mistral for structured extraction
  4. Falls back to regex for emails missed by the LLM

Returns a JSON string — list of dicts: [{name, title, email, phone}]

Exposed as a LangChain @tool.
"""
import json
import logging
import re
import time
import random
from typing import Any

import requests
from bs4 import BeautifulSoup
from langchain.tools import tool
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from config.settings import OLLAMA_BASE_URL, OLLAMA_MODEL, REQUEST_HEADERS

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
TEAM_PAGE_KEYWORDS = [
    "team", "about", "about-us", "people", "leadership",
    "management", "contact", "staff", "founders", "board",
]

EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b"
)

PHONE_REGEX = re.compile(
    r"(?:\+?91[\-\s]?)?(?:\d{3,5}[\-\s]?\d{3,5}[\-\s]?\d{3,5})"
)

MAX_HTML_CHARS = 12_000   # trim HTML before sending to LLM
PLAYWRIGHT_TIMEOUT = 12_000   # ms


# ── HTML Cleaner ──────────────────────────────────────────────────────────────

def _strip_html(raw_html: str) -> str:
    """Remove script/style blocks and return visible text-rich HTML snippet."""
    soup = BeautifulSoup(raw_html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "img", "head"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    # Normalise whitespace
    text = re.sub(r"\s{2,}", " ", text)
    return text[:MAX_HTML_CHARS]


# ── Playwright Browser Navigation ─────────────────────────────────────────────

def _find_team_page(page, base_url: str) -> str:
    """
    Given a Playwright Page already loaded at base_url, try to navigate to
    a team/about/contact sub-page and return its HTML.
    Falls back to the homepage HTML if nothing found.
    """
    try:
        page.goto(base_url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")
        time.sleep(random.uniform(1.5, 2.5))
    except PWTimeout:
        logger.warning("Timeout loading %s", base_url)
        return ""

    # Try to find a nav link that matches team-page keywords
    for kw in TEAM_PAGE_KEYWORDS:
        locator = page.locator(
            f'a:has-text("{kw}"), a[href*="{kw}"]'
        ).first

        try:
            if locator.is_visible(timeout=1500):
                href = locator.get_attribute("href") or ""
                # Resolve relative URLs
                if href.startswith("/"):
                    href = base_url.rstrip("/") + href
                elif not href.startswith("http"):
                    href = base_url.rstrip("/") + "/" + href

                page.goto(href, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")
                time.sleep(random.uniform(1.0, 2.0))
                logger.info("Found team-page keyword '%s' at %s", kw, href)
                return page.content()
        except Exception:
            continue

    # Fallback: homepage content
    return page.content()


def _scrape_with_playwright(website: str) -> str:
    """Open website in headless Chromium and return cleaned text."""
    if not website.startswith("http"):
        website = "https://" + website

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            extra_http_headers=REQUEST_HEADERS,
            user_agent=REQUEST_HEADERS["User-Agent"],
        )
        page = context.new_page()

        html = _find_team_page(page, website)
        browser.close()

    return _strip_html(html)


# ── Ollama LLM Extraction ─────────────────────────────────────────────────────

EXTRACTION_PROMPT = """\
You are a data extraction assistant. I will give you text scraped from a \
company website. Extract every person mentioned along with their job title \
and email address. If no email is visible for a person, leave the field empty.

Return ONLY a valid JSON array and nothing else. No explanation, no markdown \
fences. Each element must have exactly these keys:
  "name"  — full name of the person (string)
  "title" — job title / designation (string, empty string if unknown)
  "email" — email address (string, empty string if not found)
  "phone" — phone number (string, empty string if not found)

If no people are found, return an empty array: []

Text to analyse:
\"\"\"
{text}
\"\"\"

JSON array:"""


def _call_ollama(text: str) -> list[dict]:
    """Send text to Ollama Mistral and parse the returned JSON array."""
    prompt = EXTRACTION_PROMPT.format(text=text)

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 1024},
            },
            timeout=60,
        )
        resp.raise_for_status()
        raw_response = resp.json().get("response", "").strip()
    except Exception as exc:
        logger.error("Ollama call failed: %s", exc)
        return []

    # Strip accidental markdown fences
    raw_response = re.sub(r"^```(?:json)?", "", raw_response).strip()
    raw_response = re.sub(r"```$", "", raw_response).strip()

    try:
        data = json.loads(raw_response)
        if isinstance(data, list):
            return data
        # Some models wrap in {"contacts": [...]}
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    return v
    except json.JSONDecodeError:
        logger.warning("Ollama returned invalid JSON: %s…", raw_response[:200])

    return []


# ── Regex Email Fallback ──────────────────────────────────────────────────────

def _regex_emails(text: str) -> list[dict]:
    """Extract emails via regex and return as minimal contact dicts."""
    emails = list(set(EMAIL_REGEX.findall(text)))
    # Filter obvious non-personal addresses
    skip = {"example.com", "domain.com", "email.com", "youremail"}
    emails = [e for e in emails if not any(s in e for s in skip)]
    return [{"name": "", "title": "", "email": e, "phone": ""} for e in emails]


# ── Merge & Deduplicate ───────────────────────────────────────────────────────

def _merge_contacts(llm_contacts: list[dict], regex_contacts: list[dict]) -> list[dict]:
    """
    Merge LLM-extracted and regex-extracted contacts.
    Prefer LLM results; add regex emails not already captured.
    """
    seen_emails = {c.get("email", "").lower() for c in llm_contacts if c.get("email")}

    extra = [
        r for r in regex_contacts
        if r["email"].lower() not in seen_emails
    ]
    merged = llm_contacts + extra

    # Remove completely empty records
    return [c for c in merged if c.get("name") or c.get("email")]


# ── LangChain Tool ────────────────────────────────────────────────────────────

@tool
def extract_contacts(company_input: str) -> str:
    """
    Given a company website URL (or 'company_name|||website_url'), visit the
    site using a headless browser, find the Team / About page, and extract
    all people with their names, titles, emails, and phone numbers.

    Input format (choose one):
      - A bare URL:                 "https://example-pharma.com"
      - Name + URL separated by |||: "Acme Pharma|||https://acmepharma.com"

    Returns a JSON string — list of contact dicts:
      [{"name": "...", "title": "...", "email": "...", "phone": "..."}]
    """
    # Parse input
    if "|||" in company_input:
        parts = company_input.split("|||", 1)
        company_name = parts[0].strip()
        website = parts[1].strip()
    else:
        company_name = ""
        website = company_input.strip()

    if not website:
        logger.warning("extract_contacts called with no website.")
        return json.dumps([])

    logger.info("Extracting contacts from: %s", website)

    # 1. Scrape with Playwright
    try:
        page_text = _scrape_with_playwright(website)
    except Exception as exc:
        logger.error("Playwright scrape failed for %s: %s", website, exc)
        page_text = ""

    if not page_text:
        return json.dumps([])

    # 2. LLM extraction
    llm_contacts = _call_ollama(page_text)
    logger.info("LLM extracted %d contacts for %s", len(llm_contacts), website)

    # 3. Regex fallback for emails
    regex_contacts = _regex_emails(page_text)

    # 4. Merge
    contacts = _merge_contacts(llm_contacts, regex_contacts)
    logger.info(
        "Final contact count for %s: %d",
        company_name or website, len(contacts),
    )

    return json.dumps(contacts, ensure_ascii=False)
