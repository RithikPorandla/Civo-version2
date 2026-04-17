/**
 * Runtime smoke test for the built Civo frontend.
 *
 * Spins up a happy-dom window, navigates to each route, evaluates the
 * built JS bundle, and reports any uncaught exception — the thing
 * `tsc` and `vite build` miss.
 *
 * Usage: node scripts/smoke.mjs
 */
import { Window } from 'happy-dom';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIST = join(__dirname, '..', 'dist');

const ROUTES = [
  '/',
  '/lookup',
  '/municipalities',
  '/suitability',
  '/report/111',
  '/municipalities/2',
];

// Stub the backend: every /api call resolves with a plausible shape.
function installFetchStub(win) {
  win.fetch = async (url, init) => {
    const u = String(url);
    const payloads = {
      '/health': {
        database: true,
        postgis: '3.4.3',
        pgvector: '0.8.2',
        parcels_loaded: 200000,
        esmp_projects_loaded: 29,
        municipalities_loaded: 5,
        status: 'ok',
      },
      '/municipalities': [
        { town_id: 2, town_name: 'Acton', project_types: ['solar_ground_mount'], last_refreshed_at: null },
      ],
      '/municipality/2': {
        town_id: 2,
        town_name: 'Acton',
        county: 'Middlesex',
        project_type_bylaws: {},
        last_refreshed_at: null,
      },
      '/towns/2/doer-status': {
        town_id: 2,
        town_name: 'Acton',
        solar: null,
        bess: null,
        deadline: '2026-11-30',
        days_remaining: 228,
        other_project_types_note: '',
      },
      '/report/111': {
        parcel_id: 'F_812940_2692755',
        address: '50 Nagog Park, Acton, MA',
        project_type: 'solar_ground_mount',
        config_version: 'ma-eea-2026-v1',
        methodology: '225 CMR 29.00',
        computed_at: '2026-04-17T01:00:00Z',
        total_score: 52,
        bucket: 'CONDITIONALLY SUITABLE',
        primary_constraint: 'biodiversity',
        ineligible_flags: [],
        criteria: [
          {
            key: 'biodiversity',
            name: 'Biodiversity',
            weight: 0.2,
            raw_score: 4.2,
            weighted_contribution: 8.4,
            status: 'flagged',
            finding: 'Test finding.',
            citations: [
              { dataset: 'BioMap Core', url: 'https://gis.data.mass.gov/maps/xxx', detail: 'test' },
            ],
          },
        ],
        citations: [],
      },
      '/exemption-check': {
        is_exempt: null,
        reason: 'insufficient_data',
        regulation_reference: '225 CMR 29.07(1)',
        missing_fields: ['nameplate_capacity_kw', 'site_footprint_acres'],
      },
    };
    for (const k of Object.keys(payloads)) {
      if (u.endsWith(k) || u.includes(k)) {
        return new win.Response(JSON.stringify(payloads[k]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
    }
    return new win.Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
}

async function checkRoute(route) {
  const errors = [];
  const win = new Window({ url: `http://127.0.0.1:5173${route}` });
  win.console.error = (...args) => errors.push(args.map((a) => String(a)).join(' '));

  const html = readFileSync(join(DIST, 'index.html'), 'utf8');
  const bundleMatch = html.match(/\/assets\/index-[\w-]+\.js/);
  if (!bundleMatch) {
    return { route, errors: ['no bundle found in dist/index.html'] };
  }
  const bundleJs = readFileSync(join(DIST, bundleMatch[0]), 'utf8');

  installFetchStub(win);
  // Stub maplibre-gl's WebGL dependency since happy-dom has no canvas.
  win.HTMLCanvasElement.prototype.getContext = () => null;

  try {
    win.document.documentElement.innerHTML = html
      .replace(/<script[^>]*src="[^"]+"[^>]*><\/script>/g, '')
      .replace(/<!doctype[^>]*>/i, '');
    win.eval(bundleJs);
    // Let React commit, effects run.
    await new Promise((r) => setTimeout(r, 150));
    await win.happyDOM.waitUntilComplete();
  } catch (e) {
    errors.push(`THROW: ${e && e.stack ? e.stack.split('\n').slice(0, 5).join(' | ') : String(e)}`);
  }

  await win.happyDOM.close();
  return { route, errors };
}

(async () => {
  let hadErrors = false;
  for (const r of ROUTES) {
    const { errors } = await checkRoute(r);
    if (errors.length === 0) {
      console.log(`  OK   ${r}`);
    } else {
      hadErrors = true;
      console.log(`  FAIL ${r}`);
      for (const e of errors.slice(0, 5)) console.log(`       ${e.slice(0, 400)}`);
    }
  }
  process.exit(hadErrors ? 1 : 0);
})();
