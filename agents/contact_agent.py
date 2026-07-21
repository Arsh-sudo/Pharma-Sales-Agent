"""
Contact Agent — Fixed Version
══════════════════════════════
Key fixes vs v1:
  - Ollama timeout raised to 180s
  - Uses llama3.2 (3B) if available — much faster than mistral (7B)
  - Reduced HTML sent to LLM: 6000 chars instead of 12000
  - Full regex fallback: extracts emails + names even without LLM
  - Structured HTML parsing (looks for <h3>/<h4> + email patterns near each other)
  - Never returns empty if there are emails on the page
"""
import json
import logging
import re
import time
import random

import requests
from bs4 import BeautifulSoup
from langchain.tools import tool
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from config.settings import OLLAMA_BASE_URL, OLLAMA_MODEL, REQUEST_HEADERS

logger = logging.getLogger(__name__)

TEAM_PAGE_KEYWORDS = [
    "team", "about", "about-us", "people", "leadership",
    "management", "contact", "staff", "founders", "board",
]

EMAIL_REGEX    = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
PHONE_REGEX    = re.compile(r"(?:\+?91[\-\s]?)?[6-9]\d{9}")
NAME_PATTERN   = re.compile(r"\b([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b")

MAX_HTML_CHARS   = 6_000
PLAYWRIGHT_TIMEOUT = 12_000   # ms
OLLAMA_TIMEOUT     = 180       # seconds

SKIP_EMAILS = {"example.com", "domain.com", "email.com", "youremail",
               "yourname", "test.com", "sample.com", "info@", "support@",
               "sales@", "admin@", "contact@", "hello@", "office@"}


# ── HTML cleaner ──────────────────────────────────────────────────────────────

