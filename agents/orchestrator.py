"""
Orchestrator - Pharma Lead Discovery Pipeline
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.discovery_agent import discover_pharma_companies
from tools.contact_agent import extract_contacts
from tools.enrichment_agent import enrich_company
from tools.excel_exporter import export_to_excel
from database.neo4j_helpers import save_company, save_contact, setup_schema, close_driver

def persist_company(company, enrichment):
    company_data = {
        "name": company.get("name", ""),
        "website": company.get("website", enrichment.get("website", "")),
        "industry": enrichment.get("industry", "Pharmaceuticals"),
        "location": enrichment.get("location", "India"),
        "description": enrichment.get("description", "Leading pharmaceutical company"),
        "company_size": enrichment.get("company_size", ""),
        "specialties": enrichment.get("specialties", ["Pharmaceuticals", "APIs", "Formulations"]),
        "founded_year": enrichment.get("founded_year", ""),
        "source": company.get("source", "discovery_agent")
    }
    return save_company(company_data)

def persist_contacts(contacts, company_name):
    saved_count = 0
    for contact in contacts:
        if contact.get("name"):
            if save_contact(contact, company_name):
                saved_count += 1
    return saved_count

def run_pipeline():
    print("=" * 70)
    print("  PHARMA LEAD DISCOVERY PIPELINE")
    print("=" * 70)
    print()

    setup_schema()

    print("[Step 1/5] Discovering NEW pharma companies from real sources...")
    companies = discover_pharma_companies()

    companies_with_websites = [c for c in companies if c.get("website") and c["website"].startswith("http")]
    companies_without_websites = [c for c in companies if not (c.get("website") and c["website"].startswith("http"))]

    print(f"\n[Discovery Summary]")
    print(f"  Total companies found: {len(companies)}")
    print(f"  With websites: {len(companies_with_websites)}")
    print(f"  Without websites: {len(companies_without_websites)}")

    print(f"\n[Step 2-4] Processing {len(companies_with_websites)} companies with websites...")

    for idx, company in enumerate(companies_with_websites, 1):
        name = company.get("name", "")
        website = company.get("website", "")

        print(f"\n[{idx}/{len(companies_with_websites)}] Processing: {name}")
        print(f"  Website: {website}")

        try:
            print("  -> Enriching company details...")
            enrichment = enrich_company(website)
            persist_company(company, enrichment)

            print("  -> Extracting contacts...")
            contacts = extract_contacts(website, name)
            saved = persist_contacts(contacts, name)
            print(f"  -> Saved {saved} contacts")
        except Exception as e:
            print(f"  -> Error: {e}")
            continue

    if companies_without_websites:
        print(f"\n[Saving {len(companies_without_websites)} companies without websites...]")
        for company in companies_without_websites:
            save_company({
                "name": company["name"],
                "website": "",
                "industry": "Pharmaceuticals",
                "location": "India",
                "description": "Pharmaceutical company - website not found",
                "company_size": "",
                "specialties": ["Pharmaceuticals"],
                "founded_year": "",
                "source": company.get("source", "unknown")
            })

    print("\n[Step 5/5] Generating Excel report...")
    excel_path = export_to_excel()
    close_driver()

    print("\n" + "=" * 70)
    print("  PIPELINE COMPLETE")
    print("=" * 70)
    print(f"  Report: {excel_path}")
    print("=" * 70)

if __name__ == "__main__":
    run_pipeline()
