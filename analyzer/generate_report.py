"""
Generates a static HTML report from the accumulated scan history, including
a legend explaining what's actually being checked (so the report is
readable without already knowing what axe-core or WCAG mean), full detail
on every violation found, and the highlighted screenshot from the most
recent scan of each page.
"""

import html
import json
from pathlib import Path, PureWindowsPath

from trend_analyzer import full_report

ROOT = Path(__file__).parent.parent
HISTORY_PATH = ROOT / "history" / "a11y-history.jsonl"
OUTPUT_PATH = ROOT / "report.html"

LEGEND_HTML = """
<div class="card">
  <h2>Understanding this report</h2>
  <p>This uses <strong>axe-core</strong>, the accessibility testing engine
  that also powers Chrome Lighthouse's accessibility audits - not a custom
  or invented ruleset. It checks pages against the
  <strong>WCAG (Web Content Accessibility Guidelines)</strong>, the
  official standard for web accessibility.</p>

  <p>WCAG has three conformance levels, referenced in each violation's tags
  below:</p>
  <ul>
    <li><strong>A</strong> - the baseline. Failing this means some users genuinely cannot use the feature at all.</li>
    <li><strong>AA</strong> - the standard most organizations target (often a legal requirement). Most violations found here fall in this range.</li>
    <li><strong>AAA</strong> - the strictest level, not usually required for general use.</li>
  </ul>

  <p>Severity levels (axe-core's own definitions):</p>
  <div class="severity-row">
    <span class="severity-badge critical">critical</span> blocks users with disabilities from completing a core task entirely
  </div>
  <div class="severity-row">
    <span class="severity-badge serious">serious</span> creates a major barrier, though sometimes a workaround exists
  </div>
  <div class="severity-row">
    <span class="severity-badge moderate">moderate</span> a real problem, but not usually blocking
  </div>
  <div class="severity-row">
    <span class="severity-badge minor">minor</span> a small usability issue
  </div>

  <p>Each violation below links to axe-core's own documentation for that
  specific rule, with the exact WCAG success criteria and guidance on
  how to fix it.</p>
</div>
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Accessibility Audit Report</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
  <style>
    body {{ font-family: -apple-system, system-ui, sans-serif; margin: 0; background: #f7f5f2; color: #2a2420; line-height: 1.5; }}
    header {{ padding: 20px 32px; background: #2a2420; color: #fff; }}
    .container {{ max-width: 800px; margin: 24px auto; padding: 0 24px; }}
    .card {{ background: #fff; border-radius: 10px; padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    .card h2 {{ margin-top: 0; font-size: 16px; color: #6b5d4f; }}
    .card ul {{ font-size: 13px; padding-left: 20px; }}
    .card p {{ font-size: 13px; }}
    .severity-row {{ display: flex; align-items: center; gap: 10px; margin: 8px 0; font-size: 13px; }}
    .severity-badge {{ padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 12px; white-space: nowrap; }}
    .critical {{ background: #fde8e8; color: #8a0000; }}
    .serious {{ background: #fdf0e0; color: #8a5a00; }}
    .moderate {{ background: #fdf8e0; color: #8a7a00; }}
    .minor {{ background: #eef0e8; color: #4a5a2a; }}
    .no-data {{ color: #999; text-align: center; padding: 40px 0; }}
    .violation-item {{ border: 1px solid #eee; border-radius: 8px; padding: 14px 16px; margin-bottom: 10px; }}
    .violation-item h3 {{ margin: 0 0 6px; font-size: 14px; }}
    .violation-item .tags {{ font-size: 11px; color: #999; margin-top: 6px; }}
    .violation-item a {{ font-size: 12px; color: #b5651d; }}
    .screenshot-container {{ margin-top: 16px; border: 1px solid #eee; border-radius: 8px; overflow: hidden; }}
    .screenshot-container img {{ width: 100%; display: block; }}
    .screenshot-caption {{ font-size: 12px; color: #999; padding: 8px 12px; background: #fafafa; }}
  </style>
</head>
<body>
  <header><h1>Accessibility Audit Report</h1></header>
  <div class="container">
    {legend}
    {content}
  </div>
</body>
</html>
"""


def screenshot_src(recorded_path: str) -> str:
    """History records the absolute path from whichever machine ran the scan
    (for example /Users/name/... or C:\\...). Reports need a path relative to
    the report itself, so keep only the file name."""
    return "screenshots/" + PureWindowsPath(recorded_path).name


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def render_violation_detail(violation: dict) -> str:
    tags = esc(", ".join(violation.get("tags", [])))
    return f"""
    <div class="violation-item">
      <span class="severity-badge {esc(violation['impact'])}">{esc(violation['impact'])}</span>
      <h3>{esc(violation['rule_id'])}</h3>
      <p>{esc(violation['description'])}</p>
      <p>Affects {violation['affected_node_count']} element(s) on the page.</p>
      <div class="tags">WCAG tags: {tags}</div>
      <a href="{esc(violation['help_url'])}" target="_blank" rel="noopener">View axe-core documentation for this rule &rarr;</a>
    </div>
    """


def render_page_card(page_data: dict, index: int) -> str:
    latest = page_data["latest"]
    trend = page_data["trend"]

    if not latest["found"]:
        return f'<div class="card"><h2>{esc(latest["page_name"])}</h2><p class="no-data">No scans recorded yet.</p></div>'

    severity_html = "".join(
        f'<span class="severity-badge {esc(sev)}">{esc(sev)}: {count}</span>'
        for sev, count in latest["by_severity"].items()
    )

    canvas_id = f"trend-chart-{index}"
    labels = json.dumps([t["timestamp"][:10] for t in trend])
    data = json.dumps([t["total_violations"] for t in trend])

    violations_html = "".join(render_violation_detail(v) for v in latest["violations"])
    if not violations_html:
        violations_html = "<p>No violations found in the most recent scan.</p>"

    screenshot_html = ""
    if latest.get("screenshot"):
        screenshot_html = f"""
        <div class="screenshot-container">
          <img src="{esc(screenshot_src(latest['screenshot']))}" alt="Screenshot of {esc(latest['page_name'])} with violating elements outlined in red" />
          <div class="screenshot-caption">Elements with violations are outlined in red.</div>
        </div>
        """

    return f"""
    <div class="card">
      <h2>{esc(latest['page_name'])}</h2>
      <p>Latest scan: {esc(latest['timestamp'])} — {latest['total_violations']} total violations</p>
      <div class="severity-row" style="gap: 8px;">{severity_html}</div>
      <canvas id="{canvas_id}" height="120"></canvas>
      <script>
        new Chart(document.getElementById('{canvas_id}'), {{
          type: 'line',
          data: {{
            labels: {labels},
            datasets: [{{ label: 'Total violations', data: {data}, borderColor: '#b5651d', tension: 0.2 }}]
          }},
          options: {{ scales: {{ y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }} }} }}
        }});
      </script>
      {screenshot_html}
      <h2 style="margin-top: 24px;">Violation detail</h2>
      {violations_html}
    </div>
    """


def main():
    report = full_report(HISTORY_PATH)

    if report["total_scans_recorded"] == 0:
        content = '<div class="card"><p class="no-data">No scans recorded yet. Run `npx playwright test` to generate the first one.</p></div>'
    else:
        content = "".join(render_page_card(page, i) for i, page in enumerate(report["pages"]))

    OUTPUT_PATH.write_text(TEMPLATE.format(legend=LEGEND_HTML, content=content), encoding="utf-8")
    print(f"Report written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
