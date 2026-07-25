# Pharma Lead Discovery Pipeline - n8n Edition

## What Changed

### Real Discovery (Not Just Demo List)
The pipeline now tries to find REAL companies from:
1. **Pharma News RSS Feeds** - FiercePharma, PharmaTimes, etc.
2. **Government Tender Portals** - eProcurement, BidAssist
3. **Startup Databases** - ZaubaCorp, etc.
4. **Verified Real Companies** - Only used as fallback if scraping finds < 3 companies:
   - Mankind Pharma, Alkem Labs, Intas Pharma, Cadila, Wockhardt
   - Laurus Labs, Divi's Labs, Granules India, Aurobindo, Biocon

### n8n Integration
- Flask API server (`api_server.py`) runs locally
- n8n calls the API via HTTP Request nodes
- No Code node needed (avoids sandbox restrictions)

## Setup

### 1. Install Flask
```powershell
cd C:\Users\arsha\pharma-leads-pipeline
.\venv\Scripts\Activate.ps1
pip install flask
```

### 2. Start API Server (Keep Running!)
```powershell
cd C:\Users\arsha\pharma-leads-pipeline
.\venv\Scripts\python.exe api_server.py
```

### 3. Test Pipeline
```powershell
cd C:\Users\arsha\pharma-leads-pipeline
run_pipeline.bat
```

### 4. Import n8n Workflow
1. Open http://localhost:5678
2. Workflows -> Import from File -> Select `n8n_workflow.json`
3. Update email addresses in Gmail nodes
4. Configure Gmail OAuth2 credentials
5. Activate workflow

## How It Works

```
Daily 7AM (n8n Cron)
    |
    v
HTTP Request -> POST http://localhost:5000/run-pipeline
    |
    v
Flask API -> Runs Python Pipeline
    |
    v
Discovery Agent -> Scrapes real sources OR uses verified fallback
    |
    v
Enrichment + Contact Agents -> Process each company
    |
    v
Neo4j -> Stores companies and contacts
    |
    v
Excel Export -> Generates dated report
    |
    v
HTTP Request -> GET report path
    |
    v
Read Excel -> Send Gmail with attachment
```
