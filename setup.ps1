# =============================================================================
# Pharma Lead Pipeline - Windows Setup
# Run:
# Set-ExecutionPolicy Bypass -Scope Process
# .\setup.ps1
# =============================================================================

$ErrorActionPreference = "Stop"

function Info($msg)  { Write-Host "[INFO]  $msg" -ForegroundColor Green }
function Warn($msg)  { Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function ErrorExit($msg) {
    Write-Host "[ERROR] $msg" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Checking Python ===`n"

# -----------------------------------------------------------------------------
# Python
# -----------------------------------------------------------------------------

$python = Get-Command python -ErrorAction SilentlyContinue

if (!$python) {
    ErrorExit "Python not found. Install Python 3.10+ from https://python.org and check 'Add Python to PATH'."
}

Info "Using $(& python --version)"

# -----------------------------------------------------------------------------
# Virtual Environment
# -----------------------------------------------------------------------------

Write-Host "`n=== Virtual Environment ===`n"

if (!(Test-Path ".\venv")) {
    Info "Creating virtual environment..."
    python -m venv venv
}
else {
    Info "Virtual environment already exists."
}

& ".\venv\Scripts\Activate.ps1"

Info "Virtual environment activated."

python -m pip install --upgrade pip setuptools wheel

# -----------------------------------------------------------------------------
# Python Packages
# -----------------------------------------------------------------------------

Write-Host "`n=== Installing Python Packages ===`n"

pip install `
langchain==0.2.16 `
langchain-community==0.2.16 `
langchain-core==0.2.38 `
beautifulsoup4==4.12.3 `
requests==2.32.3 `
playwright==1.47.0 `
neo4j==5.24.0 `
pandas==2.2.3 `
openpyxl==3.1.5 `
python-dotenv==1.0.1 `
lxml==5.3.0 `
httpx==0.27.2

Info "Installing Playwright browser..."
playwright install chromium

# -----------------------------------------------------------------------------
# Ollama
# -----------------------------------------------------------------------------

Write-Host "`n=== Ollama ===`n"

$ollama = Get-Command ollama -ErrorAction SilentlyContinue

if (!$ollama) {

    Warn "Ollama not installed."
    Warn "Download from:"
    Write-Host "https://ollama.com/download/windows"

    Read-Host "Install Ollama then press ENTER"

}

Info "Pulling Mistral model..."
ollama pull mistral

# -----------------------------------------------------------------------------
# Neo4j
# -----------------------------------------------------------------------------

Write-Host "`n=== Neo4j ===`n"

Warn "Install Neo4j Desktop:"
Write-Host "https://neo4j.com/download/"

Warn "Create a local database."
Warn "Remember your password."

# -----------------------------------------------------------------------------
# .env
# -----------------------------------------------------------------------------

Write-Host "`n=== Creating .env ===`n"

if (!(Test-Path ".env")) {

@"
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# Pipeline
MAX_COMPANIES_PER_RUN=10
OUTPUT_DIR=./output
LOG_LEVEL=INFO

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your_app_password
REPORT_RECIPIENT=recipient@example.com
"@ | Out-File ".env" -Encoding utf8

Info ".env created."

}
else {

Info ".env already exists."

}

# -----------------------------------------------------------------------------
# Output Folder
# -----------------------------------------------------------------------------

if (!(Test-Path ".\output")) {
    New-Item -ItemType Directory output | Out-Null
}

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------

Write-Host ""
Write-Host "===================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Python      : $(& python --version)"
Write-Host "Venv        : .\venv"
Write-Host "Neo4j       : http://localhost:7474"
Write-Host "Ollama      : Mistral Installed"

Write-Host ""
Write-Host "Activate environment using:"
Write-Host ".\venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Then run:"
Write-Host "python orchestrator.py"