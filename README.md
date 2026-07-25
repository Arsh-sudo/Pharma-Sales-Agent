# Pharma Lead Discovery Pipeline

## Quick Start

1. Copy ALL files from this folder to `C:\Users\arsha\pharma-leads-pipeline\`
2. Update `.env` with your settings (email, passwords)
3. Double-click `run_pipeline.bat` to test
4. Set up Windows Task Scheduler for daily runs

## Files

| File | Purpose |
|------|---------|
| `agents/orchestrator.py` | Main pipeline runner |
| `tools/discovery_agent.py` | Scrapes pharma companies |
| `tools/contact_agent.py` | Extracts contacts via Playwright + Mistral |
| `tools/enrichment_agent.py` | Extracts company details |
| `tools/excel_exporter.py` | Generates Excel reports |
| `database/neo4j_helpers.py` | Neo4j database operations |
| `run_pipeline.bat` | Windows batch runner |
| `send_email.py` | Optional: Email the report |
| `.env` | Configuration |

## Prerequisites

- Python 3.10+
- Ollama with Mistral model
- Neo4j Desktop (running on localhost:7687)
- Playwright browsers installed

## Task Scheduler Setup

1. Open `taskschd.msc`
2. Create Basic Task → Name: `Pharma Pipeline Daily`
3. Trigger: Daily at 7:00 AM
4. Action: Start a program
5. Program: `C:\Users\arsha\pharma-leads-pipeline\run_pipeline.bat`
6. Start in: `C:\Users\arsha\pharma-leads-pipeline`
