"""
Orchestrator
════════════
LangChain ZERO_SHOT_REACT_DESCRIPTION agent that:

  1. Calls DiscoverPharmaCompanies → list of new companies
  2. For each company:
       a. Calls EnrichCompany   → industry, location, description …
       b. Calls ExtractContacts → names, titles, emails …
       c. Saves Company + Person nodes to Neo4j
  3. Exports daily Excel report

Run directly:
    python orchestrator.py

Or import and call:
    from orchestrator import run_pipeline
    run_pipeline()
"""
import json
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

from langchain.agents import AgentType, Tool, initialize_agent
from langchain.callbacks import StdOutCallbackHandler
from langchain_community.llms import Ollama

from agents.contact_agent    import extract_contacts
from agents.discovery_agent  import discover_pharma_companies
from agents.enrichment_agent import enrich_company
from config.settings         import OLLAMA_BASE_URL, OLLAMA_MODEL, OUTPUT_DIR
from utils.db                import Neo4jClient, init_sqlite
from utils.export            import export_to_excel

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            LOG_DIR / f"pipeline_{datetime.utcnow().strftime('%Y%m%d')}.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("orchestrator")


# ── LLM ──────────────────────────────────────────────────────────────────────
def _get_llm() -> Ollama:
    return Ollama(
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_MODEL,
        temperature=0.0,
    )


# ── Tool wrappers (plain functions for direct calls below the agent) ──────────

def _run_discovery() -> list[dict]:
    """Run the Discovery tool and parse output."""
    logger.info("── Step 1: Discovery ─────────────────────────────────────────")
    raw = discover_pharma_companies.invoke({"dummy_input": ""})
    try:
        companies = json.loads(raw)
        logger.info("Discovered %d new companies", len(companies))
        return companies
    except json.JSONDecodeError:
        logger.error("Discovery tool returned non-JSON: %s", raw[:300])
        return []


def _run_enrichment(company: dict) -> dict:
    """Run the Enrichment tool for one company and parse output."""
    name    = company.get("name", "")
    website = company.get("website", "")
    inp     = f"{name}|||{website}" if website else name

    raw = enrich_company.invoke({"company_input": inp})
    try:
        enriched = json.loads(raw)
        return enriched
    except json.JSONDecodeError:
        logger.warning("Enrichment returned non-JSON for %s", name)
        return {"name": name, "website": website}


def _run_contact_extraction(company: dict) -> list[dict]:
    """Run the Contact Extraction tool for one company and parse output."""
    name    = company.get("name", "")
    website = company.get("website", "")

    if not website:
        logger.info("No website for %s — skipping contact extraction", name)
        return []

    inp = f"{name}|||{website}"
    raw = extract_contacts.invoke({"company_input": inp})
    try:
        contacts = json.loads(raw)
        logger.info("Extracted %d contacts for %s", len(contacts), name)
        return contacts
    except json.JSONDecodeError:
        logger.warning("Contact extraction returned non-JSON for %s", name)
        return []


# ── Core pipeline (deterministic, no agent reasoning loop) ────────────────────

def _process_company(company: dict, neo4j: Neo4jClient) -> None:
    """Enrich one company, extract its contacts, and save to Neo4j."""
    name = company.get("name", "").strip()
    if not name:
        return

    logger.info("Processing: %s", name)

    # Enrich
    enriched_data = _run_enrichment(company)
    # Merge discovery source info
    enriched_data.setdefault("source", company.get("source", ""))
    neo4j.save_company(enriched_data)

    # Contacts
    contacts = _run_contact_extraction(enriched_data)
    if contacts:
        neo4j.save_contacts_bulk(contacts, name)
    else:
        logger.info("No contacts found for %s", name)


# ── Agent-based orchestration (optional — used by run_pipeline_via_agent) ─────

