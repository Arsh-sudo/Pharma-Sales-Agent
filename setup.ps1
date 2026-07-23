
# =============================================================================
# Pharma Lead Discovery Pipeline - Windows PowerShell Setup
# =============================================================================
# Run this in PowerShell as Administrator
# =============================================================================

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "     PHARMA LEAD DISCOVERY PIPELINE - WINDOWS SETUP                 " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$ProjectDir = "$env:USERPROFILE\pharma-leads-pipeline"
New-Item -ItemType Directory -Force -Path $ProjectDir | Out-Null
Set-Location $ProjectDir

Write-Host "[1/6] Installing Python 3.10..." -ForegroundColor Green
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    winget install Python.Python.3.10 --accept-source-agreements --accept-package-agreements
}

Write-Host ""
Write-Host "[2/6] Creating virtual environment..." -ForegroundColor Green
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel

Write-Host ""
Write-Host "[3/6] Installing Python packages..." -ForegroundColor Green
pip install langchain==0.2.0 langchain-community==0.2.0 langchain-ollama==0.1.0 `
    beautifulsoup4==4.12.3 requests==2.31.0 playwright==1.44.0 neo4j==5.20.0 `
    pandas==2.2.2 openpyxl==3.1.2 python-dotenv==1.0.1 lxml==5.2.2 `
    fake-useragent==1.5.1 tenacity==8.3.0

Write-Host ""
Write-Host "[4/6] Installing Playwright browsers..." -ForegroundColor Green
playwright install chromium

Write-Host ""
Write-Host "[5/6] Checking Ollama..." -ForegroundColor Green
$OllamaPath = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
if (-not (Test-Path $OllamaPath)) {
    Write-Host "    Please download Ollama from https://ollama.com/download/windows" -ForegroundColor Yellow
    Write-Host "    Then run: ollama pull mistral" -ForegroundColor Yellow
} else {
    Write-Host "    Ollama found. Pulling Mistral..." -ForegroundColor Green
    & $OllamaPath pull mistral
}

Write-Host ""
Write-Host "[6/6] Checking Neo4j..." -ForegroundColor Green
Write-Host "    Please download Neo4j Desktop from https://neo4j.com/download/" -ForegroundColor Yellow
Write-Host "    Create a local DB with password: pharma-leads-2024" -ForegroundColor Yellow

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "                    SETUP COMPLETE!                                   " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  Project:  $ProjectDir" -ForegroundColor White
Write-Host "  Next:    .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "           python agents\orchestrator.py" -ForegroundColor White
Write-Host "======================================================================" -ForegroundColor Cyan