"""
Enrichment Agent - Extracts company business details using Ollama Mistral
"""

import json
import re
from playwright.sync_api import sync_playwright
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
{{
  "company_name": "Official company name",
  "industry": "Primary industry (e.g., Pharmaceuticals, Biotechnology, Healthcare)",
  "location": "City, Country or headquarters location (e.g., Mumbai, India)",
  "description": "Brief 2-3 sentence company description including what they manufacture",
  "company_size": "Approximate employee count or size category",
  "specialties": ["List of key products, services, or specialties"],
  "founded_year": "Year founded if mentioned",
  "website": "Company website URL"
}}

If a field is not found, use your best guess based on the company type (Indian pharmaceutical company).
For location, typical Indian pharma hubs are: Mumbai, Hyderabad, Ahmedabad, Bangalore, Pune, Chennai.
Do not include any explanation or markdown formatting.
""")

def extract_page_text(page):
    try:
        return page.evaluate("""
            () => {
                const scripts = document.querySelectorAll('script, style, nav, footer, noscript, iframe');
                scripts.forEach(el => el.remove());
                return document.body.innerText.substring(0, 12000);
            }
        """) or ""
    except:
        return ""

def parse_enrichment_response(response):
    try:
        json_match = re.search(r'\{.*?\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(response)
    except:
        return {
            "company_name": "",
            "industry": "Pharmaceuticals",
            "location": "India",
            "description": "Leading pharmaceutical company",
            "company_size": "",
            "specialties": ["Pharmaceuticals", "APIs", "Formulations"],
            "founded_year": "",
            "website": ""
        }

def enrich_company(company_website):
    """Extract business details from company website."""
    if not company_website or not company_website.startswith("http"):
        print(f"[Enrichment] Invalid website: {company_website}")
        return {
            "company_name": "",
            "industry": "Pharmaceuticals",
            "location": "India",
            "description": "Leading pharmaceutical company",
            "company_size": "",
            "specialties": ["Pharmaceuticals", "APIs", "Formulations"],
            "founded_year": "",
            "website": company_website
        }

    print(f"[Enrichment] Enriching: {company_website}")
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
            text_content = text_content[:10000]
            prompt = ENRICHMENT_PROMPT.format(text_content=text_content)
            response = llm.invoke(prompt)
            enrichment_data = parse_enrichment_response(response)
            enrichment_data["website"] = company_website

            # Ensure defaults for empty fields
            if not enrichment_data.get("location"):
                enrichment_data["location"] = "India"
            if not enrichment_data.get("description"):
                enrichment_data["description"] = "Pharmaceutical company"
            if not enrichment_data.get("industry"):
                enrichment_data["industry"] = "Pharmaceuticals"

            print("[Enrichment] Extracted:")
            for key, value in enrichment_data.items():
                print(f"  {key}: {value}")
            return enrichment_data
        except Exception as e:
            print(f"[Enrichment] Error: {e}")
            return {
                "company_name": "",
                "industry": "Pharmaceuticals",
                "location": "India",
                "description": "Leading pharmaceutical company",
                "company_size": "",
                "specialties": ["Pharmaceuticals", "APIs", "Formulations"],
                "founded_year": "",
                "website": company_website
            }
        finally:
            browser.close()

if __name__ == "__main__":
    result = enrich_company("https://www.sunpharma.com")
    print(json.dumps(result, indent=2))
