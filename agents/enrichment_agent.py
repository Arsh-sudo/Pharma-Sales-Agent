"""
Enrichment Agent
════════════════
Given a company name (and optional website), enriches it with:
  - industry classification
  - location / headquarters
  - company size estimate
  - description
  - social media links

Sources: company website, Google search snippet, IndiaMart profile.
Uses Ollama Mistral to extract structured data from page text.

Exposed as a LangChain @tool.
"""
import json
import logging
import re
import time
import random
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from langchain.tools import tool

from config.settings import (
    OLLAMA_BASE_URL, OLLAMA_MODEL,
    REQUEST_HEADERS, REQUEST_TIMEOUT,
    SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX,
)

logger = logging.getLogger(__name__)

MAX_HTML_CHARS = 8_000

ENRICH_PROMPT = """\
You are a business intelligence assistant. Extract structured company data \
from the text below. Return ONLY a valid JSON object, no markdown fences, \
no explanation.

Required keys (use empty string "" if unknown):
  "industry"    — e.g. "Pharmaceutical Manufacturing", "Biotech", "CRO"
  "location"    — city, state, country
  "size"        — employee count range or "Unknown"
  "description" — one-sentence summary of what the company does
  "linkedin"    — LinkedIn URL if present
  "founded"     — founding year if mentioned

Company name: {company_name}

Text:
\"\"\"
{text}
\"\"\"

JSON object:"""


def _sleep() -> None:
    time.sleep(random.uniform(SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX))


def _get_text(url: str) -> str:
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "noscript", "head"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return re.sub(r"\s{2,}", " ", text)[:MAX_HTML_CHARS]
    except Exception as exc:
        logger.warning("GET failed for %s: %s", url, exc)
        return ""


def _google_search_snippet(company_name: str) -> str:
    """
    Fetch the first Google search result snippet for the company.
    Note: Google may block this in production — consider SerpAPI for reliability.
    """
    url = f"https://www.google.com/search?q={quote_plus(company_name + ' pharmaceutical company India')}"
    text = _get_text(url)
    _sleep()
    return text[:4000]


def _indiamart_profile(company_name: str) -> str:
    url = (
        "https://www.indiamart.com/search.mp?ss="
        + quote_plus(company_name)
    )
    text = _get_text(url)
    _sleep()
    return text[:4000]


def _call_ollama(company_name: str, text: str) -> dict:
    prompt = ENRICH_PROMPT.format(company_name=company_name, text=text)
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 512},
            },
            timeout=60,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip()
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception as exc:
        logger.error("Enrichment LLM failed for %s: %s", company_name, exc)
    return {}


@tool
def enrich_company(company_input: str) -> str:
    """
    Enrich a company with industry, location, size, and description.

    Input format (choose one):
      - Bare company name:          "Acme Pharma"
      - Name + URL separated by |||: "Acme Pharma|||https://acmepharma.com"

    Returns a JSON string with keys:
      name, website, industry, location, size, description, linkedin, founded
    """
    if "|||" in company_input:
        parts = company_input.split("|||", 1)
        company_name = parts[0].strip()
        website = parts[1].strip()
    else:
        company_name = company_input.strip()
        website = ""

    logger.info("Enriching company: %s", company_name)

    # Gather text from multiple sources
    combined_text = ""

    if website:
        combined_text += _get_text(website)
        _sleep()

    combined_text += "\n" + _google_search_snippet(company_name)
    combined_text += "\n" + _indiamart_profile(company_name)

    enriched = _call_ollama(company_name, combined_text[:MAX_HTML_CHARS])

    result = {
        "name":        company_name,
        "website":     website,
        "industry":    enriched.get("industry", ""),
        "location":    enriched.get("location", ""),
        "size":        enriched.get("size", ""),
        "description": enriched.get("description", ""),
        "linkedin":    enriched.get("linkedin", ""),
        "founded":     enriched.get("founded", ""),
    }

    logger.info("Enriched %s: %s", company_name, result)
    return json.dumps(result, ensure_ascii=False)
