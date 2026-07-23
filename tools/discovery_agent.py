import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from duckduckgo_search import DDGS   # <-- new import

from config.settings import SEED_COMPANIES

logger = logging.getLogger(__name__)

def find_company_website(company_name: str) -> Optional[str]:
    """
    Use DuckDuckGo to find the official website of a company.
    Returns the first organic result that is not Wikipedia or LinkedIn.
    """
    query = f"{company_name} pharmaceutical company official website"
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                url = r.get('href', '')
                # Avoid generic sites that are not the official company page
                if 'wikipedia' not in url and 'linkedin' not in url and 'facebook' not in url:
                    return url
    except Exception as e:
        logger.warning(f"DDG search failed for {company_name}: {e}")
    return None


def scrape_tender_tiger() -> List[Dict]:
    """Scrape Tender Tiger for pharma-related tenders and extract company names."""
    results = []
    try:
        url = "https://www.tendertiger.net/search?q=pharmaceutical"
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(resp.text, 'lxml')
        # Look for company names in tender listings – adjust selectors as needed
        for item in soup.select('.tender-item .company-name'):
            name = item.text.strip()
            if name:
                results.append({"name": name, "website": None})
    except Exception as e:
        logger.warning(f"TenderTiger scrape failed: {e}")
    return results


def scrape_indiamart() -> List[Dict]:
    """Scrape IndiaMart for pharmaceutical companies."""
    results = []
    try:
        url = "https://www.indiamart.com/search?q=pharmaceutical+companies"
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(resp.text, 'lxml')
        # Adjust selectors based on actual page structure
        for item in soup.select('.company-name'):
            name = item.text.strip()
            if name:
                results.append({"name": name, "website": None})
    except Exception as e:
        logger.warning(f"IndiaMart scrape failed: {e}")
    return results


def scrape_google_news() -> List[Dict]:
    """Scrape Google News RSS for pharma company mentions."""
    results = []
    try:
        url = "https://news.google.com/rss/search?q=pharmaceutical+company&hl=en-IN&gl=IN&ceid=IN:en"
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(resp.text, 'xml')
        for item in soup.find_all('item'):
            title = item.title.text if item.title else ''
            # Simple extraction: look for company names (could be improved with NER)
            # For now, we extract any text that contains "Pharma" or "Pharmaceutical"
            if 'pharma' in title.lower() or 'pharmaceutical' in title.lower():
                # Naive: take the first few words as company name
                name = title.split('.')[0].split(',')[0].strip()
                if name and len(name) > 3:
                    results.append({"name": name, "website": None})
    except Exception as e:
        logger.warning(f"Google News scrape failed: {e}")
    return results


def discover_companies(limit: int = 10) -> List[Dict]:
    """
    Main discovery function:
    - Scrapes all sources
    - Merges with seed list
    - Deduplicates and enriches with website using fallback search
    - Returns up to `limit` companies, preferring those with websites.
    """
    logger.info("Starting company discovery...")
    
    raw = []
    raw.extend(scrape_tender_tiger())
    raw.extend(scrape_indiamart())
    raw.extend(scrape_google_news())
    logger.info(f"Scraped {len(raw)} raw results")
    
    # Merge with seed companies (which have known websites)
    all_companies = raw + SEED_COMPANIES   # SEED_COMPANIES is a list of dicts with 'name' and 'website'
    
    # Deduplicate by name (keep first occurrence, but if later one has a website, update)
    seen = {}
    unique = []
    for c in all_companies:
        name = c.get("name", "").strip()
        if not name:
            continue
        if name not in seen:
            seen[name] = c
            unique.append(c)
        else:
            # If existing lacks a website, take the new one's website if any
            if not seen[name].get("website") and c.get("website"):
                seen[name]["website"] = c["website"]
    
    # For each company without a website, try the fallback search
    for company in unique:
        if not company.get("website"):
            logger.info(f"Searching website for {company['name']}...")
            site = find_company_website(company["name"])
            if site:
                company["website"] = site
                logger.info(f"Found: {site}")
    
    # Sort: companies with website first
    unique.sort(key=lambda x: bool(x.get("website")), reverse=True)
    
    # Take top `limit`
    result = unique[:limit]
    logger.info(f"Discovery complete: {len(result)} companies (from {len(unique)} total)")
    return result