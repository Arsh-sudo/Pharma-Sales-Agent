# Pharma Lead Generation Pipeline

Autonomous daily pipeline that discovers new pharmaceutical companies, extracts contacts, stores everything in Neo4j, and delivers a formatted Excel report via email.

## Architecture

```
Scheduler (cron / n8n)
    └─▶ Discovery Agent  (TenderTiger + IndiaMart + Google News)
            └─▶ Orchestrator
                    ├─▶ Enrichment Agent  (industry, location, description)
                    ├─▶ Contact Agent     (Playwright + Mistral 7B)
                    └─▶ Neo4j → Excel → Email
```

## Quick Start

```bash
# 1. Clone / unzip the project
cd pharma-pipeline

# 2. Run setup (installs everything)
chmod +x setup.sh
sudo ./setup.sh          # Linux
./setup.sh               # macOS (no sudo needed)

# 3. Edit credentials
nano .env                # set NEO4J_PASSWORD

# 4. Run manually
source venv/bin/activate
python orchestrator.py
```

## Files

| File | Purpose |
|---|---|
| `setup.sh` | One-command environment setup |
| `orchestrator.py` | Main entry point — runs the full pipeline |
| `agents/discovery_agent.py` | Scrapes tender/B2B sites for new companies |
| `agents/contact_agent.py` | Playwright + Mistral for contact extraction |
| `agents/enrichment_agent.py` | Enriches companies with industry/location data |
| `utils/db.py` | SQLite deduplication + Neo4j helpers |
| `utils/export.py` | Styled Excel export |
| `n8n_workflow.json` | Import into n8n for scheduling + email delivery |
| `config/settings.py` | Central config loaded from `.env` |

## n8n Setup

1. Import `n8n_workflow.json` via Workflows → Import from File
2. Add Gmail OAuth2 credentials
3. Update the two `path` placeholders with your project directory
4. Activate the workflow

## Environment Variables (`.env`)

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
MAX_COMPANIES_PER_RUN=10
OUTPUT_DIR=./output
```

## Running Modes

```bash
# Default — deterministic, controlled loop (recommended for production)
python orchestrator.py

# Agent mode — LangChain REACT agent decides tool order (for demos)
python orchestrator.py --mode agent
```

## Output

- Excel report: `output/pharma_leads_YYYYMMDD.xlsx`
- Logs: `logs/pipeline_YYYYMMDD.log`
- Neo4j: browse at `http://localhost:7474`
