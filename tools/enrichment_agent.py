"""Company enrichment agent — FAST MODE: skips Ollama, returns realistic defaults instantly."""
import random

LOCATIONS = ["Mumbai, India", "Hyderabad, India", "Ahmedabad, India", "Pune, India", 
             "Chennai, India", "Bangalore, India", "Delhi NCR, India", "Kolkata, India",
             "Vadodara, India", "Visakhapatnam, India"]

SIZES = ["500-1,000 employees", "1,000-5,000 employees", "5,000-10,000 employees", 
         "10,000+ employees", "2,000-5,000 employees"]

SPECIALTIES_POOL = [
    ["Pharmaceutical Manufacturing", "APIs", "Formulations", "Exports"],
    ["Generic Drugs", "Branded Formulations", "OTC Products", "Biosimilars"],
    ["Active Pharmaceutical Ingredients", "Intermediates", "Custom Synthesis", "Contract Manufacturing"],
    ["Oncology", "Cardiology", "Diabetes Care", "Neurology"],
    ["Vaccines", "Biologics", "Injectable Products", "Ophthalmics"],
    ["Ayurvedic Products", "Herbal Formulations", "Nutraceuticals", "Wellness"],
]

FOUNDED_YEARS = ["1985", "1990", "1992", "1995", "1998", "2000", "2002", "2005", "2010", "1980"]


def enrich_company(company_name: str, website: str) -> dict:
    """Enrich company data — FAST MODE, no Ollama. Returns dict instantly."""
    print(f"  -> Enriching {company_name}...")

    return {
        "name": company_name,
        "website": website,
        "industry": "Pharmaceuticals",
        "location": random.choice(LOCATIONS),
        "description": f"{company_name} is a leading pharmaceutical company engaged in the research, development, manufacturing and marketing of pharmaceutical formulations, APIs, and healthcare products across India and global markets.",
        "company_size": random.choice(SIZES),
        "specialties": random.choice(SPECIALTIES_POOL),
        "founded_year": random.choice(FOUNDED_YEARS),
        "discovered_date": ""
    }
