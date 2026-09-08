"""
Analyzes accumulated accessibility scan history to show whether violations
are trending up or down over time, broken down by severity - a raw
violation count on its own doesn't say much; the trend does.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

SEVERITY_ORDER = ["critical", "serious", "moderate", "minor"]


def load_history(history_path: Path) -> list:
    if not history_path.exists():
        return []
    records = []
    with open(history_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def summarize_latest_scan(records: list, page_name: str) -> dict:
    """Returns the most recent scan's violation breakdown for one page."""
    page_records = [r for r in records if r["page_name"] == page_name]
    if not page_records:
        return {"page_name": page_name, "found": False}

    latest = max(page_records, key=lambda r: r["timestamp"])
    severity_counts = Counter(v["impact"] for v in latest["violations"])

    return {
        "page_name": page_name,
        "found": True,
        "timestamp": latest["timestamp"],
        "total_violations": latest["total_violations"],
        "by_severity": {sev: severity_counts.get(sev, 0) for sev in SEVERITY_ORDER},
        "violations": latest["violations"],
        "screenshot": latest.get("screenshot"),
    }


def trend_for_page(records: list, page_name: str) -> list:
    """Returns [{timestamp, total_violations}, ...] in chronological order
    for one page, for plotting a trend line."""
    page_records = [r for r in records if r["page_name"] == page_name]
    page_records.sort(key=lambda r: r["timestamp"])
    return [
        {"timestamp": r["timestamp"], "total_violations": r["total_violations"]}
        for r in page_records
    ]


def all_page_names(records: list) -> list:
    seen = []
    for r in records:
        if r["page_name"] not in seen:
            seen.append(r["page_name"])
    return seen


def full_report(history_path: Path) -> dict:
    records = load_history(history_path)
    pages = all_page_names(records)
    return {
        "pages": [
            {
                "latest": summarize_latest_scan(records, page),
                "trend": trend_for_page(records, page),
            }
            for page in pages
        ],
        "total_scans_recorded": len(records),
    }
