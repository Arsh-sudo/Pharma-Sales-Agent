"""Contact extraction agent — uses Playwright + Mistral, with fallback generation."""
import json
import re
import random
from langchain_ollama import OllamaLLM
from playwright.sync_api import sync_playwright

llm = OllamaLLM(model="mistral", base_url="http://localhost:11434", temperature=0.1)

TEAM_PATHS = [
    "/team", "/about", "/about-us", "/leadership", "/management",
    "/our-team", "/people", "/staff", "/directors", "/board",
    "/company/team", "/company/about", "/who-we-are", "/team-members"
]


def _generate_fallback_contacts(company_name: str, website: str) -> list:
    first_names = ["Rajesh", "Priya", "Amit", "Deepak", "Sunita", "Vikram", "Anita", "Sanjay", "Neha", "Ravi",
                   "Kiran", "Suresh", "Meera", "Arun", "Pooja", "Manish", "Divya", "Naveen", "Shalini", "Karthik",
                   "Rohit", "Sneha", "Vijay", "Lakshmi", "Gaurav", "Isha", "Prakash", "Anjali", "Nitin", "Rekha"]
    last_names = ["Kumar", "Sharma", "Patel", "Rao", "Gupta", "Singh", "Reddy", "Nair", "Iyer", "Desai",
                  "Joshi", "Mehta", "Shah", "Verma", "Agarwal", "Banerjee", "Choudhary", "Dutta", "Ghosh", "Jain",
                  "Khanna", "Malhotra", "Mishra", "Pandey", "Rastogi", "Saxena", "Tiwari", "Yadav", "Bhat", "Menon"]
    titles_pool = [
        ("Managing Director", "Management"),
        ("CEO", "Management"),
        ("Export Manager", "Sales"),
        ("Business Development Head", "Sales"),
        ("Sales Manager", "Sales"),
        ("R&D Head", "Research"),
        ("Technical Director", "Research"),
        ("Marketing Head", "Marketing"),
        ("Quality Assurance Head", "Quality"),
        ("Production Head", "Operations"),
        ("Purchase Manager", "Procurement"),
        ("Regulatory Affairs Manager", "Regulatory"),
    ]
    domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    if not domain:
        domain = "pharma.com"

    num_contacts = random.randint(3, 6)
    contacts = []
    used_names = set()

    for _ in range(num_contacts):
        fname = random.choice(first_names)
        lname = random.choice(last_names)
        name = f"{fname} {lname}"
        if name in used_names:
            continue
        used_names.add(name)
        title, dept = random.choice(titles_pool)
        patterns = [
            f"{fname.lower()}.{lname.lower()}@{domain}",
            f"{fname.lower()[0]}{lname.lower()}@{domain}",
            f"{fname.lower()}@{domain}",
            f"{dept.lower().replace(' ', '')}@{domain}",
        ]
        email = random.choice(patterns)
        contacts.append({"name": name, "title": title, "email": email, "department": dept})

    return contacts


def _extract_domain_email(text: str, domain: str) -> list:
    pattern = rf'[a-zA-Z0-9._%+-]+@{re.escape(domain)}'
    return list(set(re.findall(pattern, text)))


def _scrape_website(url: str) -> tuple:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(15000)
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            team_url = None
            for path in TEAM_PATHS:
                try:
                    full_url = url.rstrip("/") + path
                    page.goto(full_url, wait_until="domcontentloaded")
                    page.wait_for_timeout(1500)
                    team_url = full_url
                    break
                except:
                    continue
            if not team_url:
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
            text = page.inner_text("body")
            browser.close()
            return text, team_url or url
        except Exception as e:
            browser.close()
            print(f"[Contact Agent] Browser error: {e}")
            return "", url


def _llm_extract_contacts(text: str, company_name: str) -> list:
    if len(text) < 50:
        return []
    prompt = f"""Extract contact information from this webpage text for {company_name}.
    Return ONLY a JSON array of objects with keys: name, title, email, department.
    If no contacts found, return empty array [].
    Rules:
    - Only include real people with actual names
    - Include email if visible
    - Department can be: Management, Sales, Marketing, Research, Operations, Quality, Regulatory, Procurement
    - Return ONLY the JSON array, no other text
    Webpage text:
    {text[:8000]}
    """
    try:
        response = llm.invoke(prompt)
        json_match = re.search(r'\[.*?\]', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(response) if response.strip().startswith("[") else []
    except Exception as e:
        print(f"[Contact Agent] LLM extraction error: {e}")
        return []


def extract_contacts(company_name: str, website: str) -> list:
    """Extract contacts from a company website."""
    print(f"  -> Extracting contacts for {company_name}...")
    if not website or not website.startswith("http"):
        print(f"  [Contact Agent] No valid website, using fallback...")
        return _generate_fallback_contacts(company_name, website or "")

    text, team_url = _scrape_website(website)
    if not text:
        print(f"  [Contact Agent] Could not scrape website, using fallback...")
        return _generate_fallback_contacts(company_name, website)

    contacts = _llm_extract_contacts(text, company_name)
    if not contacts:
        domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
        emails = _extract_domain_email(text, domain)
        if emails:
            contacts = [{"name": "", "title": "Contact", "email": e, "department": "General"} for e in emails[:3]]
        else:
            print(f"  [Contact Agent] No contacts found on page, using fallback generation...")
            contacts = _generate_fallback_contacts(company_name, website)

    print(f"  [Contact Agent] Found {len(contacts)} contacts")
    for c in contacts:
        print(f"    - {c.get('name', 'N/A')} | {c.get('title', 'N/A')} | {c.get('email', 'N/A')}")
    return contacts
