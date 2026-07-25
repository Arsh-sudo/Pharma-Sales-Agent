"""Pharma Lead Discovery Pipeline — Direct Execution Mode."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.neo4j_helpers import setup_schema, save_company, save_contact, close_driver
from tools.discovery_agent import discover_pharma_companies
from tools.contact_agent import extract_contacts
from tools.enrichment_agent import enrich_company
from tools.excel_exporter import export_to_excel


def run_pipeline():
    """Run the full pipeline: Discover -> Enrich -> Extract Contacts -> Save -> Export."""
    print("=" * 70)
    print("  PHARMA LEAD DISCOVERY PIPELINE")
    print("=" * 70)
    print()

    setup_schema()

    print("[Step 1/5] Discovering companies...")
    companies = discover_pharma_companies()

    if not companies:
        print("[!] No companies found. Exiting.")
        close_driver()
        return

    print(f"Found {len(companies)} companies\n")

    for idx, company in enumerate(companies, 1):
        name = company.get("name", "Unknown")
        website = company.get("website", "")

        print(f"[{idx}/{len(companies)}] Processing: {name}")
        print(f"  Website: {website}")

        if not website:
            print(f"  Skipping {name}: No valid website\n")
            continue

        print("  -> Enriching...")
        enriched = enrich_company(name, website)
        enriched["discovered_date"] = __import__("datetime").datetime.now().isoformat()
        save_company(enriched)

        print("  -> Extracting contacts...")
        contacts = extract_contacts(name, website)

        if contacts:
            for contact in contacts:
                save_contact(contact, name)
            print(f"  -> Saved {len(contacts)} contacts\n")
        else:
            print("  -> No contacts found\n")

    print("[Step 5/5] Generating Excel report...")
    report_path = export_to_excel()

    close_driver()

    print()
    print("=" * 70)
    print("  PIPELINE COMPLETE")
    print(f"  Report: {report_path}")
    print("=" * 70)

    return report_path


if __name__ == "__main__":
    run_pipeline()
