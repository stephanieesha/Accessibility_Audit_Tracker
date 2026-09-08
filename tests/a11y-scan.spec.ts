import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'fs';
import path from 'path';

/**
 * Scans a configured list of pages with axe-core and appends results to a
 * history file, so violations can be tracked as a trend over time.
 *
 * Two things beyond a basic scan:
 * 1. Console narration at each step - run with `npx playwright test --headed`
 *    to watch a real browser do this live, with the terminal output
 *    explaining what's happening at each stage.
 * 2. A full-page screenshot with every violating element outlined in red,
 *    saved per scan - a visual record of exactly what was flagged and
 *    where, since a text description alone doesn't show that clearly.
 */

const PAGES_TO_SCAN = [
  { name: 'Login page', url: 'https://shirly2-0.onrender.com/login' },
];

const HISTORY_PATH = path.join(__dirname, '..', 'history', 'a11y-history.jsonl');
const SCREENSHOTS_DIR = path.join(__dirname, '..', 'screenshots');

for (const pageConfig of PAGES_TO_SCAN) {
  test(`accessibility scan: ${pageConfig.name}`, async ({ page: browserPage }) => {
    console.log(`\n[${pageConfig.name}] Step 1: Navigating to ${pageConfig.url}...`);
    await browserPage.goto(pageConfig.url, { timeout: 45000 });

    console.log(`[${pageConfig.name}] Step 2: Running axe-core accessibility scan...`);
    const results = await new AxeBuilder({ page: browserPage }).analyze();

    console.log(`[${pageConfig.name}] Step 3: Found ${results.violations.length} violation type(s), affecting ${results.violations.reduce((sum, v) => sum + v.nodes.length, 0)} element(s) total.`);

    // Highlight every violating element directly on the page with a red
    // outline before screenshotting, so the image shows exactly what was
    // flagged - not just a list of CSS selectors.
    console.log(`[${pageConfig.name}] Step 4: Highlighting violating elements for screenshot...`);
    const allSelectors = results.violations.flatMap((v) =>
      v.nodes.map((n) => n.target[0]).filter((t): t is string => typeof t === 'string')
    );

    await browserPage.evaluate((selectors) => {
      selectors.forEach((sel) => {
        try {
          document.querySelectorAll(sel).forEach((el) => {
            (el as HTMLElement).style.outline = '3px solid red';
            (el as HTMLElement).style.outlineOffset = '2px';
          });
        } catch {
          // Some selectors (e.g. inside iframes) can't be matched this way - skip, not fatal.
        }
      });
    }, allSelectors);

    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
    // Stable filename per page (not timestamped) - overwritten each run.
    // This keeps only the current screenshot committed to the repo rather
    // than accumulating one image per historical scan forever; the trend
    // data itself already lives in history/a11y-history.jsonl.
    const screenshotFilename = `${pageConfig.name.replace(/\s+/g, '-').toLowerCase()}-latest.png`;
    const screenshotPath = path.join(SCREENSHOTS_DIR, screenshotFilename);
    await browserPage.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`[${pageConfig.name}] Step 5: Screenshot saved to screenshots/${screenshotFilename}`);

    const record = {
      timestamp: new Date().toISOString(),
      page_name: pageConfig.name,
      url: pageConfig.url,
      screenshot: `screenshots/${screenshotFilename}`,
      violations: results.violations.map((v) => ({
        rule_id: v.id,
        impact: v.impact,
        description: v.description,
        help_url: v.helpUrl,
        tags: v.tags, // e.g. ['wcag2a', 'wcag143'] - which WCAG criteria this maps to
        affected_node_count: v.nodes.length,
      })),
      total_violations: results.violations.length,
    };

    fs.mkdirSync(path.dirname(HISTORY_PATH), { recursive: true });
    fs.appendFileSync(HISTORY_PATH, JSON.stringify(record) + '\n');

    console.log(`[${pageConfig.name}] Step 6: Recorded to history.\n`);

    expect(results).toBeTruthy();
  });
}
