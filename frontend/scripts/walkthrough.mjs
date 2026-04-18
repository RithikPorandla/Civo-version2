/**
 * Scripted "consultant walkthrough" of the Civo platform.
 *
 * Captures a screenshot at every meaningful step — Overview →
 * Address Lookup (filled) → Report (scrolled through criteria,
 * expanded one, scrolled to mitigation/precedents) → Municipalities
 * index → Municipality detail with DOER strip → DOER deviation
 * drawer open. Each step saves to scripts/walkthrough/<NN>_<slug>.png.
 *
 * Both servers must be up:
 *   - backend on :8000 (uvicorn)
 *   - frontend on :5173 (vite)
 */
import puppeteer from 'puppeteer';
import { mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = join(__dirname, 'walkthrough');
const BASE = 'http://127.0.0.1:5173';

// Viewport tuned to a typical analyst laptop.
const VIEWPORT = { width: 1440, height: 900 };

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function shot(page, name) {
  const path = join(OUT, `${name}.png`);
  // fullPage: true captures the whole scrollable height so long reports
  // land in a single image.
  await page.screenshot({ path, fullPage: true });
  console.log(`  saved ${name}.png`);
}

async function goto(page, route, settle = 1800) {
  await page.goto(BASE + route, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await sleep(settle);
}

(async () => {
  await mkdir(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport(VIEWPORT);

  // Silence tile noise in logs.
  page.on('pageerror', (e) => console.error('PAGE ERR:', e.message));

  // -------- STEP 1: Overview ---------------------------------------
  console.log('\n01 overview');
  await goto(page, '/');
  await shot(page, '01_overview');

  // -------- STEP 2: Address Lookup form ----------------------------
  console.log('02 address lookup (blank)');
  await goto(page, '/lookup');
  await shot(page, '02_lookup_blank');

  // -------- STEP 3: Fill the form ----------------------------------
  console.log('03 address lookup (filled)');
  await page.evaluate(() => {
    // Find all inputs by type/placeholder and clear them.
    document.querySelectorAll('input').forEach((i) => {
      i.value = '';
      i.dispatchEvent(new Event('input', { bubbles: true }));
    });
  });
  const addressInput = await page.$('input[placeholder*="Nagog" i], input[type="text"], input:not([type])');
  if (addressInput) {
    await addressInput.click({ clickCount: 3 });
    await addressInput.type('50 Nagog Park, Acton, MA', { delay: 12 });
  }
  // Project type select
  await page.select('select', 'solar_ground_mount').catch(() => {});
  // Nameplate kW + acres
  const numberInputs = await page.$$('input[type="number"]');
  if (numberInputs[0]) {
    await numberInputs[0].click();
    await numberInputs[0].type('500', { delay: 12 });
  }
  if (numberInputs[1]) {
    await numberInputs[1].click();
    await numberInputs[1].type('3.2', { delay: 12 });
  }
  await sleep(400);
  await shot(page, '03_lookup_filled');

  // -------- STEP 4: Submit → Report --------------------------------
  console.log('04 report (landed)');
  // Click the Score button — match text content.
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button')].find((b) =>
      /score site/i.test(b.textContent || '')
    );
    btn?.click();
  });
  // Wait for URL change to /report/*.
  await page.waitForFunction(() => /\/report\//.test(location.pathname), {
    timeout: 30000,
  });
  await sleep(2500);
  await shot(page, '04_report_landed');

  // -------- STEP 5: Scroll to criteria + expand one ----------------
  console.log('05 report (criteria expanded)');
  await page.evaluate(() => {
    // Scroll to the first criterion row
    const rows = [...document.querySelectorAll('div')]
      .filter((d) => {
        const grid = getComputedStyle(d).gridTemplateColumns;
        return grid && grid.includes('28px');
      });
    const firstRow = rows[0];
    if (firstRow) {
      firstRow.scrollIntoView({ block: 'start' });
      firstRow.click();
    }
  });
  await sleep(900);
  await shot(page, '05_report_criterion_open');

  // -------- STEP 6: Mitigation + precedents ------------------------
  console.log('06 report (mitigation + precedents)');
  await page.evaluate(() => {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'instant' });
  });
  await sleep(700);
  await shot(page, '06_report_mitigation');

  // -------- STEP 7: Municipalities index ---------------------------
  console.log('07 municipalities index');
  await goto(page, '/municipalities');
  await shot(page, '07_municipalities_index');

  // -------- STEP 8: Municipality detail (DOER strip) ---------------
  console.log('08 municipality detail');
  await goto(page, '/municipalities/2'); // Acton
  await shot(page, '08_municipality_acton');

  // -------- STEP 9: Open DOER drawer -------------------------------
  console.log('09 DOER deviation drawer');
  await page.evaluate(() => {
    const solarCard = [...document.querySelectorAll('button')].find((b) =>
      /Solar · DOER model bylaw/i.test(b.textContent || '')
    );
    solarCard?.click();
  });
  await sleep(800);
  await shot(page, '09_doer_drawer');

  // -------- STEP 10: Site Suitability ------------------------------
  console.log('10 site suitability');
  await goto(page, '/suitability');
  await shot(page, '10_site_suitability');

  await browser.close();
  console.log(`\nDone. ${OUT}`);
})();
