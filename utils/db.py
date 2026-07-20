"""
Database helpers:
  - SQLite  → deduplication (processed_companies table)
  - Neo4j   → save Company and Person nodes + WORKS_AT relationships
"""
import sqlite3
import logging
from datetime import datetime
from typing import Optional

from neo4j import GraphDatabase

from config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, SQLITE_PATH

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  SQLite — deduplication
# ══════════════════════════════════════════════════════════════════════════════

def _sqlite_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_sqlite() -> None:
    """Create the processed_companies table if it doesn't exist."""
    with _sqlite_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_companies (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL UNIQUE,
                website     TEXT,
                processed_at TEXT   NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
    logger.info("SQLite deduplication table ready.")


def is_company_processed(name: str) -> bool:
    """Return True if this company name has already been processed."""
    with _sqlite_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_companies WHERE LOWER(name) = LOWER(?)",
            (name.strip(),)
        ).fetchone()
    return row is not None


def mark_company_processed(name: str, website: str = "") -> None:
    """Record that a company has been processed (idempotent)."""
    with _sqlite_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO processed_companies (name, website, processed_at)
            VALUES (?, ?, ?)
            """,
            (name.strip(), website, datetime.utcnow().isoformat()),
        )
        conn.commit()


def get_processed_count() -> int:
    with _sqlite_conn() as conn:
        row = conn.execute("SELECT COUNT(*) FROM processed_companies").fetchone()
    return row[0]


# ══════════════════════════════════════════════════════════════════════════════
#  Neo4j — graph operations
# ══════════════════════════════════════════════════════════════════════════════

class Neo4jClient:
    """Thin wrapper around the Neo4j driver with helper methods."""

    def __init__(self) -> None:
        self._driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        )

    def close(self) -> None:
        self._driver.close()

    # ── Company ───────────────────────────────────────────────────────────────

    def save_company(self, data: dict) -> None:
        """
        MERGE a Company node and set all provided properties.
        data must contain at least {'name': str}.
        """
        name = data.get("name", "").strip()
        if not name:
            logger.warning("save_company: skipping empty name")
            return

        props = {k: v for k, v in data.items() if v}   # drop empty values

        with self._driver.session() as session:
            session.run(
                """
                MERGE (c:Company {name: $name})
                SET   c += $props,
                      c.updated_at = datetime()
                """,
                name=name,
                props=props,
            )
        logger.info("Neo4j: saved Company '%s'", name)

    # ── Contact / Person ──────────────────────────────────────────────────────

    def save_contact(self, contact: dict, company_name: str) -> None:
        """
        MERGE a Person node, link it to the Company with WORKS_AT.
        contact: {'name', 'title', 'email', ...}
        """
        person_name = contact.get("name", "").strip()
        if not person_name:
            logger.warning("save_contact: skipping contact with no name")
            return

        props = {k: v for k, v in contact.items() if v}

        with self._driver.session() as session:
            session.run(
                """
                MATCH  (c:Company {name: $company})
                MERGE  (p:Person  {name: $person_name})
                SET    p += $props,
                       p.updated_at = datetime()
                MERGE  (p)-[:WORKS_AT]->(c)
                """,
                company=company_name.strip(),
                person_name=person_name,
                props=props,
            )
        logger.info(
            "Neo4j: saved Person '%s' → Company '%s'", person_name, company_name
        )

    def save_contacts_bulk(self, contacts: list[dict], company_name: str) -> None:
        for contact in contacts:
            try:
                self.save_contact(contact, company_name)
            except Exception as exc:
                logger.error(
                    "Failed to save contact %s for %s: %s",
                    contact.get("name"), company_name, exc,
                )

    # ── Query ─────────────────────────────────────────────────────────────────

    def get_all_leads(self, since_date: Optional[str] = None) -> list[dict]:
        """
        Return all (Person, Company) rows added since since_date (ISO string).
        If since_date is None, return everything.
        """
        date_filter = (
            "AND c.updated_at >= datetime($since)"
            if since_date else ""
        )
        query = f"""
            MATCH (p:Person)-[:WORKS_AT]->(c:Company)
            WHERE 1=1 {date_filter}
            RETURN
                c.name        AS company,
                c.industry    AS industry,
                c.location    AS location,
                c.website     AS website,
                p.name        AS contact_name,
                p.title       AS title,
                p.email       AS email
            ORDER BY c.name, p.name
        """
        with self._driver.session() as session:
            result = session.run(query, since=since_date)
            return [record.data() for record in result]

    def company_exists(self, name: str) -> bool:
        with self._driver.session() as session:
            row = session.run(
                "MATCH (c:Company {name: $name}) RETURN c LIMIT 1", name=name
            ).single()
        return row is not None
