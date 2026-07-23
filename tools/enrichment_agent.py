
# ============================================
# 4. tools/enrichment_agent.py
# ============================================
enrichment_agent = r'''"""
Enrichment Agent - Company Details Extraction Tool
Scrapes a company's website to extract general business information
(industry, location, description, size, etc.) using Ollama Mistral.
"""

import json
import re
from typing import Dict
from playwright.sync_api import sync_playwright
from langchain.tools import tool
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate

llm = OllamaLLM(
    model="mistral",
    base_url="http://localhost:11434",
    temperature=0.1,
    timeout=120
)

ENRICHMENT_PROMPT = PromptTemplate.from_template("""
You are a business intelligence analyst. Extract structured company information
from the following webpage content.

WEBPAGE CONTENT:
{text_content}

Extract and return ONLY a valid JSON object with these fields:
{
  "company_name": "Official company name",
  "industry": "Primary industry (e.g., Pharmaceuticals, Biotechnology, Healthcare)",
  "location": "City, Country or headquarters location",
  "description": "Brief 2-3 sentence company description",
  "company_size": "Approximate employee count or size category",
  "specialties": ["List of key products, services, or specialties"],
  "founded_year": "Year founded if mentioned",
  "website": "Company website URL"
}

If a field is not found, use null or empty string.
Do not include any explanation or markdown formatting.
""")

def extract_page_text(page) -> str:
    try:
        return page.evaluate("""
            () => {
                const scripts = document.querySelectorAll('script, style, nav, footer, noscript, iframe');
                scripts.forEach(el => el.remove());
                return document.body.innerText.substring(0, 10000);
            }
        """) or ""
    except:
        return ""

def parse_enrichment_response(response: str) -> Dict:
    try:
        json_match = re.search(r'\{.*?\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(response)
    except:
        return {
            "company_name": "",
            "industry": "Pharmaceuticals",
            "location": "",
            "description": "",
            "company_size": "",
            "specialties": [],
            "founded_year": "",
            "website": ""
        }

@tool
def enrich_company(company_website: str) -> Dict:
    """
    Given a company's website URL, extract general business details
    (industry, location, description, size, specialties) using Ollama Mistral.
    Returns a dict with company enrichment data.
    """
    if not company_website or not company_website.startswith("http"):
        print(f"[Enrichment Agent] Invalid website URL: {company_website}")
        return {
            "company_name": "",
            "industry": "Pharmaceuticals",
            "location": "",
            "description": "",
            "company_size": "",
            "specialties": [],
            "founded_year": "",
            "website": company_website
        }
    print(f"[Enrichment Agent] Enriching company data from: {company_website}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        try:
            page.goto(company_website, timeout=15000, wait_until="networkidle")
            page.wait_for_timeout(2000)
            text_content = extract_page_text(page)
            text_content = text_content[:8000]
            prompt = ENRICHMENT_PROMPT.format(text_content=text_content)
            response = llm.invoke(prompt)
            enrichment_data = parse_enrichment_response(response)
            enrichment_data["website"] = company_website
            print(f"[Enrichment Agent] Extracted data:")
            for key, value in enrichment_data.items():
                print(f"  {key}: {value}")
            return enrichment_data
        except Exception as e:
            print(f"[Enrichment Agent] Error: {e}")
            return {
                "company_name": "",
                "industry": "Pharmaceuticals",
                "location": "",
                "description": "",
                "company_size": "",
                "specialties": [],
                "founded_year": "",
                "website": company_website
            }
        finally:
            browser.close()

if __name__ == "__main__":
    result = enrich_company.invoke({"company_website": "https://www.example-pharma.com"})
    print(json.dumps(result, indent=2))
'''

with open(f"{output_dir}/tools/enrichment_agent.py", "w") as f:
    f.write(enrichment_agent)
print("enrichment_agent.py written")
