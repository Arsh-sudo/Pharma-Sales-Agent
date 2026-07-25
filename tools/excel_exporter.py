"""
Excel Export Tool - Generates daily report from Neo4j data
"""

import os
import pandas as pd
from datetime import datetime
from database.neo4j_helpers import get_all_leads, get_companies_without_contacts, mark_export_date

EXPORT_DIR = os.getenv("EXPORT_DIR", "./exports")

def ensure_export_dir():
    os.makedirs(EXPORT_DIR, exist_ok=True)

def export_to_excel():
    """
    Query Neo4j and generate dated Excel report.
    Returns the file path.
    """
    ensure_export_dir()
    print("[Excel Exporter] Generating daily report...")

    leads_with_contacts = get_all_leads()
    companies_without_contacts = get_companies_without_contacts()

    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"pharma_leads_{date_str}.xlsx"
    filepath = os.path.join(EXPORT_DIR, filename)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        if leads_with_contacts:
            df_contacts = pd.DataFrame(leads_with_contacts)
            col_order = [
                "Company", "Website", "Industry", "Location",
                "Contact", "Title", "Email", "Department",
                "Description", "DiscoveredDate"
            ]
            df_contacts = df_contacts[[c for c in col_order if c in df_contacts.columns]]
            df_contacts.to_excel(writer, sheet_name="Leads with Contacts", index=False)
            worksheet = writer.sheets["Leads with Contacts"]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if cell.value:
                            max_length = max(max_length, len(str(cell.value)))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        else:
            pd.DataFrame({"Message": ["No contacts found yet."]}).to_excel(
                writer, sheet_name="Leads with Contacts", index=False
            )

        if companies_without_contacts:
            df_no_contacts = pd.DataFrame(companies_without_contacts)
            df_no_contacts.to_excel(writer, sheet_name="Companies No Contacts", index=False)
        else:
            pd.DataFrame({"Message": ["All companies have contacts."]}).to_excel(
                writer, sheet_name="Companies No Contacts", index=False
            )

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

    mark_export_date()
    print(f"[Excel Exporter] Report saved: {filepath}")
    print(f"  - Companies with contacts: {len(leads_with_contacts)}")
    print(f"  - Companies without contacts: {len(companies_without_contacts)}")
    return filepath

if __name__ == "__main__":
    filepath = export_to_excel()
    print(f"Export complete: {filepath}")
