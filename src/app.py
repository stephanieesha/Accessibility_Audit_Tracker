"""
Web UI: paste a URL, get an accessibility scan back. Runs the standalone
Node scanner (scripts/scan-url.js) as a subprocess per request, so any
URL can be checked on demand rather than only the fixed pages in
tests/a11y-scan.spec.ts.

Run with: python src/app.py
Then open: http://localhost:5020
"""

import json
import re
import subprocess
from pathlib import Path

from flask import Flask, jsonify, render_template, request

ROOT = Path(__file__).parent.parent
SCREENSHOTS_DIR = ROOT / "screenshots"
HISTORY_PATH = ROOT / "history" / "a11y-history.jsonl"
SCANNER_SCRIPT = ROOT / "scripts" / "scan-url.js"

app = Flask(
    __name__,
    template_folder=str(ROOT / "templates"),
    static_folder=str(SCREENSHOTS_DIR),
    static_url_path="/screenshots",
)


def safe_filename(url: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "-", url)[:50]


def log_scan(output: dict, url: str) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {**output, "page_name": url}
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


@app.route("/")
def index():
    return render_template("scan_ui.html")


@app.route("/scan", methods=["POST"])
def scan():
    data = request.get_json() or {}
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "URL is required"}), 400
    if not url.startswith(("http://", "https://")):
        return jsonify({"error": "URL must start with http:// or https://"}), 400

    screenshot_path = SCREENSHOTS_DIR / f"{safe_filename(url)}-latest.png"

    try:
        result = subprocess.run(
            ["node", str(SCANNER_SCRIPT), url, str(screenshot_path)],
            capture_output=True,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Scan timed out after 90 seconds - the page may be slow to load"}), 504

    stdout_lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
    if not stdout_lines:
        return jsonify({"error": f"Scanner produced no output. stderr: {result.stderr}"}), 500

    try:
        output = json.loads(stdout_lines[-1])
    except json.JSONDecodeError:
        return jsonify({"error": f"Scanner output was not valid JSON: {stdout_lines[-1]}"}), 500

    if "error" in output:
        return jsonify(output), 500

    log_scan(output, url)

    if output.get("screenshot"):
        output["screenshot_url"] = f"/screenshots/{Path(output['screenshot']).name}"

    return jsonify(output)


if __name__ == "__main__":
    app.run(debug=True, port=5020)
