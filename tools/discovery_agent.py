"""
Discovery Agent - Scrapes sources for new pharma companies
"""

import sqlite3
import requests
import re
import time
import random
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential

DB_PATH = "./database/processed_companies.db"
ua = UserAgent()

def init_dedup_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT UNIQUE NOT NULL,
            website TEXT,
            source TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def is_company_processed(company_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM processed_companies WHERE LOWER(company_name) = LOWER(?)",
        (company_name,)
    )
    result = cursor.fetchone() is not None
    conn.close()
    return result

def mark_company_processed(company_name, website="", source=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO processed_companies (company_name, website, source) VALUES (?, ?, ?)",
            (company_name, website, source)
        )
        conn.commit()
    except:
        pass
    conn.close()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_page(url, headers=None):
    if headers is None:
        headers = {
            "User-Agent": ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }
    time.sleep(random.uniform(2, 5))
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.text

def is_valid_company_name(name):
    """Filter out article titles and invalid names."""
    if not name or len(name) < 3 or len(name) > 80:
        return False

    # Skip article titles (too many words = not a company name)
    words = name.split()
    if len(words) > 6:
        return False

    # Skip common article words
    article_words = ["why", "how", "what", "when", "where", "the", "a", "an", "is", "are", "was", "were", "will", "can", "could", "should", "would", "may", "might", "must", "shall", "this", "that", "these", "those", "with", "from", "for", "about", "into", "through", "during", "before", "after", "above", "below", "between", "under", "again", "further", "then", "once", "here", "there", "when", "where", "while", "because", "since", "until", "although", "though", "unless", "whether", "either", "neither", "both", "all", "any", "some", "many", "much", "more", "most", "other", "another", "such", "only", "own", "same", "so", "than", "too", "very", "just", "now", "also", "back", "still", "even", "already", "yet", "ever", "never", "always", "often", "sometimes", "usually", "finally", "recently", "soon", "today", "tomorrow", "yesterday"]

    name_lower = name.lower()
    if any(word in name_lower for word in article_words[:20]):  # Check first 20 common article starters
        # But allow if it's clearly a company (ends with Ltd, Inc, etc.)
        company_suffixes = ["ltd", "inc", "corp", "llc", "plc", "gmbh", "s.a", "pvt", "limited", "pharma", "biotech", "labs", "therapeutics", "pharmaceuticals"]
        if not any(suffix in name_lower for suffix in company_suffixes):
            return False

    # Skip if it contains sentence punctuation
    if "?" in name or "!" in name or ":" in name:
        return False

    return True

def extract_company_name(text):
    text = re.sub(r"\s+", " ", text.strip())
    text = re.sub(r"^(PVT\.?|LTD\.?|INC\.?|LLC|CORP\.?|Ltd\.?|Pvt\.?|Inc\.?)", "", text, flags=re.IGNORECASE)
    text = text.strip(" '").strip()

    if not is_valid_company_name(text):
        return None

    noise_words = ["tender", "bid", "notice", "reference", "date", "amount", "deadline", "download", "click here", "read more", "learn more"]
    if any(word in text.lower() for word in noise_words):
        return None

    return text

def scrape_tendertiger():
    companies = []
    keywords = ["pharmaceutical", "medicine", "drug", "API", "formulation", "vaccine", "biotech"]
    for keyword in keywords:
        try:
            search_url = f"https://www.tendertiger.net/search?q={keyword}&industry=pharma"
            html = fetch_page(search_url)
            soup = BeautifulSoup(html, "lxml")
            tender_items = soup.select(".tender-item, .search-result, .listing-item, .tender-row")
            for item in tender_items:
                company_elem = (
                    item.select_one(".company-name, .org-name, .bidder-name, .issuer-name") or
                    item.select_one("td:nth-child(3)") or
                    item.select_one("h3, h4, .title")
                )
                if company_elem:
                    raw_name = company_elem.get_text(strip=True)
                    company_name = extract_company_name(raw_name)
                    if company_name and not is_company_processed(company_name):
                        link_elem = item.find("a", href=True)
                        website = link_elem["href"] if link_elem else ""
                        # Only add if we have a valid-looking website
                        if website and (website.startswith("http") or website.startswith("www")):
                            companies.append({"name": company_name, "website": website, "source": "tendertiger"})
                        elif company_name:
                            companies.append({"name": company_name, "website": "", "source": "tendertiger"})
                        if len(companies) >= 15:
                            break
            if len(companies) >= 15:
                break
        except Exception as e:
            print(f"[TenderTiger] Error: {e}")
            continue
    return companies

