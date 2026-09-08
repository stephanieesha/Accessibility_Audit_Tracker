# Accessibility Audit Tracker

Runs automated accessibility scans against real pages on a schedule and
tracks violations over time - not just a one-time check, but a trend:
are things getting better or worse, and by how much.

## Why accessibility, and why tracked over time

Accessibility compliance is a genuinely underserved area in most QA
portfolios - most candidates have zero accessibility work to show, despite
it being a real compliance and usability requirement for production
software. A single audit is a snapshot; tracking violations over time is
what actually shows whether accessibility work is improving things or
just being ignored.

## How it works

```
tests/a11y-scan.spec.ts (Playwright + axe-core)
              |
    scans each configured page
              |
              v
history/a11y-history.jsonl (append-only, one record per scan)
              |
              v
   analyzer/trend_analyzer.py: latest severity breakdown + trend over time
              |
              v
   analyzer/generate_report.py: static HTML report with trend charts
```

axe-core is the industry-standard accessibility testing engine (the same
engine behind Lighthouse's accessibility audits) - not a custom or
invented ruleset.

## What's scanned

Currently just the login page (`tests/a11y-scan.spec.ts`), since it
doesn't require authentication. Extending to authenticated pages (the
dashboard, categories) requires handling Shirly's login flow first - the
`ShoppingListPage.ts` Page Object from the Flaky Test Detector project has
that pattern already worked out and can be reused directly.

**Cold-start handling:** Render's free tier serves its own placeholder
"waking up" page while an app spins up, and a plain `page.goto()` has no
way to know that isn't the real content - it's a fully-formed page as far
as Playwright is concerned. Both the scheduled scanner and the on-demand
scanner poll for that placeholder's text and reload until it's gone
(up to 60s), before scanning or screenshotting anything. Without this, a
scan can silently run against Render's own loading screen instead of the
actual app.

## Setup

```bash
npm install
npx playwright install --with-deps chromium
pip install -r requirements.txt
```

## Running a scan

```bash
npx playwright test
```
This appends a new record to `history/a11y-history.jsonl` for each
configured page, and saves a screenshot to `screenshots/`.

## Generating the report

```bash
python analyzer/generate_report.py
```
Writes `report.html` - open it directly in a browser, no server needed.

## Watching it run

```bash
npx playwright test --headed
```
Opens a real, visible browser and narrates each step in the terminal
(navigate → scan → highlight violations → screenshot → record). Drop
`--headed` for a normal fast run without the visible browser window.

## What the report shows

Beyond the trend chart, `report.html` includes:
- A legend explaining what axe-core actually checks (WCAG conformance
  levels A/AA/AAA) and what each severity level means, so the report is
  readable without already knowing accessibility terminology
- Full detail on every violation from the most recent scan: description,
  which WCAG criteria it maps to, and a link to axe-core's own
  documentation for how to fix it
- A screenshot of the page with every violating element outlined in red -
  a visual record of exactly what was flagged and where, not just a list
  of CSS selectors

## Screenshots

Saved to `screenshots/`, one per scan, named by page and timestamp. These
accumulate over time along with the history file - worth periodically
clearing old ones if storage becomes a concern, since every scan keeps
its own image.

## Running the tests

```bash
pytest tests/test_trend_analyzer.py
```
Covers picking the correct "latest" scan by timestamp, severity breakdown,
chronological trend ordering, and the empty-history edge case - all using
fixture data, so these don't depend on live network access or axe-core
actually running.

## On-demand scanning via web UI

Rather than editing `PAGES_TO_SCAN` for every new page, paste any URL
directly:

```bash
pip install -r requirements.txt
python src/app.py
```
Then open `http://localhost:5020`. Enter a URL, click Scan, and results
(violations, severity, screenshot with issues outlined in red) appear in
the browser. Every on-demand scan also logs to the same
`history/a11y-history.jsonl` used by the scheduled scans, so it
contributes to the trend data too - it's a different way of triggering
a scan, not a separate system.

This runs `scripts/scan-url.js` (a standalone Node script, separate from
the Playwright test file) as a subprocess per request - the same
axe-core scan and cold-start-aware waiting logic, just callable with any
URL instead of a fixed config list.

## Adding another page to scan

Add an entry to the `PAGES_TO_SCAN` array in `tests/a11y-scan.spec.ts`:
```typescript
{ name: 'Categories page', url: 'https://shirly2-0.onrender.com/lists' }
```

## Roadmap

- Scan authenticated pages (dashboard, categories, item views) once the
  login flow is wired in
- Scheduled CI run with the same commit-back pattern as the Flaky Test
  Detector (`.github/workflows/scan.yml` is already set up for this)
- Fail CI on new critical/serious violations once a clean baseline is
  established, rather than only tracking trend passively
