@echo off
echo ===========================================
echo   PHARMA PIPELINE - DAILY RUN
echo ===========================================
echo.

cd /d "C:\Users\arsha\pharma-leads-pipeline"

echo [1/3] Activating virtual environment...
call "C:\Users\arsha\pharma-leads-pipeline\venv\Scripts\activate.bat"

echo [2/3] Running pipeline...
"C:\Users\arsha\pharma-leads-pipeline\venv\Scripts\python.exe" "C:\Users\arsha\pharma-leads-pipeline\agents\orchestrator.py"

echo [3/3] Pipeline complete. Checking for report...
if exist "exports\pharma_leads_*.xlsx" (
    echo Report generated successfully.
) else (
    echo WARNING: No report found.
)

echo.
echo ===========================================
echo   DONE
echo ===========================================
pause
