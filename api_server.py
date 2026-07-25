"""
Flask API Server - Pharma Pipeline
n8n calls this API to run the pipeline
"""

from flask import Flask, jsonify
import subprocess
import os
import glob
from datetime import datetime

app = Flask(__name__)

PROJECT_DIR = r"C:\Users\arsha\pharma-leads-pipeline"
VENV_PYTHON = os.path.join(PROJECT_DIR, "venv", "Scripts", "python.exe")

def find_latest_report():
    export_dir = os.path.join(PROJECT_DIR, "exports")
    files = glob.glob(os.path.join(export_dir, "pharma_leads_*.xlsx"))
    if not files:
        return None
    return max(files, key=os.path.getctime)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()})

@app.route('/run-pipeline', methods=['POST'])
def run_pipeline():
    try:
        result = subprocess.run(
            [VENV_PYTHON, "agents/orchestrator.py"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=3600
        )
        report_path = find_latest_report()
        return jsonify({
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'report_path': report_path,
            'report_exists': report_path is not None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get-report-path', methods=['GET'])
def get_report_path():
    report_path = find_latest_report()
    return jsonify({
        'report_path': report_path,
        'exists': report_path is not None,
        'filename': os.path.basename(report_path) if report_path else None
    })

if __name__ == '__main__':
    print("Starting Pharma Pipeline API on http://localhost:5000")
    print("Endpoints: /health, /run-pipeline, /get-report-path")
    app.run(host='0.0.0.0', port=5000, debug=False)
