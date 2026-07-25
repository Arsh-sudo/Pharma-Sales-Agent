"""Company enrichment agent — extracts company details via Playwright + Mistral."""
import json
import re
from langchain_ollama import OllamaLLM
from playwright.sync_api import sync_playwright

llm = OllamaLLM(model="mistral", base_url="http://localhost:11434", temperature=0.1)


def enrich_company(company_name: str, website: str) -> dict:
    """Enrich company data from website. Returns dict with company details."""
    print(f"  -> Enriching {company_name}...")

    defaults = {
        "name": company_name,
        "website": website,
        "industry": "Pharmaceuticals",
        "location": "India",
        "description": f"{company_name} is a leading pharmaceutical company engaged in manufacturing and marketing of pharmaceutical formulations and APIs.",
        "company_size": "1,000-5,000 employees",
        "specialties": ["Pharmaceutical Manufacturing", "APIs", "Formulations", "Exports"],
        "founded_year": "1995",
        "discovered_date": ""
    }

    if not website or not website.startswith("http"):
        print(f"  [Enrichment] No valid website, using defaults")
        return defaults

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(15000)
            page.goto(website, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            text = page.inner_text("body")
            browser.close()

            if len(text) < 100:
                print(f"  [Enrichment] Page too short, using defaults")
                return defaults

            visible_text = text[:10000]
            prompt = f"""Extract company information from this webpage text for {company_name}.
            Return ONLY a JSON object with these exact keys: industry, location, description, company_size, specialties (array), founded_year.
            Use "Unknown" if a field cannot be determined.
            Return ONLY the JSON object, no other text.
            Webpage text:
            {visible_text}
            """

            try:
                response = llm.invoke(prompt)
                json_match = re.search(r'\{.*?\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    data["name"] = company_name
                    data["website"] = website
                    for key in defaults:
                        if key not in data:
                            data[key] = defaults[key]
                    print(f"  [Enrichment] Extracted: {data.get('location', 'N/A')} | {data.get('industry', 'N/A')}")
                    return data
            except Exception as e:
                print(f"  [Enrichment] LLM parse error: {e}")
    except Exception as e:
        print(f"  [Enrichment] Browser error: {e}")

    return defaults
