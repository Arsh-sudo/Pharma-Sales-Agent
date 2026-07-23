
# ============================================
# 3. tools/contact_agent.py
# ============================================
contact_agent = r'''"""
Contact Agent - Playwright-based Contact Extraction Tool
Visits company websites, finds Team/About pages, and uses Ollama Mistral
to extract structured contact information (names, titles, emails).
"""

import json
import re
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from langchain.tools import tool
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate

llm = OllamaLLM(
    model="mistral",
    base_url="http://localhost:11434",
    temperature=0.1,
    timeout=120
)

def find_team_page(page, base_url: str) -> Optional[str]:
    team_patterns = [
        "/team", "/about", "/about-us", "/leadership", "/management",
        "/our-team", "/people", "/staff", "/executives", "/directors",
        "/company", "/who-we-are", "/team-members"
    ]
    for pattern in team_patterns:
        try:
            link = page.locator(f'a:has-text("{pattern.replace("/", "").replace("-", " ").title()}")').first
            if link.count() > 0:
                href = link.get_attribute("href")
                if href:
                    if href.startswith("http"):
                        return href
                    else:
                        return base_url.rstrip("/") + "/" + href.lstrip("/")
        except:
            continue
    for pattern in team_patterns:
        try:
            test_url = base_url.rstrip("/") + pattern
            response = page.goto(test_url, timeout=8000, wait_until="domcontentloaded")
            if response and response.status == 200:
                return test_url
        except:
            continue
    return None

def extract_visible_text(page) -> str:
    try:
        text = page.evaluate("""
            () => {
                const scripts = document.querySelectorAll('script, style, nav, footer, noscript');
                scripts.forEach(el => el.remove());
                return document.body.innerText;
            }
        """)
        return text or ""
    except:
        return ""

def extract_html_content(page) -> str:
    try:
        html = page.evaluate("""
            () => {
                const selectors = [
                    'main', 'article', '.team-section', '.about-section',
                    '.leadership', '.management', '#team', '#about',
                    '.content', '.container'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) return el.innerHTML;
                }
                return document.body.innerHTML;
            }
        """)
        return html or ""
    except:
        return ""

def extract_contacts_with_llm(text_content: str, html_content: str) -> List[Dict]:
    prompt_template = PromptTemplate.from_template("""
You are an expert data extraction assistant. Extract contact information 
from the following webpage content of a pharmaceutical company.

Extract ALL people mentioned with their:
- Full name
- Job title/role (e.g., CEO, Director, Sales Manager, R&D Head)
- Email address (if visible)
- Department (if mentioned)

WEBPAGE TEXT CONTENT:
{text_content}

WEBPAGE HTML SNIPPETS:
{html_content}

Return ONLY a valid JSON array in this exact format:
[
  {
    "name": "John Doe",
    "title": "Chief Executive Officer",
    "email": "john@example.com",
    "department": "Management"
  }
]

If no contacts are found, return an empty array [].
Do not include any explanation or markdown formatting.
""")
    max_chars = 8000
    text_content = text_content[:max_chars]
    html_content = html_content[:max_chars]
    prompt = prompt_template.format(text_content=text_content, html_content=html_content)
    try:
        response = llm.invoke(prompt)
        json_match = re.search(r'\[.*?\]', response, re.DOTALL)
        if json_match:
            contacts = json.loads(json_match.group())
            return contacts if isinstance(contacts, list) else []
        contacts = json.loads(response)
        return contacts if isinstance(contacts, list) else []
    except json.JSONDecodeError as e:
        print(f"[LLM Extraction] JSON parse error: {e}")
        return fallback_extraction(text_content)
    except Exception as e:
        print(f"[LLM Extraction] Error: {e}")
        return []

def fallback_extraction(text: str) -> List[Dict]:
    contacts = []
    patterns = [
        r'([A-Z][a-z]+\s+[A-Z][a-z]+)[,\s-]+(CEO|CFO|CTO|Director|Manager|Head|President|VP|Vice President|Chief|Founder|Owner|Sales|Marketing|R&D|Research)',
        r'(Mr\.?|Mrs\.?|Ms\.?|Dr\.?)?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)[,\s-]+(.*?)(?:\n|$)',
    ]
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            name = match.group(1) if match.group(1) else match.group(2)
            title = match.group(2) if match.group(1) else match.group(3)
            surrounding = text[max(0, match.start()-100):min(len(text), match.end()+100)]
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', surrounding)
            email = email_match.group(0) if email_match else ""
            contacts.append({
                "name": name.strip(),
                "title": title.strip() if title else "Unknown",
                "email": email,
                "department": ""
            })
    return contacts

@tool
def extract_contacts(company_website: str) -> List[Dict]:
    """
    Given a company's website URL, visit the site, find the Team/About page,
    and extract contacts (names, titles, emails) using Ollama Mistral.
    Returns a list of dicts: [{'name': '...', 'title': '...', 'email': '...'}, ...]
    """
    if not company_website or not company_website.startswith("http"):
        print(f"[Contact Agent] Invalid website URL: {company_website}")
        return []
    print(f"[Contact Agent] Extracting contacts from: {company_website}")
    contacts = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        try:
            print(f"[Contact Agent] Visiting homepage...")
            page.goto(company_website, timeout=15000, wait_until="networkidle")
            page.wait_for_timeout(2000)
            team_url = find_team_page(page, company_website)
            if team_url and team_url != company_website:
                print(f"[Contact Agent] Found team page: {team_url}")
                page.goto(team_url, timeout=15000, wait_until="networkidle")
                page.wait_for_timeout(2000)
            else:
                print(f"[Contact Agent] No separate team page found, using homepage content")
            text_content = extract_visible_text(page)
            html_content = extract_html_content(page)
            print(f"[Contact Agent] Running LLM extraction...")
            contacts = extract_contacts_with_llm(text_content, html_content)
            print(f"[Contact Agent] Extracted {len(contacts)} contacts")
            for c in contacts:
                print(f"  - {c.get('name', 'N/A')} | {c.get('title', 'N/A')} | {c.get('email', 'N/A')}")
        except PlaywrightTimeout:
            print(f"[Contact Agent] Timeout accessing {company_website}")
        except Exception as e:
            print(f"[Contact Agent] Error: {e}")
        finally:
            browser.close()
    return contacts

if __name__ == "__main__":
    test_contacts = extract_contacts.invoke({"company_website": "https://www.example-pharma.com"})
    print(json.dumps(test_contacts, indent=2))
'''

with open(f"{output_dir}/tools/contact_agent.py", "w") as f:
    f.write(contact_agent)
print("contact_agent.py written")
