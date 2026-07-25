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
from tools.demo_companies import get_demo_companies
from database.neo4j_helpers import save_company, save_contact, setup_schema, close_driver

def persist_company(company, enrichment):
    company_data = {
        "name": company.get("name", ""),
        "website": company.get("website", enrichment.get("website", "")),
        "industry": enrichment.get("industry", "Pharmaceuticals"),
        "location": enrichment.get("location", ""),
        "description": enrichment.get("description", ""),
        "company_size": enrichment.get("company_size", ""),
        "specialties": enrichment.get("specialties", []),
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

    print("[Step 1/5] Discovering companies...")
    companies = discover_pharma_companies()

    companies_with_websites = [c for c in companies if c.get("website") and c["website"].startswith("http")]

    if not companies_with_websites:
        print("\n[!] No companies with valid websites found from scraping.")
        print("[!] Using demo companies...")
        companies = get_demo_companies(3)
        print(f"[Demo] Loaded {len(companies)} companies:")
        for c in companies:
            print(f"  - {c['name']} | {c['website']}")
    else:
        companies = companies_with_websites

    print(f"\n[Step 2-4] Processing {len(companies)} companies...")

    for idx, company in enumerate(companies, 1):
        name = company.get("name", "")
        website = company.get("website", "")

        if not website or not website.startswith("http"):
            print(f"\nSkipping {name}: No valid website")
            continue

        print(f"\n[{idx}/{len(companies)}] Processing: {name}")
        print(f"  Website: {website}")

        try:
            print("  -> Enriching...")
            enrichment = enrich_company(website)
            persist_company(company, enrichment)

            print("  -> Extracting contacts...")
            contacts = extract_contacts(website, name)  # Pass company name!
            saved = persist_contacts(contacts, name)
            print(f"  -> Saved {saved} contacts")
        except Exception as e:
            print(f"  -> Error: {e}")
            continue

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