def _build_agent_tools() -> list[Tool]:
    return [
        Tool(
            name="DiscoverPharmaCompanies",
            func=lambda _: discover_pharma_companies.invoke({"dummy_input": ""}),
            description=(
                "Find up to 10 new pharma companies from public tender sites, "
                "B2B portals, and news. Call with no arguments (empty string). "
                "Returns JSON list of {name, website, source}."
            ),
        ),
        Tool(
            name="EnrichCompany",
            func=lambda x: enrich_company.invoke({"company_input": x}),
            description=(
                "Get industry, location, size, and description for a company. "
                "Input: 'Company Name|||https://website.com' or just 'Company Name'. "
                "Returns JSON object."
            ),
        ),
        Tool(
            name="ExtractContacts",
            func=lambda x: extract_contacts.invoke({"company_input": x}),
            description=(
                "Extract contacts (name, title, email) from a company website. "
                "Input: 'Company Name|||https://website.com'. "
                "Returns JSON list of contact dicts."
            ),
        ),
    ]


def run_pipeline_via_agent() -> Path:
    """
    Let the LangChain ZERO_SHOT_REACT agent orchestrate the full pipeline.
    Useful for demos or when you want the LLM to decide tool order.
    Note: more unpredictable than run_pipeline(); prefer run_pipeline() for prod.
    """
    llm   = _get_llm()
    tools = _build_agent_tools()

    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        max_iterations=50,
        callbacks=[StdOutCallbackHandler()],
        handle_parsing_errors=True,
    )

    prompt = (
        "You are a pharmaceutical lead generation pipeline. "
        "Do the following in order:\n"
        "1. Call DiscoverPharmaCompanies (no arguments) to get today's company list.\n"
        "2. For each company in the list, call EnrichCompany then ExtractContacts.\n"
        "3. Report how many companies and contacts were processed.\n"
        "Do not skip any company. Start now."
    )

    try:
        result = agent.run(prompt)
        logger.info("Agent run complete: %s", result)
    except Exception as exc:
        logger.error("Agent run failed: %s\n%s", exc, traceback.format_exc())

    return export_to_excel()


# ── Main deterministic pipeline ───────────────────────────────────────────────

def run_pipeline() -> Path:
    """
    Deterministic version — runs each step in a controlled loop.
    Recommended for production / scheduled runs.
    Returns the path of the generated Excel file.
    """
    logger.info("═══════════════════════════════════════════════════════")
    logger.info("  Pharma Lead Pipeline  |  %s  (UTC)", datetime.utcnow().strftime("%Y-%m-%d %H:%M"))
    logger.info("═══════════════════════════════════════════════════════")

    init_sqlite()
    neo4j = Neo4jClient()

    try:
        # ── 1. Discover ───────────────────────────────────────────────────────
        companies = _run_discovery()
        if not companies:
            logger.warning("No new companies found today. Pipeline exiting.")
            return export_to_excel()

        # ── 2. Process each company ───────────────────────────────────────────
        logger.info("── Step 2: Enrich + Extract Contacts ─────────────────────")
        for i, company in enumerate(companies, 1):
            logger.info("[%d/%d] %s", i, len(companies), company.get("name"))
            try:
                _process_company(company, neo4j)
            except Exception as exc:
                logger.error(
                    "Failed processing %s: %s\n%s",
                    company.get("name"), exc, traceback.format_exc(),
                )

        # ── 3. Export ─────────────────────────────────────────────────────────
        logger.info("── Step 3: Export Excel ──────────────────────────────────")
        filepath = export_to_excel()

        logger.info("═══════════════════════════════════════════════════════")
        logger.info("  Pipeline complete — report: %s", filepath)
        logger.info("═══════════════════════════════════════════════════════")
        return filepath

    finally:
        neo4j.close()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pharma Lead Generation Pipeline")
    parser.add_argument(
        "--mode",
        choices=["deterministic", "agent"],
        default="deterministic",
        help="'deterministic' (default) runs a controlled loop; "
             "'agent' lets LangChain REACT decide the order.",
    )
    args = parser.parse_args()

    if args.mode == "agent":
        output = run_pipeline_via_agent()
    else:
        output = run_pipeline()

    print(f"\n✅  Report ready: {output}")
