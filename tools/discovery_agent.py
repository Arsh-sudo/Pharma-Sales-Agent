"""
Discovery Agent - Finds REAL pharma companies from multiple sources
"""

import sqlite3
import requests
import re
import time
import random
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

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
    cursor.execute("SELECT 1 FROM processed_companies WHERE LOWER(company_name) = LOWER(?)", (company_name,))
    result = cursor.fetchone() is not None
    conn.close()
    return result

def mark_company_processed(company_name, website="", source=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO processed_companies (company_name, website, source) VALUES (?, ?, ?)",
                      (company_name, website, source))
        conn.commit()
    except:
        pass
    conn.close()

def fetch_page(url, headers=None, timeout=15):
    if headers is None:
        headers = {"User-Agent": ua.random, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
    time.sleep(random.uniform(1, 3))
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text

def is_valid_company_name(name):
    if not name or len(name) < 3 or len(name) > 80:
        return False
    words = name.split()
    if len(words) > 7:
        return False
    article_starters = ["why ", "how ", "what ", "when ", "where ", "the ", "this ", "that ", "these ", "those ",
                       "with ", "from ", "for ", "about ", "into ", "through ", "during ", "before ", "after ",
                       "above ", "below ", "between ", "under ", "again ", "further ", "then ", "once ", "here ",
                       "there ", "while ", "because ", "since ", "until ", "although ", "though ", "unless ",
                       "whether ", "either ", "neither ", "both ", "all ", "any ", "some ", "many ", "much ",
                       "more ", "most ", "other ", "another ", "such ", "only ", "own ", "same ", "so ", "than ",
                       "too ", "very ", "just ", "now ", "also ", "back ", "still ", "even ", "already ", "yet ",
                       "ever ", "never ", "always ", "often ", "sometimes ", "usually ", "finally ", "recently ",
                       "soon ", "today ", "tomorrow ", "yesterday"]
    name_lower = name.lower()
    if any(name_lower.startswith(word) for word in article_starters):
        suffixes = ["ltd", "inc", "corp", "llc", "plc", "gmbh", "pvt", "limited", "pharma", "bio", "labs",
                   "therapeutics", "pharmaceuticals", "biotech", "healthcare", "medical", "drug", "api", "formulation"]
        if not any(suffix in name_lower for suffix in suffixes):
            return False
    if "?" in name or "!" in name or ":" in name or '"' in name:
        return False
    return True

def extract_company_name(text):
    text = re.sub(r"\s+", " ", text.strip())
    text = re.sub(r"^(PVT\.?|LTD\.?|INC\.?|LLC|CORP\.?|Ltd\.?|Pvt\.?|Inc\.?)", "", text, flags=re.IGNORECASE)
    text = text.strip(" '").strip()
    if not is_valid_company_name(text):
        return None
    noise = ["tender", "bid", "notice", "reference", "date", "amount", "deadline", "download",
             "click here", "read more", "learn more", "submit", "apply", "register", "login", "sign in",
             "home", "about us", "contact us", "privacy policy", "terms of service"]
    if any(word in text.lower() for word in noise):
        return None
    return text

def scrape_pharma_news_rss():
    companies = []
    rss_feeds = [
        "https://www.pharmaceutical-technology.com/feed/",
        "https://www.fiercepharma.com/rss/xml",
    ]
    for rss_url in rss_feeds:
        try:
            html = fetch_page(rss_url, timeout=10)
            soup = BeautifulSoup(html, "xml")
            items = soup.find_all("item")[:8]
            for item in items:
                title = item.find("title")
                description = item.find("description")
                text_to_search = ""
                if title:
                    text_to_search += title.get_text() + " "
                if description:
                    text_to_search += description.get_text()
                patterns = [
                    r"\b([A-Z][a-zA-Z&\s]+(?:Pharma|Pharmaceuticals|Biotech|Labs|Therapeutics|Bio|Healthcare|Medical|Drug))\b",
                    r"\b([A-Z][a-zA-Z&\s]+(?:Ltd|Inc|Corp|Limited|LLC|PLC))\b",
                ]
                for pattern in patterns:
                    matches = re.finditer(pattern, text_to_search)
                    for match in matches:
                        clean_name = extract_company_name(match.group(1))
                        if clean_name and not is_company_processed(clean_name):
                            website = ""
                            if description:
                                desc_text = description.get_text()
                                url_match = re.search(r'https?://[^\s<>"{}|\\^`\[\]]+', desc_text)
                                if url_match:
                                    website = url_match.group(0)
                            companies.append({"name": clean_name, "website": website, "source": "pharma_news_rss"})
                            if len(companies) >= 12:
                                break
                    if len(companies) >= 12:
                        break
                if len(companies) >= 12:
                    break
        except Exception as e:
            print(f"[RSS] Error with {rss_url}: {e}")
            continue
    return companies

def scrape_government_tenders():
    companies = []
    try:
        url = "https://www.bidassist.com/search?q=pharmaceutical"
        html = fetch_page(url, timeout=10)
        soup = BeautifulSoup(html, "lxml")
        tender_items = soup.select(".tender-card, .search-item, .listing-item")
        for item in tender_items:
            org_elem = item.select_one(".organization, .department, .company, .authority")
            if org_elem:
                raw_name = org_elem.get_text(strip=True)
                company_name = extract_company_name(raw_name)
                if company_name and not is_company_processed(company_name):
                    companies.append({"name": company_name, "website": "", "source": "government_tenders"})
                    if len(companies) >= 8:
                        break
    except Exception as e:
        print(f"[Gov Tenders] Error: {e}")
    return companies

def scrape_startup_databases():
    companies = []
    try:
        url = "https://www.zaubacorp.com/companysearchresults/pharma"
        headers = {"User-Agent": ua.random}
        html = fetch_page(url, headers=headers, timeout=10)
        soup = BeautifulSoup(html, "lxml")
        company_rows = soup.select(".table tr, .company-row, .search-result")
        for row in company_rows:
            name_elem = row.select_one("td a, .company-name, h3")
            if name_elem:
                raw_name = name_elem.get_text(strip=True)
                company_name = extract_company_name(raw_name)
                if company_name and not is_company_processed(company_name):
                    link = name_elem.get("href", "")
                    website = f"https://www.zaubacorp.com{link}" if link.startswith("/") else link
                    companies.append({"name": company_name, "website": website, "source": "startup_database"})
                    if len(companies) >= 8:
                        break
    except Exception as e:
        print(f"[Startup DB] Error: {e}")
    return companies

def discover_pharma_companies():
    init_dedup_db()
    print("[Discovery] Starting REAL pharma company discovery...")
    print("[Discovery] This may take 1-2 minutes...")

    all_companies = []

    print("[Discovery] Checking pharma news RSS feeds...")
    all_companies.extend(scrape_pharma_news_rss())
    print(f"  Found {len(all_companies)} from news")

    print("[Discovery] Checking government tenders...")
    all_companies.extend(scrape_government_tenders())
    print(f"  Total now: {len(all_companies)}")

    print("[Discovery] Checking startup databases...")
    all_companies.extend(scrape_startup_databases())
    print(f"  Total now: {len(all_companies)}")

    seen = set()
    unique_companies = []
    for company in all_companies:
        name_lower = company["name"].lower()
        if name_lower not in seen and not is_company_processed(company["name"]):
            seen.add(name_lower)
            unique_companies.append(company)
            mark_company_processed(company["name"], company.get("website", ""), company["source"])

    result = unique_companies[:10]
    print(f"\n[Discovery] Found {len(result)} NEW pharma companies from scraping:")
    for c in result:
        print(f"  - {c['name']} | Website: {c.get('website', 'N/A')[:50]} | Source: {c['source']}")

    # If we found very few companies, supplement with verified real companies
    if len(result) < 3:
        print("\n[Discovery] Found few companies from scraping. Adding verified pharma companies...")
        verified_companies = [
            {"name": "Mankind Pharma", "website": "https://www.mankindpharma.com", "source": "verified_list"},
            {"name": "Alkem Laboratories", "website": "https://www.alkemlabs.com", "source": "verified_list"},
            {"name": "Intas Pharmaceuticals", "website": "https://www.intaspharma.com", "source": "verified_list"},
            {"name": "Cadila Healthcare", "website": "https://www.zyduscadila.com", "source": "verified_list"},
            {"name": "Wockhardt Limited", "website": "https://www.wockhardt.com", "source": "verified_list"},
            {"name": "Laurus Labs", "website": "https://www.lauruslabs.com", "source": "verified_list"},
            {"name": "Divi's Laboratories", "website": "https://www.divislabs.com", "source": "verified_list"},
            {"name": "Granules India", "website": "https://www.granulesindia.com", "source": "verified_list"},
            {"name": "Aurobindo Pharma", "website": "https://www.aurobindo.com", "source": "verified_list"},
            {"name": "Biocon Limited", "website": "https://www.biocon.com", "source": "verified_list"},
        ]
        for vc in verified_companies:
            if not is_company_processed(vc["name"]):
                result.append(vc)
                mark_company_processed(vc["name"], vc["website"], vc["source"])
                if len(result) >= 10:
                    break
        print(f"[Discovery] Total after supplement: {len(result)}")

    return result

if __name__ == "__main__":
    init_dedup_db()
    companies = discover_pharma_companies()
    print(f"\nFinal count: {len(companies)}")
    for c in companies:
        print(f"  {c['name']} - {c.get('website', 'No website')}")
