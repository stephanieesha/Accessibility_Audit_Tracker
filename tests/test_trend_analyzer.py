import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "analyzer"))

from trend_analyzer import summarize_latest_scan, trend_for_page, all_page_names, load_history

SAMPLE_RECORDS = [
    {
        "timestamp": "2026-09-01T10:00:00Z",
        "page_name": "Login page",
        "url": "https://example.com/login",
        "screenshot": "screenshots/login-page-2026-09-01.png",
        "violations": [
            {"rule_id": "color-contrast", "impact": "serious", "description": "x", "help_url": "x", "tags": ["wcag2aa", "wcag143"], "affected_node_count": 2},
            {"rule_id": "label", "impact": "critical", "description": "x", "help_url": "x", "tags": ["wcag2a", "wcag412"], "affected_node_count": 1},
        ],
        "total_violations": 2,
    },
    {
        "timestamp": "2026-09-02T10:00:00Z",
        "page_name": "Login page",
        "url": "https://example.com/login",
        "screenshot": "screenshots/login-page-2026-09-02.png",
        "violations": [
            {"rule_id": "color-contrast", "impact": "serious", "description": "x", "help_url": "x", "tags": ["wcag2aa", "wcag143"], "affected_node_count": 2},
        ],
        "total_violations": 1,
    },
]


def test_summarize_latest_scan_picks_most_recent_by_timestamp():
    summary = summarize_latest_scan(SAMPLE_RECORDS, "Login page")
    assert summary["timestamp"] == "2026-09-02T10:00:00Z"
    assert summary["total_violations"] == 1


def test_summarize_latest_scan_breaks_down_by_severity():
    summary = summarize_latest_scan(SAMPLE_RECORDS, "Login page")
    assert summary["by_severity"]["serious"] == 1
    assert summary["by_severity"]["critical"] == 0  # not present in the LATEST scan


def test_summarize_returns_not_found_for_unknown_page():
    summary = summarize_latest_scan(SAMPLE_RECORDS, "Nonexistent page")
    assert summary["found"] is False


def test_summarize_includes_full_violation_detail_for_report_display():
    summary = summarize_latest_scan(SAMPLE_RECORDS, "Login page")
    assert len(summary["violations"]) == 1
    assert summary["violations"][0]["rule_id"] == "color-contrast"
    assert "wcag2aa" in summary["violations"][0]["tags"]


def test_summarize_includes_screenshot_path():
    summary = summarize_latest_scan(SAMPLE_RECORDS, "Login page")
    assert summary["screenshot"] == "screenshots/login-page-2026-09-02.png"


def test_trend_for_page_is_chronologically_ordered():
    trend = trend_for_page(SAMPLE_RECORDS, "Login page")
    assert trend[0]["timestamp"] < trend[1]["timestamp"]


def test_trend_shows_improvement_over_time():
    trend = trend_for_page(SAMPLE_RECORDS, "Login page")
    # violation count went from 2 -> 1: a real, detectable improvement
    assert trend[0]["total_violations"] > trend[-1]["total_violations"]


def test_all_page_names_deduplicates_and_preserves_order():
    records = SAMPLE_RECORDS + [{**SAMPLE_RECORDS[0], "page_name": "Dashboard"}]
    names = all_page_names(records)
    assert names == ["Login page", "Dashboard"]


def test_load_history_returns_empty_list_for_missing_file():
    assert load_history(Path("/tmp/does-not-exist-a11y.jsonl")) == []