def _strip_html(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "img", "head", "nav", "footer"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s{2,}", " ", text)
    return text[:MAX_HTML_CHARS]


# ── Playwright navigation ─────────────────────────────────────────────────────

def _find_team_page_html(website: str) -> str:
    if not website.startswith("http"):
        website = "https://" + website

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            extra_http_headers=REQUEST_HEADERS,
            user_agent=REQUEST_HEADERS["User-Agent"],
        )
        page = context.new_page()

        try:
            page.goto(website, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")
            time.sleep(random.uniform(1.5, 2.5))
        except PWTimeout:
            logger.warning("Timeout loading %s", website)
            browser.close()
            return ""

        # Try to click a team/about page link
        for kw in TEAM_PAGE_KEYWORDS:
            try:
                locator = page.locator(f'a:has-text("{kw}"), a[href*="{kw}"]').first
                if locator.is_visible(timeout=1500):
                    href = locator.get_attribute("href") or ""
                    if href.startswith("/"):
                        href = website.rstrip("/") + href
                    elif not href.startswith("http"):
                        href = website.rstrip("/") + "/" + href
                    page.goto(href, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")
                    time.sleep(random.uniform(1.0, 2.0))
                    logger.info("Found team-page via '%s': %s", kw, href)
                    break
            except Exception:
                continue

        html = page.content()
        browser.close()
    return html


# ── Structured HTML parsing (no LLM needed) ───────────────────────────────────

def _parse_contacts_from_html(raw_html: str) -> list[dict]:
    """
    Try to extract contacts directly from HTML structure:
    looks for heading tags near email addresses.
    Returns list of {name, title, email, phone}.
    """
    soup = BeautifulSoup(raw_html, "lxml")
    contacts = []

    # Strategy 1: Find all emails, look backwards for a name heading
    full_text = soup.get_text(" ")
    emails = EMAIL_REGEX.findall(full_text)
    emails = [e for e in emails if not any(s in e.lower() for s in SKIP_EMAILS)]

    if not emails:
        return []

    # Strategy 2: Look for cards/sections that contain both a name-like heading and an email
    for section in soup.select("div, section, article, li"):
        section_text = section.get_text(" ", strip=True)
        section_emails = EMAIL_REGEX.findall(section_text)
        section_emails = [e for e in section_emails if not any(s in e.lower() for s in SKIP_EMAILS)]
        if not section_emails:
            continue

        # Find a name-like heading inside this section
        name = ""
        title = ""
        for tag in section.find_all(["h1","h2","h3","h4","h5","strong","b"]):
            text = tag.get_text(strip=True)
            if NAME_PATTERN.match(text) and len(text) < 50:
                name = text
                # Check sibling/child for title
                sib = tag.find_next_sibling()
                if sib:
                    t = sib.get_text(strip=True)
                    if t and len(t) < 80 and not EMAIL_REGEX.search(t):
                        title = t
                break

        for email in section_emails:
            contacts.append({
                "name":  name,
                "title": title,
                "email": email,
                "phone": "",
            })

    # Deduplicate by email
    seen = set()
    unique = []
    for c in contacts:
        e = c["email"].lower()
        if e not in seen:
            seen.add(e)
            unique.append(c)

    return unique


def _regex_emails_only(text: str) -> list[dict]:
    """Last-resort: just return all emails found on the page."""
    emails = list(set(EMAIL_REGEX.findall(text)))
    emails = [e for e in emails if not any(s in e.lower() for s in SKIP_EMAILS)]
    return [{"name": "", "title": "", "email": e, "phone": ""} for e in emails]


# ── Ollama LLM extraction ─────────────────────────────────────────────────────

EXTRACTION_PROMPT = """\
Extract every person from the text below. Return ONLY a JSON array, no explanation, \
no markdown. Each element: {{"name":"","title":"","email":"","phone":""}}. \
If no people found return [].

Text:
\"\"\"
{text}
\"\"\"

JSON array:"""


def _call_ollama(text: str) -> list[dict]:
    prompt = EXTRACTION_PROMPT.format(text=text[:MAX_HTML_CHARS])
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model":   OLLAMA_MODEL,
                "prompt":  prompt,
                "stream":  False,
                "options": {"temperature": 0.0, "num_predict": 800},
            },
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip()
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    return v
    except Exception as exc:
        logger.warning("Ollama contact extraction failed: %s", exc)
    return []


# ── Merge helpers ─────────────────────────────────────────────────────────────

def _merge(primary: list[dict], fallback: list[dict]) -> list[dict]:
    seen = {c.get("email", "").lower() for c in primary if c.get("email")}
    extra = [c for c in fallback if c.get("email", "").lower() not in seen]
    merged = primary + extra
    return [c for c in merged if c.get("name") or c.get("email")]


# ── LangChain Tool ────────────────────────────────────────────────────────────

@tool
def extract_contacts(company_input: str) -> str:
    """
    Visit a company website, find Team/About/Contact pages, and extract
    people with names, titles, emails, and phone numbers.

    Input: 'Company Name|||https://website.com'  or  'https://website.com'
    Returns JSON list: [{"name":"...","title":"...","email":"...","phone":"..."}]
    """
    if "|||" in company_input:
        parts = company_input.split("|||", 1)
        company_name = parts[0].strip()
        website = parts[1].strip()
    else:
        company_name = ""
        website = company_input.strip()

    if not website:
        return json.dumps([])

    logger.info("Extracting contacts from: %s", website)

    # 1. Scrape with Playwright
    try:
        raw_html = _find_team_page_html(website)
    except Exception as exc:
        logger.error("Playwright failed for %s: %s", website, exc)
        raw_html = ""

    if not raw_html:
        return json.dumps([])

    # 2. Structured HTML parsing (fast, no LLM)
    structured_contacts = _parse_contacts_from_html(raw_html)
    logger.info("Structured parsing found %d contacts", len(structured_contacts))

    # 3. LLM extraction (if structured parsing missed people)
    page_text = _strip_html(raw_html)
    llm_contacts = []
    if len(structured_contacts) < 3:
        llm_contacts = _call_ollama(page_text)
        logger.info("LLM found %d contacts for %s", len(llm_contacts), company_name or website)

    # 4. Regex email fallback
    regex_contacts = _regex_emails_only(page_text)

    # 5. Merge all three: structured → LLM → regex
    contacts = _merge(structured_contacts, _merge(llm_contacts, regex_contacts))

    logger.info("Final: %d contacts for %s", len(contacts), company_name or website)
    return json.dumps(contacts, ensure_ascii=False)
