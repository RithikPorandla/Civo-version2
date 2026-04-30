import { useState } from 'react';
import { Link } from 'react-router-dom';

interface Report {
  id: number;
  address: string;
  town: string;
  score: number;
  bucket: 'SUITABLE' | 'CONDITIONALLY SUITABLE' | 'CONSTRAINED';
  date: string;
  factors: { label: string; flag: 'ok' | 'warn' | 'block' }[];
  acreage: number;
  projectType: string;
}

const REPORTS: Report[] = [
  {
    id: 1,
    address: 'Kendall Square, Cambridge, MA',
    town: 'Cambridge',
    score: 92.5,
    bucket: 'SUITABLE',
    date: 'Apr 28',
    acreage: 14.2,
    projectType: 'BESS Standalone',
    factors: [
      { label: 'Grid within 0.4 mi',     flag: 'ok'   },
      { label: 'No wetland buffer',       flag: 'ok'   },
      { label: 'By-right zoning',         flag: 'ok'   },
    ],
  },
  {
    id: 2,
    address: '50 Nagog Park, Acton, MA',
    town: 'Acton',
    score: 64.1,
    bucket: 'CONDITIONALLY SUITABLE',
    date: 'Apr 26',
    acreage: 8.7,
    projectType: 'BESS Standalone',
    factors: [
      { label: 'ConCom jurisdiction',     flag: 'warn' },
      { label: '150 ft wetland setback',  flag: 'warn' },
      { label: 'Site plan review req.',   flag: 'warn' },
    ],
  },
  {
    id: 3,
    address: 'East Freetown, MA',
    town: 'Freetown',
    score: 35.4,
    bucket: 'CONSTRAINED',
    date: 'Apr 24',
    acreage: 22.1,
    projectType: 'Solar Ground-Mount',
    factors: [
      { label: 'Moratorium active',       flag: 'block' },
      { label: 'ACEC overlay',            flag: 'block' },
      { label: 'Grid capacity limited',   flag: 'block' },
    ],
  },
];

const FLAG_COLOR = { ok: '#6b7e5a', warn: '#b07e30', block: '#a85a4a' };
const FLAG_BG    = { ok: 'rgba(107,126,90,0.10)', warn: 'rgba(176,126,48,0.10)', block: 'rgba(168,90,74,0.10)' };

const CHIP_CLASS: Record<Report['bucket'], string> = {
  'SUITABLE':               'chip suit',
  'CONDITIONALLY SUITABLE': 'chip cond',
  'CONSTRAINED':            'chip cons',
};
const CHIP_LABEL: Record<Report['bucket'], string> = {
  'SUITABLE':               'Suitable',
  'CONDITIONALLY SUITABLE': 'Conditional',
  'CONSTRAINED':            'Constrained',
};

function scoreClass(s: number) {
  if (s >= 75) return 's-high';
  if (s >= 50) return 's-mid';
  return 's-low';
}

// Mini horizontal score bar — shows 0–100 position
function ScoreBar({ score }: { score: number }) {
  const color = score >= 75 ? '#6b7e5a' : score >= 50 ? '#c9a464' : '#a85a4a';
  return (
    <div style={{ width: '100%', height: 3, background: 'var(--border-soft)', borderRadius: 999, marginTop: 5 }}>
      <div style={{ width: `${score}%`, height: 3, background: color, borderRadius: 999, opacity: 0.75 }} />
    </div>
  );
}

