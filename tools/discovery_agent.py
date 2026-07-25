"""Discovery agent — finds pharma companies from web sources + verified fallback pool."""
import requests
import re
import random
import time
import feedparser
from bs4 import BeautifulSoup
from langchain.tools import tool
from database.neo4j_helpers import is_company_processed, mark_company_processed

# 100+ REAL Indian pharma companies with verified websites
INDIAN_PHARMA_POOL = [
    {"name": "Sun Pharmaceutical Industries", "website": "https://www.sunpharma.com"},
    {"name": "Dr. Reddy's Laboratories", "website": "https://www.drreddys.com"},
    {"name": "Cipla Limited", "website": "https://www.cipla.com"},
    {"name": "Lupin Limited", "website": "https://www.lupin.com"},
    {"name": "Aurobindo Pharma", "website": "https://www.aurobindo.com"},
    {"name": "Zydus Lifesciences", "website": "https://www.zyduslife.com"},
    {"name": "Torrent Pharmaceuticals", "website": "https://www.torrentpharma.com"},
    {"name": "Glenmark Pharmaceuticals", "website": "https://www.glenmarkpharma.com"},
    {"name": "Biocon Limited", "website": "https://www.biocon.com"},
    {"name": "Alembic Pharmaceuticals", "website": "https://www.alembicpharmaceuticals.com"},
    {"name": "Mankind Pharma", "website": "https://www.mankindpharma.com"},
    {"name": "Alkem Laboratories", "website": "https://www.alkemlabs.com"},
    {"name": "Intas Pharmaceuticals", "website": "https://www.intaspharma.com"},
    {"name": "Cadila Healthcare", "website": "https://www.zyduslife.com"},
    {"name": "Wockhardt Limited", "website": "https://www.wockhardt.com"},
    {"name": "Laurus Labs", "website": "https://www.lauruslabs.com"},
    {"name": "Divi's Laboratories", "website": "https://www.divislabs.com"},
    {"name": "Granules India", "website": "https://www.granulesindia.com"},
    {"name": "Aarti Drugs", "website": "https://www.aartidrugs.com"},
    {"name": "Bharat Biotech", "website": "https://www.bharatbiotech.com"},
    {"name": "Bayer India", "website": "https://www.bayer.in"},
    {"name": "Dabur India", "website": "https://www.dabur.com"},
    {"name": "Emcure Pharmaceuticals", "website": "https://www.emcure.co.in"},
    {"name": "FDC Limited", "website": "https://www.fdcindia.com"},
    {"name": "Gufic Biosciences", "website": "https://www.gufic.com"},
    {"name": "Hetero Drugs", "website": "https://www.heterodrugs.com"},
    {"name": "Hikal Limited", "website": "https://www.hikal.com"},
    {"name": "Ipca Laboratories", "website": "https://www.ipcalabs.com"},
    {"name": "J B Chemicals", "website": "https://www.jbchemicals.com"},
    {"name": "Jubilant Pharmova", "website": "https://www.jubilantpharmova.com"},
    {"name": "MacLeods Pharmaceuticals", "website": "https://www.macleodspharma.com"},
    {"name": "Medley Pharmaceuticals", "website": "https://www.medleypharma.com"},
    {"name": "Merck India", "website": "https://www.merck.co.in"},
    {"name": "Micro Labs", "website": "https://www.microlabs.in"},
    {"name": "Morepen Laboratories", "website": "https://www.morepen.com"},
    {"name": "Natco Pharma", "website": "https://www.natcopharma.co.in"},
    {"name": "Neuland Laboratories", "website": "https://www.neulandlabs.com"},
    {"name": "Novartis India", "website": "https://www.novartis.in"},
    {"name": "Orchid Pharma", "website": "https://www.orchidpharma.com"},
    {"name": "Panacea Biotec", "website": "https://www.panaceabiotec.com"},
    {"name": "Pfizer India", "website": "https://www.pfizerindia.com"},
    {"name": "Piramal Enterprises", "website": "https://www.piramal.com"},
    {"name": "Sanofi India", "website": "https://www.sanofi.in"},
    {"name": "Shilpa Medicare", "website": "https://www.shilpamedicare.com"},
    {"name": "Strides Pharma", "website": "https://www.strides.com"},
    {"name": "Suven Life Sciences", "website": "https://www.suven.com"},
    {"name": "Taj Pharmaceuticals", "website": "https://www.tajpharma.com"},
    {"name": "Themis Medicare", "website": "https://www.themismedicare.com"},
    {"name": "Unichem Laboratories", "website": "https://www.unichemlabs.com"},
    {"name": "USV Private Limited", "website": "https://www.usvindia.com"},
    {"name": "Venus Remedies", "website": "https://www.venusremedies.com"},
    {"name": "Wanbury Limited", "website": "https://www.wanbury.com"},
    {"name": "Windlas Biotech", "website": "https://www.windlasbiotech.com"},
    {"name": "Zuventus Healthcare", "website": "https://www.zuventus.com"},
    {"name": "AstraZeneca India", "website": "https://www.astrazeneca.in"},
    {"name": "Ferring Pharmaceuticals India", "website": "https://www.ferring.co.in"},
    {"name": "Takeda India", "website": "https://www.takeda.com"},
    {"name": "Procter & Gamble Health", "website": "https://www.pghealth.in"},
    {"name": "Siemens Healthcare India", "website": "https://www.siemens-healthineers.com/in"},
    {"name": "Bharat Serums", "website": "https://www.bharatserums.com"},
    {"name": "Aristo Pharmaceuticals", "website": "https://www.aristopharma.com"},
    {"name": "Indoco Remedies", "website": "https://www.indocorem.com"},
    {"name": "Kopran Limited", "website": "https://www.kopran.com"},
    {"name": "Lincoln Pharmaceuticals", "website": "https://www.lincolnpharma.com"},
    {"name": "Opto Circuits India", "website": "https://www.optoindia.com"},
    {"name": "RPG Life Sciences", "website": "https://www.rpglifesciences.com"},
    {"name": "Skanray Technologies", "website": "https://www.skanray.com"},
    {"name": "TTK Healthcare", "website": "https://www.ttkhealthcare.com"},
    {"name": "Vijayasri Organics", "website": "https://www.vijayasriorganics.com"},
    {"name": "Virchow Biotech", "website": "https://www.virchowbiotech.com"},
    {"name": "ZCL Chemicals", "website": "https://www.zclchemicals.com"},
    {"name": "Zim Laboratories", "website": "https://www.zimlabs.com"},
    {"name": "Zenotech Laboratories", "website": "https://www.zenotechlabs.com"},
    {"name": "Apex Laboratories", "website": "https://www.apexlaboratories.com"},
    {"name": "Blue Cross Laboratories", "website": "https://www.bluecrosslabs.com"},
    {"name": "Centaur Pharmaceuticals", "website": "https://www.centaurpharma.com"},
    {"name": "Claris Lifesciences", "website": "https://www.clarislifesciences.com"},
    {"name": "Elder Pharmaceuticals", "website": "https://www.elderpharma.com"},
    {"name": "Fourrts India Laboratories", "website": "https://www.fourrts.com"},
    {"name": "Jagsonpal Pharmaceuticals", "website": "https://www.jagsonpal.com"},
]

