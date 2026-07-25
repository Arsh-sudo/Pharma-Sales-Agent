"""
Excel Export Tool - Generates daily report
"""

import os
import pandas as pd
from datetime import datetime
from database.neo4j_helpers import get_all_leads, get_companies_without_contacts, mark_export_date

EXPORT_DIR = os.getenv("EXPORT_DIR", "./exports")

def ensure_export_dir():
    os.makedirs(EXPORT_DIR, exist_ok=True)

def auto_resize_columns(worksheet):
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if cell.value:
                    cell_length = len(str(cell.value))
                    if cell_length > max_length:
                        max_length = cell_length
            except:
                pass
        adjusted_width = min(max_length + 4, 70)
        worksheet.column_dimensions[column_letter].width = adjusted_width

def export_to_excel():
    ensure_export_dir()
    print("[Excel Exporter] Generating report...")

    leads_with_contacts = get_all_leads()
    companies_without_contacts = get_companies_without_contacts()

    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"pharma_leads_{date_str}.xlsx"
    filepath = os.path.join(EXPORT_DIR, filename)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        if leads_with_contacts:
            df_contacts = pd.DataFrame(leads_with_contacts)
            col_mapping = {
                "c.name": "Company", "c.website": "Website", "c.industry": "Industry",
                "c.location": "Location", "p.name": "Contact", "p.title": "Title",
                "p.email": "Email", "p.department": "Department",
                "c.description": "Description", "c.discovered_date": "DiscoveredDate"
            }
            df_contacts = df_contacts.rename(columns=col_mapping)
            expected_cols = ["Company", "Website", "Industry", "Location", "Contact",
                           "Title", "Email", "Department", "Description", "DiscoveredDate"]
            available_cols = [c for c in expected_cols if c in df_contacts.columns]
            df_contacts = df_contacts[available_cols]
            df_contacts.to_excel(writer, sheet_name="Leads with Contacts", index=False)
            auto_resize_columns(writer.sheets["Leads with Contacts"])
        else:
            pd.DataFrame({"Message": ["No contacts found."]}).to_excel(
                writer, sheet_name="Leads with Contacts", index=False)
            auto_resize_columns(writer.sheets["Leads with Contacts"])

        if companies_without_contacts:
            df_no_contacts = pd.DataFrame(companies_without_contacts)
            df_no_contacts = df_no_contacts.rename(columns={
                "c.name": "Company", "c.website": "Website", "c.industry": "Industry",
                "c.location": "Location", "c.description": "Description"
            })
            df_no_contacts.to_excel(writer, sheet_name="Companies No Contacts", index=False)
            auto_resize_columns(writer.sheets["Companies No Contacts"])
        else:
            pd.DataFrame({"Message": ["All companies have contacts."]}).to_excel(
                writer, sheet_name="Companies No Contacts", index=False)

        from database.neo4j_helpers import get_pipeline_stats
        stats = get_pipeline_stats()
        summary_df = pd.DataFrame([
            ["Total Companies", stats.get("total_companies", 0)],
            ["Total Contacts", stats.get("total_contacts", 0)],
            ["Companies Discovered Today", stats.get("companies_today", 0)],
            ["Contacts Added Today", stats.get("contacts_today", 0)],
            ["Export Date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
        ], columns=["Metric", "Value"])
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        auto_resize_columns(writer.sheets["Summary"])

    mark_export_date()
    print(f"[Excel Exporter] Saved: {filepath}")
    print(f"  - With contacts: {len(leads_with_contacts)}")
    print(f"  - Without contacts: {len(companies_without_contacts)}")
    return filepath

if __name__ == "__main__":
    filepath = export_to_excel()
    print(f"Export complete: {filepath}")
