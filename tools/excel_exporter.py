"""Excel exporter — generates daily reports from Neo4j data."""
import os
import pandas as pd
from datetime import datetime
from langchain.tools import tool
from database.neo4j_helpers import get_all_leads, get_companies_without_contacts, get_pipeline_stats, mark_export

EXPORT_DIR = os.getenv("EXPORT_DIR", "./exports")


def _strip_tz(value):
    """Remove timezone info from datetime objects for Excel compatibility."""
    if hasattr(value, 'tzinfo') and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


@tool
def export_to_excel() -> str:
    """Export all leads to a dated Excel file. Returns the file path."""
    print("[Excel Exporter] Generating report...")
    os.makedirs(EXPORT_DIR, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"pharma_leads_{date_str}.xlsx"
    filepath = os.path.join(EXPORT_DIR, filename)

    leads = get_all_leads()
    no_contact = get_companies_without_contacts()
    stats = get_pipeline_stats()

    # Build contacts DataFrame
    contacts_rows = []
    for company in leads:
        base = {
            "Company Name": company.get("name", ""),
            "Website": company.get("website", ""),
            "Industry": company.get("industry", ""),
            "Location": company.get("location", ""),
            "Description": company.get("description", ""),
            "Company Size": company.get("company_size", ""),
            "Specialties": ", ".join(company.get("specialties", [])) if isinstance(company.get("specialties"), list) else str(company.get("specialties", "")),
            "Founded Year": company.get("founded_year", ""),
            "Discovered Date": _strip_tz(company.get("discovered_date", "")),
        }
        if company.get("contacts"):
            for contact in company["contacts"]:
                row = base.copy()
                row["Contact Name"] = contact.get("name", "")
                row["Contact Title"] = contact.get("title", "")
                row["Contact Email"] = contact.get("email", "")
                row["Department"] = contact.get("department", "")
                contacts_rows.append(row)
        else:
            row = base.copy()
            row["Contact Name"] = ""
            row["Contact Title"] = ""
            row["Contact Email"] = ""
            row["Department"] = "No contacts found"
            contacts_rows.append(row)

    df_contacts = pd.DataFrame(contacts_rows)

    # Build "no contacts" DataFrame
    no_contact_rows = []
    for company in no_contact:
        no_contact_rows.append({
            "Company Name": company.get("name", ""),
            "Website": company.get("website", ""),
            "Industry": company.get("industry", ""),
            "Location": company.get("location", ""),
            "Discovered Date": _strip_tz(company.get("discovered_date", "")),
        })
    df_no_contact = pd.DataFrame(no_contact_rows)

    # Build summary
    df_summary = pd.DataFrame({
        "Metric": ["Total Companies", "Total Contacts", "Companies Added Today", "Companies Without Contacts", "Report Generated"],
        "Value": [
            stats["total_companies"],
            stats["total_contacts"],
            stats["today_companies"],
            len(no_contact),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]
    })

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df_contacts.to_excel(writer, sheet_name="Leads with Contacts", index=False)
        df_no_contact.to_excel(writer, sheet_name="Companies No Contacts", index=False)
        df_summary.to_excel(writer, sheet_name="Summary", index=False)

        # Auto-resize columns
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            for col in ws.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if cell.value:
                            max_length = max(max_length, len(str(cell.value)))
                    except:
                        pass
                ws.column_dimensions[column].width = min(max_length + 3, 60)

    total_contacts = sum(len(c.get("contacts", [])) for c in leads)
    mark_export(filename, len(leads), total_contacts)

    print(f"[Excel Exporter] Report saved: {filepath}")
    print(f"  - Companies with contacts: {len([c for c in leads if c.get('contacts')])}")
    print(f"  - Companies without contacts: {len(no_contact)}")

    return filepath