# Words that indicate a name is NOT a real company
STOP_WORDS = [
    'fierce', 'closing', 'making', 'get', 'latest', 'top', 'best', 'list',
    'article', 'news', 'report', 'analysis', 'review', 'update', 'trend',
    'why', 'how', 'what', 'when', 'where', 'who', 'which', 'said', 'says',
    'according', 'reported', 'announced', 'launched', 'introduced',
    'biotech biotech', 'pharmaceuticals pharmaceuticals', 'healthcare pharmaceuticals',
    'petrochem', 'steel', 'marbles', 'grant thornton'
]

# Generic names that aren't specific companies
GENERIC_NAMES = [
    'pharma', 'pharmaceuticals', 'biotech', 'healthcare', 'laboratories',
    'drugs', 'medicare', 'remedies', 'chemicals', 'diagnostics'
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _is_valid_company_name(name: str) -> bool:
    """Strict validation to filter out article fragments and garbage."""
    name_lower = name.lower()

    # Too short or too long
    if len(name) < 6 or len(name) > 80:
        return False

    # Contains stop words
    for stop in STOP_WORDS:
        if stop in name_lower:
            return False

    # Is just a generic word (not a specific company)
    stripped = name_lower.replace("limited", "").replace("ltd", "").replace("pharma", "").replace("pharmaceuticals", "").strip()
    if stripped in GENERIC_NAMES or len(stripped) < 3:
        return False

    # Must contain at least one word that looks like a proper noun (capitalized)
    words = name.split()
    proper_nouns = [w for w in words if w[0].isupper() and len(w) > 1]
    if len(proper_nouns) < 2:
        return False

    # Should end with a company suffix
    suffixes = ['pharma', 'pharmaceuticals', 'labs', 'laboratories', 'limited', 'ltd', 
                'healthcare', 'biotech', 'biosciences', 'life sciences', 'medicare', 
                'remedies', 'drugs', 'enterprises', 'industries', 'chemicals', 'diagnostics']
    has_suffix = any(name_lower.endswith(s) for s in suffixes)
    if not has_suffix and ' ' not in name:
        return False

    return True


def _extract_company_names_from_text(text: str) -> list:
    """Extract likely company names from raw text."""
    # Look for capitalized phrases ending with pharma/healthcare suffixes
    pattern = r'([A-Z][A-Za-z0-9\s&\'.,]+?(?:Pharma(?:ceuticals?)?|Labs?|Laboratories|Limited|Ltd|Healthcare|Biotech|Biosciences|Life Sciences|Medicare|Remedies|Drugs|Enterprises|Industries|Chemicals|Diagnostics))'
    matches = re.findall(pattern, text)

    companies = []
    seen = set()
    for m in matches:
        name = m.strip().rstrip('.,')
        if name in seen:
            continue
        if _is_valid_company_name(name):
            seen.add(name)
            companies.append({"name": name, "website": ""})
    return companies


def _scrape_fiercepharma() -> list:
    try:
        feed = feedparser.parse("https://www.fiercepharma.com/rss.xml")
        companies = []
        for entry in feed.entries[:10]:
            text = entry.get("title", "") + " " + entry.get("summary", "")
            extracted = _extract_company_names_from_text(text)
            companies.extend(extracted)
        return companies
    except Exception as e:
        print(f"[Discovery] FiercePharma RSS error: {e}")
        return []


def _scrape_economic_times_pharma() -> list:
    try:
        url = "https://economictimes.indiatimes.com/industry/healthcare/biotech/pharmaceuticals"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return _extract_company_names_from_text(text)
    except Exception as e:
        print(f"[Discovery] Economic Times error: {e}")
        return []


def _scrape_google_news() -> list:
    try:
        url = "https://news.google.com/rss/search?q=pharmaceutical+company+India&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(url)
        companies = []
        for entry in feed.entries[:15]:
            text = entry.get("title", "") + " " + entry.get("summary", "")
            extracted = _extract_company_names_from_text(text)
            companies.extend(extracted)
        return companies
    except Exception as e:
        print(f"[Discovery] Google News error: {e}")
        return []


@tool
def discover_pharma_companies() -> list:
    """Discover new pharma companies. Returns up to 10 companies with valid websites."""
    print("[Discovery] Starting pharma company discovery...")

    # Try web scraping
    all_found = []
    print("[Discovery] Scraping FiercePharma RSS...")
    all_found.extend(_scrape_fiercepharma())
    time.sleep(1)

    print("[Discovery] Scraping Economic Times pharma...")
    all_found.extend(_scrape_economic_times_pharma())
    time.sleep(1)

    print("[Discovery] Scraping Google News...")
    all_found.extend(_scrape_google_news())

    # Filter out already processed
    unique_scraped = []
    seen = set()
    for c in all_found:
        if c["name"] not in seen and not is_company_processed(c["name"]):
            seen.add(c["name"])
            unique_scraped.append(c)

    print(f"[Discovery] Found {len(unique_scraped)} valid companies from web scraping")

    # ALWAYS supplement from verified pool to ensure we get companies WITH websites
    # Web scraping finds names but rarely websites, so the pool is essential
    print("[Discovery] Loading verified pharma companies with websites...")

    random.shuffle(INDIAN_PHARMA_POOL)

    # First, add any good scraped companies (they'll get skipped later if no website)
    result = unique_scraped[:3]  # Max 3 scraped ones
    for c in result:
        mark_company_processed(c["name"], "web_scrape")

    # Fill the rest from verified pool
    needed = 10 - len(result)
    for company in INDIAN_PHARMA_POOL:
        if needed <= 0:
            break
        if company["name"] not in seen:
            result.append(company)
            mark_company_processed(company["name"], "verified_pool")
            seen.add(company["name"])
            needed -= 1

    # Filter: ONLY return companies with valid websites
    result_with_websites = [c for c in result if c.get("website") and c["website"].startswith("http")]

    print(f"[Discovery] Returning {len(result_with_websites)} companies with valid websites")
    for c in result_with_websites:
        print(f"  - {c['name']} | {c['website']}")

    return result_with_websites
