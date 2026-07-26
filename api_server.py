"""Flask API server to bridge n8n and the Python pipeline."""
from flask import Flask, jsonify, send_file
import subprocess
import os
import glob
import shutil
from datetime import datetime

app = Flask(__name__)

PROJECT_DIR = r"C:\Users\arsha\pharma-leads-pipeline"
EXPORT_DIR = os.path.join(PROJECT_DIR, "exports")
# n8n can ONLY read from this directory
N8N_FILES_DIR = r"C:\Users\arsha\.n8n-files\exports"


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def _copy_to_n8n_dir(source_path: str) -> str:
    """Copy the generated Excel to n8n's allowed directory."""
    _ensure_dir(N8N_FILES_DIR)
    filename = os.path.basename(source_path)
    dest_path = os.path.join(N8N_FILES_DIR, filename)
    shutil.copy2(source_path, dest_path)
    return dest_path


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "time": datetime.now().isoformat()
    })


@app.route('/run-pipeline', methods=['POST'])
def run_pipeline():
    try:
        result = subprocess.run(
            [os.path.join(PROJECT_DIR, "venv", "Scripts", "python.exe"),
             os.path.join(PROJECT_DIR, "agents", "orchestrator.py")],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=3600
        )

        # Find today's report
        today = datetime.now().strftime("%Y%m%d")
        pattern = os.path.join(EXPORT_DIR, f"pharma_leads_{today}*.xlsx")
        files = glob.glob(pattern)

        report_exists = len(files) > 0
        report_path = ""
        n8n_path = ""

        if report_exists:
            report_path = files[0]
            n8n_path = _copy_to_n8n_dir(report_path)

        return jsonify({
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "report_exists": report_exists,
            "report_path": n8n_path,  # Return the n8n-accessible path
            "original_path": report_path
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "report_exists": False,
            "report_path": ""
        }), 500


@app.route('/get-report-path', methods=['GET'])
def get_report_path():
    today = datetime.now().strftime("%Y%m%d")
    # Look in n8n allowed directory
    pattern = os.path.join(N8N_FILES_DIR, f"pharma_leads_{today}*.xlsx")
    files = glob.glob(pattern)

    if files:
        return jsonify({
            "report_exists": True,
            "report_path": files[0]
        })
    else:
        return jsonify({
            "report_exists": False,
            "report_path": ""
        })


@app.route('/download-report', methods=['GET'])
def download_report():
    """Alternative: serve the file directly via HTTP."""
    today = datetime.now().strftime("%Y%m%d")
    pattern = os.path.join(N8N_FILES_DIR, f"pharma_leads_{today}*.xlsx")
    files = glob.glob(pattern)

    if files:
        return send_file(files[0], as_attachment=True)
    else:
        return jsonify({"error": "No report found"}), 404


if __name__ == '__main__':
    print("Starting Pharma Pipeline API on http://localhost:5000")
    print("Endpoints: /health, /run-pipeline, /get-report-path, /download-report")
    app.run(host='0.0.0.0', port=5000, debug=False)