export default function SiteSuitability() {
  const [query, setQuery] = useState('');

  const suitable    = REPORTS.filter((r) => r.bucket === 'SUITABLE').length;
  const conditional = REPORTS.filter((r) => r.bucket === 'CONDITIONALLY SUITABLE').length;
  const constrained = REPORTS.filter((r) => r.bucket === 'CONSTRAINED').length;
  const avgScore    = Math.round(REPORTS.reduce((s, r) => s + r.score, 0) / REPORTS.length);

  const filtered = REPORTS.filter((r) =>
    r.address.toLowerCase().includes(query.toLowerCase()) ||
    r.town.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="page" style={{ fontFamily: 'var(--sans)' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24, marginBottom: 20 }}>
        <div>
          <div className="page-eyebrow">Suitability</div>
          <h1 className="page-h1">Reports</h1>
          <p className="page-sub">
            {REPORTS.length} sites scored · avg {avgScore}/100 · {suitable} suitable · {conditional} conditional · {constrained} constrained
          </p>
        </div>
        <Link to="/app/lookup" className="btn btn-primary" style={{ marginTop: 24, flexShrink: 0 }}>
          New report →
        </Link>
      </div>

      {/* Top constraint summary strip */}
      <div
        className="card"
        style={{ padding: '12px 18px', marginBottom: 16, display: 'flex', gap: 24, alignItems: 'center', flexWrap: 'wrap' }}
      >
        <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-soft)', flexShrink: 0 }}>
          Top constraints
        </div>
        {[
          { label: 'ConCom jurisdiction',   count: 2 },
          { label: 'Wetland setback',       count: 2 },
          { label: 'Moratorium',            count: 1 },
          { label: 'ACEC overlay',          count: 1 },
          { label: 'Grid capacity',         count: 1 },
        ].map((c) => (
          <div key={c.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 12.5, color: 'var(--text-mid)', fontWeight: 500 }}>{c.label}</span>
            <span
              style={{
                fontSize: 10.5,
                fontWeight: 600,
                background: 'var(--surface-alt)',
                border: '1px solid var(--border)',
                borderRadius: 4,
                padding: '1px 6px',
                color: 'var(--text-soft)',
              }}
            >
              {c.count}
            </span>
          </div>
        ))}
      </div>

      {/* Filter + count */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginBottom: 10 }}>
        <input
          type="text"
          placeholder="Filter by address or town…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{
            width: 260, height: 32,
            paddingLeft: 12, paddingRight: 12,
            borderRadius: 7, border: '1px solid var(--border)',
            background: 'var(--surface)', fontSize: 13,
            color: 'var(--text)', fontFamily: 'var(--sans)',
            outline: 'none', boxSizing: 'border-box',
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
          onBlur={(e)  => (e.currentTarget.style.borderColor = 'var(--border)')}
        />
        <div style={{ fontSize: 12, color: 'var(--text-soft)' }}>{filtered.length} of {REPORTS.length}</div>
      </div>

      {/* Report rows */}
      <div className="card" style={{ overflow: 'hidden' }}>
        {filtered.length === 0 && (
          <div style={{ padding: '20px 16px', fontSize: 13, color: 'var(--text-soft)' }}>
            No reports match "{query}"
          </div>
        )}
        {filtered.map((r, idx) => (
          <Link
            key={r.id}
            to={`/report/${r.id}`}
            style={{
              display: 'grid',
              gridTemplateColumns: '64px 1fr auto 80px 28px',
              gap: 16,
              alignItems: 'start',
              padding: '12px 16px',
              textDecoration: 'none',
              color: 'var(--text)',
              borderBottom: idx < filtered.length - 1 ? '1px solid var(--border-soft)' : 'none',
              transition: 'background 100ms ease',
            }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLAnchorElement).style.background = 'var(--surface)')}
            onMouseLeave={(e) => ((e.currentTarget as HTMLAnchorElement).style.background = 'transparent')}
          >
            {/* Score + bar */}
            <div>
              <div className={`score ${scoreClass(r.score)}`} style={{ fontSize: 14, width: 44, height: 44 }}>
                {r.score}
              </div>
              <ScoreBar score={r.score} />
            </div>

            {/* Address + constraint factors */}
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--text)', lineHeight: 1.3 }}>
                {r.address}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--text-soft)', marginTop: 2, marginBottom: 7 }}>
                {r.projectType} · {r.acreage} ac
              </div>
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                {r.factors.map((f) => (
                  <span
                    key={f.label}
                    style={{
                      fontSize: 11,
                      fontWeight: 500,
                      padding: '2px 7px',
                      borderRadius: 4,
                      background: FLAG_BG[f.flag],
                      color: FLAG_COLOR[f.flag],
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {f.label}
                  </span>
                ))}
              </div>
            </div>

            {/* Status chip + date */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, paddingTop: 2 }}>
              <span className={CHIP_CLASS[r.bucket]}>{CHIP_LABEL[r.bucket]}</span>
              <span style={{ fontSize: 11.5, color: 'var(--text-soft)' }}>{r.date}</span>
            </div>

            {/* Arrow */}
            <div style={{ display: 'none' }} /> {/* placeholder for grid alignment */}
            <div style={{ fontSize: 13, color: 'var(--text-soft)', paddingTop: 2 }}>→</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
