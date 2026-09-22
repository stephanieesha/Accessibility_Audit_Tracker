"""
Web UI: paste a URL, get an accessibility scan back. Runs the standalone
Node scanner (scripts/scan-url.js) as a subprocess per request, so any
URL can be checked on demand rather than only the fixed pages in
tests/a11y-scan.spec.ts.

Run with: python src/app.py
Then open: http://localhost:5020
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request

sys.path.insert(0, str(Path(__file__).parent))
from limits import client_ip, daily_scan_allowed, is_safe_url, too_many_requests  # noqa: E402

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


@app.before_request
def limit_scans_per_visitor():
    if request.method == "POST" and too_many_requests(client_ip(request)):
        return jsonify({"error": "Too many scans - please wait a minute and try again"}), 429


@app.after_request
def keep_out_of_search_engines(response):
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.route("/robots.txt")
def robots():
    return "User-agent: *\nDisallow: /\n", 200, {"Content-Type": "text/plain"}


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

    safe, reason = is_safe_url(url)
    if not safe:
        return jsonify({"error": reason}), 400

    if not daily_scan_allowed():
        return jsonify({"error": "The daily limit for on-demand scans has been reached - please try again tomorrow"}), 429

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

    # On a public deployment the container's filesystem is not persistent, so writing to the
    # log here would silently vanish on the next restart. The trend chart on the published
    # report stays sourced from the scheduled GitHub Actions scan either way; DISABLE_HISTORY_LOG
    # just stops this app pretending an on-demand scan was recorded when it was not.
    if os.environ.get("DISABLE_HISTORY_LOG", "").lower() != "true":
        log_scan(output, url)

    if output.get("screenshot"):
        output["screenshot_url"] = f"/screenshots/{Path(output['screenshot']).name}"

    return jsonify(output)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", port=int(os.environ.get("PORT", "5020")))
