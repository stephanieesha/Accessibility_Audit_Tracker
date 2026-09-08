/**
 * Standalone accessibility scanner for a single arbitrary URL, invoked by
 * the Flask web UI via subprocess. Separate from tests/a11y-scan.spec.ts
 * (which is Playwright's own test runner, scanning a fixed config list) -
 * this is a plain script so it can be called with any URL on demand.
 *
 * Usage: node scripts/scan-url.js <url> <screenshot-output-path>
 * Prints a single line of JSON to stdout.
 */

const { chromium } = require('playwright');
const { AxeBuilder } = require('@axe-core/playwright');
const fs = require('fs');
const path = require('path');

async function waitForRealPage(page, maxWaitMs = 60000) {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    const bodyText = (await page.locator('body').innerText().catch(() => '')).toLowerCase();
    if (!bodyText.includes('application loading') && !bodyText.includes('incoming http request')) {
      return;
    }
    await page.waitForTimeout(2000);
    await page.reload({ waitUntil: 'networkidle' }).catch(() => {});
  }
}

async function main() {
  const url = process.argv[2];
  const screenshotPath = process.argv[3];

  if (!url) {
    console.log(JSON.stringify({ error: 'No URL provided' }));
    process.exit(1);
  }

  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    await page.goto(url, { timeout: 45000, waitUntil: 'load' });
    await waitForRealPage(page);

    const results = await new AxeBuilder({ page }).analyze();

    const allSelectors = results.violations.flatMap((v) =>
      v.nodes.map((n) => n.target[0]).filter((t) => typeof t === 'string')
    );
    await page.evaluate((selectors) => {
      selectors.forEach((sel) => {
        try {
          document.querySelectorAll(sel).forEach((el) => {
            el.style.outline = '3px solid red';
            el.style.outlineOffset = '2px';
          });
        } catch (e) {
          // some selectors (e.g. inside iframes) can't be matched this way - skip, not fatal
        }
      });
    }, allSelectors);

    if (screenshotPath) {
      fs.mkdirSync(path.dirname(screenshotPath), { recursive: true });
      await page.screenshot({ path: screenshotPath, fullPage: true });
    }

    const output = {
      url,
      timestamp: new Date().toISOString(),
      total_violations: results.violations.length,
      violations: results.violations.map((v) => ({
        rule_id: v.id,
        impact: v.impact,
        description: v.description,
        help_url: v.helpUrl,
        tags: v.tags,
        affected_node_count: v.nodes.length,
      })),
      screenshot: screenshotPath || null,
    };

    console.log(JSON.stringify(output));
  } catch (err) {
    console.log(JSON.stringify({ error: err.message }));
    process.exit(1);
  } finally {
    await browser.close();
  }
}

main();
