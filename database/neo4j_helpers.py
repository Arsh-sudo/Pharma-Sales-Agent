"""Neo4j database helpers."""
import os
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "pharma-leads-2024")

_driver = None

def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver

def close_driver():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
        print("[Neo4j] Driver closed")

def setup_schema():
    driver = get_driver()
    with driver.session() as session:
        try:
            session.run("CREATE CONSTRAINT company_name IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE")
        except Exception as e:
            print(f"[Neo4j] Constraint may already exist: {e}")
        try:
            session.run("CREATE CONSTRAINT contact_email IF NOT EXISTS FOR (p:Person) REQUIRE p.email IS UNIQUE")
        except Exception as e:
            print(f"[Neo4j] Constraint may already exist: {e}")
        try:
            session.run("CREATE INDEX company_website IF NOT EXISTS FOR (c:Company) ON (c.website)")
        except Exception as e:
            print(f"[Neo4j] Index may already exist: {e}")
    print("[Neo4j] Schema setup complete")

def save_company(company_data: dict):
    driver = get_driver()
    with driver.session() as session:
        session.run("""
            MERGE (c:Company {name: $name})
            SET c.website = $website,
                c.industry = $industry,
                c.location = $location,
                c.description = $description,
                c.company_size = $company_size,
                c.specialties = $specialties,
                c.founded_year = $founded_year,
                c.discovered_date = datetime()
        """, company_data)

def save_contact(contact_data: dict, company_name: str):
    driver = get_driver()
    with driver.session() as session:
        session.run("""
            MATCH (c:Company {name: $company_name})
            MERGE (p:Person {email: $email})
            SET p.name = $name,
                p.title = $title,
                p.department = $department
            MERGE (p)-[:WORKS_AT]->(c)
        """, {"company_name": company_name, **contact_data})

def get_all_leads():
    driver = get_driver()
    with driver.session() as session:
        result = session.run("""
            MATCH (c:Company)
            OPTIONAL MATCH (p:Person)-[:WORKS_AT]->(c)
            RETURN c, collect(p) as contacts
            ORDER BY c.discovered_date DESC
        """)
        leads = []
        for record in result:
            company = dict(record["c"])
            company["contacts"] = [dict(p) for p in record["contacts"]]
            leads.append(company)
    return leads

def get_companies_without_contacts():
    driver = get_driver()
    with driver.session() as session:
        result = session.run("""
            MATCH (c:Company)
            WHERE NOT (c)<-[:WORKS_AT]-(:Person)
            RETURN c
        """)
        companies = [dict(record["c"]) for record in result]
    return companies

def get_pipeline_stats():
    driver = get_driver()
    with driver.session() as session:
        total_companies = session.run("MATCH (c:Company) RETURN count(c) as total").single()["total"]
        total_contacts = session.run("MATCH (p:Person) RETURN count(p) as total").single()["total"]
        today_companies = session.run("""
            MATCH (c:Company)
            WHERE c.discovered_date >= datetime({epochSeconds: timestamp() / 1000 * 1000 - 86400})
            RETURN count(c) as total
        """).single()["total"]
    return {
        "total_companies": total_companies,
        "total_contacts": total_contacts,
        "today_companies": today_companies
    }

def mark_export(filename: str, companies_count: int, contacts_count: int):
    driver = get_driver()
    with driver.session() as session:
        session.run("""
            CREATE (e:Export {filename: $filename, companies_count: $companies_count, contacts_count: $contacts_count, exported_at: datetime()})
        """, {"filename": filename, "companies_count": companies_count, "contacts_count": contacts_count})

def is_company_processed(name: str) -> bool:
    """Check if a company has already been processed."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run("MATCH (c:Company {name: $name}) RETURN count(c) as count", {"name": name})
        count = result.single()["count"]
    return count > 0

def mark_company_processed(name: str, source: str = "pipeline"):
    """Mark a company as processed."""
    driver = get_driver()
    with driver.session() as session:
        session.run("""
            MERGE (c:Company {name: $name})
            SET c.source = $source,
                c.discovered_date = datetime()
        """, {"name": name, "source": source})
