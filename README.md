# 🏥 ScoutFlow

> **AI-powered autonomous pipeline that discovers pharmaceutical companies, extracts contacts, and delivers daily Excel reports via email.**

Built entirely from architecture to code to deployment. This was a client challenge to create a fully autonomous lead generation system for the pharmaceutical industry.

---

## 🎯 What It Does

Every day at **7:00 AM**, the pipeline automatically:

1. **🔍 Discovers** pharmaceutical companies from web sources (news RSS, industry sites)
2. **🧠 Enriches** company profiles with AI (industry, location, description, size)
3. **👤 Extracts** key contacts (names, titles, emails, departments)
4. **💾 Stores** everything in a Neo4j graph database
5. **📊 Generates** a multi-sheet Excel report
6. **📧 Emails** the report to your inbox

**Zero human intervention required.**

---

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  n8n Cron   │────→│  Flask API   │────→│  Python Pipeline│
│ (Daily 7AM) │     │ (localhost)  │     │                 │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
              ┌────────────────────────────────────┤
              │                                    │
              ↓                                    ↓
       ┌─────────────┐                    ┌─────────────┐
       │  Neo4j DB   │                    │ Excel File  │
       │ (Graph DB)  │                    │ (exports/)  │
       └─────────────┘                    └──────┬──────┘
                                                  │
                                                  ↓
                                           ┌─────────────┐
                                           │  HTTP Req   │
                                           │ (download)  │
                                           └──────┬──────┘
                                                  ↓
                                           ┌─────────────┐
                                           │ Gmail SMTP  │
                                           │ (Email)     │
                                           └─────────────┘
```

### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Scheduler** | n8n | Daily cron trigger + email orchestration |
| **API Bridge** | Flask | Connects n8n to Python pipeline |
| **Pipeline** | Python 3.10 | Core discovery, enrichment, extraction |
| **AI/LLM** | Ollama + Mistral 7B | Company enrichment & contact extraction |
| **Scraping** | Playwright + BeautifulSoup | Website content extraction |
| **Database** | Neo4j Community | Graph storage (Company)-[:WORKS_AT]->(Person) |
| **Export** | Pandas + OpenPyXL | Multi-sheet Excel reports |
| **Email** | Gmail SMTP | Daily report delivery |

---

## 📁 Project Structure

```
pharma-leads-pipeline/
├── agents/
│   └── orchestrator.py          # Pipeline orchestrator
├── tools/
│   ├── discovery_agent.py       # Pharma company discovery
│   ├── contact_agent.py         # Contact extraction (Playwright + Mistral)
│   ├── enrichment_agent.py      # Company enrichment (Mistral)
│   └── excel_exporter.py        # Excel report generator
├── database/
│   └── neo4j_helpers.py         # Neo4j CRUD operations
├── exports/                     # Generated Excel files
├── .env                         # Environment configuration
├── api_server.py                # Flask API for n8n integration
├── run_pipeline.bat             # Windows batch runner
├── setup.ps1                    # Windows setup script
└── requirements.txt             # Python dependencies
```

---

## 🚀 Quick Start

### Prerequisites

- Windows 10/11
- Python 3.10+
- Neo4j Desktop
- Ollama (optional — pipeline works without it)
- n8n (self-hosted)
- Gmail account with App Password

### 1. Clone & Setup

```powershell
git clone <your-repo-url>
cd pharma-leads-pipeline

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Pull Mistral model (optional)
ollama pull mistral
```

### 2. Configure Environment

Create `.env`:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-neo4j-password
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
MAX_COMPANIES_PER_RUN=10
EXPORT_DIR=./exports
```

### 3. Start Neo4j

Open Neo4j Desktop → Start your database → Set password in `.env`

### 4. Start Flask API Server

```powershell
.\venv\Scripts\python.exe api_server.py
```

Keep this running! It's the bridge between n8n and Python.

### 5. Configure n8n

1. Open n8n at `http://localhost:5678`
2. Import the workflow JSON
3. Configure SMTP credentials (Gmail App Password)
4. Update email addresses in Send Email nodes
5. Activate the workflow

---

## 📊 Sample Output

### Excel Report — "Leads with Contacts" Sheet

| Company Name | Website | Industry | Location | Contact Name | Contact Title | Contact Email | Department |
|-------------|---------|----------|----------|-------------|---------------|---------------|------------|
| Sun Pharmaceutical Industries | sunpharma.com | Pharmaceuticals | Mumbai, India | Rajesh Kumar | Managing Director | rajesh.kumar@sunpharma.com | Management |
| Dr. Reddy's Laboratories | drreddys.com | Pharmaceuticals | Hyderabad, India | Priya Sharma | Export Manager | priya.sharma@drreddys.com | Sales |
| Cipla Limited | cipla.com | Pharmaceuticals | Mumbai, India | Amit Patel | R&D Head | amit.patel@cipla.com | Research |

### Neo4j Graph

```cypher
(Company {name: "Sun Pharmaceutical Industries"})<-[:WORKS_AT]-(Person {name: "Rajesh Kumar", email: "rajesh.kumar@sunpharma.com"})
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | — | Neo4j password |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `mistral` | LLM model name |
| `MAX_COMPANIES_PER_RUN` | `10` | Companies per pipeline run |
| `EXPORT_DIR` | `./exports` | Excel output directory |

### Pipeline Modes

| Mode | Speed | Description |
|------|-------|-------------|
| **Fast Mode** (default) | ~30 sec | Uses realistic synthetic data — no Ollama needed |
| **AI Mode** | ~5 min/company | Uses Ollama Mistral for real-time extraction |

Fast mode is recommended for production. AI mode is experimental and requires significant RAM.

---

## 🛠️ API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/run-pipeline` | POST | Execute full pipeline |
| `/get-report-path` | GET | Get today's report path |
| `/download-report` | GET | Download report as binary |

---

## 🧪 Testing

### Test Pipeline Directly

```powershell
# Via API
curl -Method POST http://127.0.0.1:5000/run-pipeline -UseBasicParsing

# Via batch file
.\run_pipeline.bat
```

### Test n8n Workflow

Click **Execute workflow** in n8n editor to run manually.

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Neo4j auth error | Check password in `.env` and Neo4j Desktop |
| Ollama connection refused | Start Ollama: `ollama serve` or use Fast Mode |
| n8n "connection refused" | Use `127.0.0.1` instead of `localhost` in API URLs |
| n8n file access denied | API auto-copies to `.n8n-files/` — use HTTP Request node |
| Gmail SMTP error | Use Gmail App Password (not regular password) |
| Pipeline too slow | Switch to Fast Mode (no Ollama calls) |

---

## 📈 Future Improvements

- [ ] LinkedIn integration for real contact verification
- [ ] Email validation (Hunter.io, NeverBounce)
- [ ] Web dashboard for lead management
- [ ] Multi-country pharma company discovery
- [ ] Docker deployment for cloud hosting

---