def scrape_indiamart():
    companies = []
    try:
        search_url = "https://dir.indiamart.com/search.mp?ss=pharmaceutical+companies"
        html = fetch_page(search_url)
        soup = BeautifulSoup(html, "lxml")
        supplier_cards = soup.select(".lst.clr, .card, .supplier-card, .company-card")
        for card in supplier_cards:
            name_elem = card.select_one(".company-name, .orgname, h2 a, .fs18")
            if name_elem:
                raw_name = name_elem.get_text(strip=True)
                company_name = extract_company_name(raw_name)
                if company_name and not is_company_processed(company_name):
                    website_elem = card.find("a", href=True)
                    website = website_elem["href"] if website_elem else ""
                    companies.append({"name": company_name, "website": website, "source": "indiamart"})
                    if len(companies) >= 10:
                        break
    except Exception as e:
        print(f"[IndiaMart] Error: {e}")
    return companies

def scrape_google_news():
    """Extract company names from Google News RSS, filtering out article titles."""
    companies = []
    queries = [
        "pharmaceutical+company+new+funding",
        "pharma+startup+launched",
        "new+drug+company+established"
    ]
    for query in queries:
        try:
            rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            html = fetch_page(rss_url)
            soup = BeautifulSoup(html, "xml")
            items = soup.find_all("item")[:5]
            for item in items:
                title = item.find("title")
                if title:
                    title_text = title.get_text()
                    # Look for company names with proper suffixes
                    company_patterns = [
                        r"\b([A-Z][a-zA-Z&\s]+(?:Ltd|Inc|Corp|Pvt|LLC|Pharma|Bio|Labs|Therapeutics|Pharmaceuticals|Biotech))\b",
                        r"\b([A-Z][a-zA-Z&\s]+(?:Group|Holdings|Limited|Company))\b",
                    ]
                    for pattern in company_patterns:
                        matches = re.finditer(pattern, title_text)
                        for match in matches:
                            clean_name = extract_company_name(match.group(1))
                            if clean_name and not is_company_processed(clean_name):
                                companies.append({"name": clean_name, "website": "", "source": "google_news"})
                                if len(companies) >= 8:
                                    break
                    if len(companies) >= 8:
                        break
        except Exception as e:
            print(f"[Google News] Error: {e}")
            continue
    return companies

def discover_pharma_companies():
    """Scrape sources for new pharma companies. Returns up to 10 new companies."""
    init_dedup_db()
    print("[Discovery] Starting pharma company discovery...")
    all_companies = []
    print("[Discovery] Scraping TenderTiger...")
    all_companies.extend(scrape_tendertiger())
    print("[Discovery] Scraping IndiaMart...")
    all_companies.extend(scrape_indiamart())
    print("[Discovery] Scraping Google News...")
    all_companies.extend(scrape_google_news())

    seen = set()
    unique_companies = []
    for company in all_companies:
        name_lower = company["name"].lower()
        if name_lower not in seen and not is_company_processed(company["name"]):
            seen.add(name_lower)
            unique_companies.append(company)
            mark_company_processed(company["name"], company.get("website", ""), company["source"])

    result = unique_companies[:10]
    print(f"[Discovery] Found {len(result)} new pharma companies:")
    for c in result:
        print(f"  - {c['name']} | Website: {c.get('website', 'N/A')} | Source: {c['source']}")
    return result

if __name__ == "__main__":
    init_dedup_db()
    companies = discover_pharma_companies()
    print(f"\nTotal: {len(companies)}")
