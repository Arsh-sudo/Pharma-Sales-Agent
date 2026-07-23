
# ============================================
# 5. database/neo4j_helpers.py
# ============================================
neo4j_helpers = r'''"""
Neo4j Database Helper Functions
Handles all database operations for the Pharma Lead Discovery Pipeline.
"""

import os
from datetime import datetime
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "pharma-leads-2024")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def setup_schema():
    """Create constraints and indexes for optimal performance."""
    with driver.session() as session:
        session.run("CREATE CONSTRAINT company_name IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE")
        session.run("CREATE CONSTRAINT person_name_company IF NOT EXISTS FOR (p:Person) REQUIRE (p.name, p.company) IS UNIQUE")
        session.run("CREATE CONSTRAINT daily_export_date IF NOT EXISTS FOR (d:DailyExport) REQUIRE d.date IS UNIQUE")
        session.run("CREATE INDEX company_industry IF NOT EXISTS FOR (c:Company) ON (c.industry)")
        session.run("CREATE INDEX person_email IF NOT EXISTS FOR (p:Person) ON (p.email)")
        session.run("CREATE INDEX company_source IF NOT EXISTS FOR (c:Company) ON (c.source)")
    print("[Neo4j] Schema setup complete")

def save_company(company_data: dict) -> bool:
    """Save or update a Company node in Neo4j."""
    query = """
    MERGE (c:Company {name: $name})
    SET c.website = COALESCE($website, c.website, ""),
        c.industry = COALESCE($industry, c.industry, "Pharmaceuticals"),
        c.location = COALESCE($location, c.location, ""),
        c.description = COALESCE($description, c.description, ""),
        c.company_size = COALESCE($company_size, c.company_size, ""),
        c.specialties = COALESCE($specialties, c.specialties, []),
        c.founded_year = COALESCE($founded_year, c.founded_year, ""),
        c.source = COALESCE($source, c.source, ""),
        c.updated_at = datetime(),
        c.discovered_date = COALESCE(c.discovered_date, datetime())
    RETURN c.name AS company_name
    """
    try:
        with driver.session() as session:
            result = session.run(query, **company_data)
            record = result.single()
            if record:
                print(f"[Neo4j] Saved company: {record['company_name']}")
                return True
    except Exception as e:
        print(f"[Neo4j Error] save_company: {e}")
    return False

def company_exists(company_name: str) -> bool:
    query = "MATCH (c:Company {name: $name}) RETURN count(c) > 0 AS exists"
    with driver.session() as session:
        result = session.run(query, name=company_name)
        return result.single()["exists"]

def save_contact(contact_data: dict, company_name: str) -> bool:
    """Save a Person node and link it to a Company."""
    query = """
    MATCH (c:Company {name: $company_name})
    MERGE (p:Person {name: $name, company: $company_name})
    SET p.title = COALESCE($title, p.title, ""),
        p.email = COALESCE($email, p.email, ""),
        p.department = COALESCE($department, p.department, ""),
        p.updated_at = datetime()
    MERGE (p)-[:WORKS_AT]->(c)
    RETURN p.name AS contact_name
    """
    try:
        with driver.session() as session:
            result = session.run(
                query,
                company_name=company_name,
                name=contact_data.get("name", ""),
                title=contact_data.get("title", ""),
                email=contact_data.get("email", ""),
                department=contact_data.get("department", "")
            )
            record = result.single()
            if record:
                print(f"[Neo4j] Saved contact: {record['contact_name']} @ {company_name}")
                return True
    except Exception as e:
        print(f"[Neo4j Error] save_contact: {e}")
    return False

def get_all_leads() -> list:
    query = """
    MATCH (p:Person)-[:WORKS_AT]->(c:Company)
    RETURN c.name AS Company, c.website AS Website, c.industry AS Industry,
           c.location AS Location, c.description AS Description,
           p.name AS Contact, p.title AS Title, p.email AS Email,
           p.department AS Department, c.discovered_date AS DiscoveredDate
    ORDER BY c.name, p.name
    """
    with driver.session() as session:
        result = session.run(query)
        return [record.data() for record in result]

def get_companies_without_contacts() -> list:
    query = """
    MATCH (c:Company)
    WHERE NOT (c)<-[:WORKS_AT]-(:Person)
    RETURN c.name AS Company, c.website AS Website, c.industry AS Industry,
           c.location AS Location, c.description AS Description
    """
    with driver.session() as session:
        result = session.run(query)
        return [record.data() for record in result]

def mark_export_date():
    query = """
    MERGE (d:DailyExport {date: date()})
    SET d.exported_at = datetime()
    RETURN d.date AS export_date
    """
    with driver.session() as session:
        result = session.run(query)
        return result.single()["export_date"]

def get_pipeline_stats() -> dict:
    queries = {
        "total_companies": "MATCH (c:Company) RETURN count(c) AS count",
        "total_contacts": "MATCH (p:Person) RETURN count(p) AS count",
        "companies_today": "MATCH (c:Company) WHERE c.discovered_date >= date() RETURN count(c) AS count",
        "contacts_today": "MATCH (p:Person) WHERE p.updated_at >= datetime() - duration('P1D') RETURN count(p) AS count"
    }
    stats = {}
    with driver.session() as session:
        for key, query in queries.items():
            result = session.run(query)
            stats[key] = result.single()["count"]
    return stats

def close_driver():
    driver.close()
    print("[Neo4j] Driver closed")

if __name__ == "__main__":
    setup_schema()
    print("Pipeline stats:", get_pipeline_stats())
'''

with open(f"{output_dir}/database/neo4j_helpers.py", "w") as f:
    f.write(neo4j_helpers)
print("neo4j_helpers.py written")
