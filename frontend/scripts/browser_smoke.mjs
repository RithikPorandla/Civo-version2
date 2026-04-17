/**
 * Real-browser runtime smoke test.
 *
 * Launches headless Chromium via puppeteer, navigates each route on
 * the live dev server (http://127.0.0.1:5173), and captures any
 * uncaught page error or console.error. Exits non-zero if any route
 * fails.
 *
 * Run the backend (port 8000) and vite (port 5173) before calling.
 */
import puppeteer from 'puppeteer';

const ROUTES = [
  '/',
  '/lookup',
  '/municipalities',
  '/municipalities/2',
  '/suitability',
  '/report/111',
];

const BASE = 'http://127.0.0.1:5173';
const WAIT_MS = 3500;

// Mass.gov fonts / tile-server warnings are noise — suppress them so
// real errors aren't lost. Add more here if they're confirmed benign.
const IGNORE_PATTERNS = [
  /favicon\.ico/i,
  /maplibregl_prefer_attribution/i,
  // Map tile fetches are canceled when the page closes — not a real failure.
  /server\.arcgisonline\.com/i,
  /basemaps\.cartocdn\.com/i,
  /tiles?\.openstreetmap\.org/i,
];

// Console errors without a URL are typically browser-internal (favicon,
// net aborts). They come as "Failed to load resource:" with no other
// content. Filter them out because the response handler already catches
// the real 4xx/5xx URLs.
const CONSOLE_NOISE = /^Failed to load resource:/i;

async function checkOne(browser, route) {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(`PAGE THROW: ${e.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      const text = msg.text();
      if (IGNORE_PATTERNS.some((r) => r.test(text))) return;
      if (CONSOLE_NOISE.test(text)) return; // URL is in response handler
      errors.push(`CONSOLE: ${text}`);
    }
  });
  page.on('requestfailed', (req) => {
    const url = req.url();
    if (IGNORE_PATTERNS.some((r) => r.test(url))) return;
    errors.push(`REQ FAILED: ${req.failure()?.errorText} ${url}`);
  });
  page.on('response', (res) => {
    if (res.status() >= 400 && !IGNORE_PATTERNS.some((r) => r.test(res.url()))) {
      const method = res.request().method();
      errors.push(`HTTP ${res.status()} ${method}: ${res.url()}`);
    }
  });

  try {
    // domcontentloaded + fixed wait rather than networkidle0 — the map tiles
    // stream forever and would otherwise push us past the navigation timeout.
    await page.goto(BASE + route, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await new Promise((r) => setTimeout(r, WAIT_MS));
    // Check that the root element actually rendered something.
    const rootHtml = await page.evaluate(
      () => document.getElementById('root')?.innerHTML?.length ?? 0
    );
    if (rootHtml === 0) {
      errors.push(`ROOT empty after ${WAIT_MS}ms`);
    }
  } catch (e) {
    errors.push(`NAVIGATE THROW: ${e?.message || e}`);
  }
  await page.close();
  return errors;
}

(async () => {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  let hadError = false;
  for (const r of ROUTES) {
    const errs = await checkOne(browser, r);
    if (errs.length === 0) {
      console.log(`  OK   ${r}`);
    } else {
      hadError = true;
      console.log(`  FAIL ${r}`);
      for (const e of errs.slice(0, 6)) console.log(`       ${e.slice(0, 500)}`);
    }
  }
  await browser.close();
  process.exit(hadError ? 1 : 0);
})();
