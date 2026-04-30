import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api, doerApi, ProjectTypeCode } from '../lib/api';
import DoerAlignmentStrip from '../components/DoerAlignmentStrip';

const PROJECT_TYPES: Array<{ code: ProjectTypeCode; label: string }> = [
  { code: 'solar_rooftop', label: 'Solar Rooftop' },
  { code: 'solar_ground_mount', label: 'Solar Ground-Mount' },
  { code: 'solar_canopy', label: 'Solar Canopy' },
  { code: 'bess_standalone', label: 'BESS Standalone' },
  { code: 'bess_colocated', label: 'BESS Co-located' },
  { code: 'substation', label: 'Substation' },
  { code: 'transmission', label: 'Transmission' },
  { code: 'ev_charging', label: 'EV Charging' },
];

// Short labels for the project type pills shown in each row
const TYPE_SHORT: Partial<Record<ProjectTypeCode, string>> = {
  solar_rooftop:     'Rooftop',
  solar_ground_mount:'Ground',
  solar_canopy:      'Canopy',
  bess_standalone:   'BESS',
  bess_colocated:    'BESS+',
  substation:        'Sub.',
  transmission:      'Trans.',
  ev_charging:       'EV',
};

export default function MunicipalitiesRoute() {
  const { townId } = useParams();
  if (townId) return <MunicipalityDetail townId={Number(townId)} />;
  return <MunicipalityIndex />;
}

function MunicipalityIndex() {
  const [query, setQuery] = useState('');

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['municipalities'],
    queryFn: () => api.listMunicipalities(),
  });

  if (isPending)
    return <div style={{ padding: 36, color: 'var(--text-soft)', fontSize: 13 }}>Loading…</div>;

  if (isError)
    return (
      <div style={{ padding: 36, maxWidth: 560 }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--rust)', marginBottom: 6 }}>
          Could not load municipalities
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-soft)', lineHeight: 1.6 }}>{String(error)}</div>
      </div>
    );

  const towns = data || [];
  const moratoriumCount = towns.filter((m) => m.moratorium_active).length;
  const filtered = towns.filter((m) =>
    m.town_name.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="page" style={{ fontFamily: 'var(--sans)' }}>

      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div className="page-eyebrow">Coverage</div>
        <h1 className="page-h1">Municipalities</h1>
        <p className="page-sub">
          {towns.length} towns indexed · {moratoriumCount} active moratoriums
        </p>
      </div>

      {/* Search + count row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 16,
          marginBottom: 12,
        }}
      >
        <div style={{ position: 'relative', width: 260 }}>
          <input
            type="text"
            placeholder="Filter towns…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{
              width: '100%',
              height: 32,
              paddingLeft: 12,
              paddingRight: 12,
              borderRadius: 7,
              border: '1px solid var(--border)',
              background: 'var(--surface)',
              fontSize: 13,
              color: 'var(--text)',
              fontFamily: 'var(--sans)',
              outline: 'none',
              boxSizing: 'border-box',
            }}
            onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
            onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
          />
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-soft)' }}>
          {filtered.length} of {towns.length}
        </div>
      </div>

      {/* Column headers */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 220px 110px 90px 28px',
          gap: 12,
          padding: '0 16px 8px',
          borderBottom: '1px solid var(--border-soft)',
        }}
      >
        {['Town', 'Project types', 'Status', 'Refreshed', ''].map((h) => (
          <div
            key={h}
            style={{
              fontSize: 11,
              fontWeight: 500,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              color: 'var(--text-soft)',
            }}
          >
            {h}
          </div>
        ))}
      </div>

      {/* Rows */}
      <div className="card" style={{ overflow: 'hidden', marginTop: 4 }}>
        {filtered.length === 0 && (
          <div style={{ padding: '20px 16px', fontSize: 13, color: 'var(--text-soft)' }}>
            No towns match "{query}"
          </div>
        )}
        {filtered.map((m, idx) => (
          <Link
            key={m.town_id}
            to={`/municipalities/${m.town_id}`}
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 220px 110px 90px 28px',
              gap: 12,
              alignItems: 'center',
              padding: '11px 16px',
              textDecoration: 'none',
              color: 'var(--text)',
              borderBottom: idx < filtered.length - 1 ? '1px solid var(--border-soft)' : 'none',
              transition: 'background 100ms ease',
            }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLAnchorElement).style.background = 'var(--surface)')}
            onMouseLeave={(e) => ((e.currentTarget as HTMLAnchorElement).style.background = 'transparent')}
          >
            {/* Town name */}
            <div
              style={{
                fontFamily: "'Fraunces', Georgia, serif",
                fontSize: 15,
                fontWeight: 500,
                letterSpacing: '-0.01em',
                color: 'var(--text)',
                lineHeight: 1.2,
              }}
            >
              {m.town_name}
            </div>

            {/* Project type pills — show first 3, then +N */}
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {m.project_types.slice(0, 3).map((pt) => (
                <span
                  key={pt}
                  style={{
                    fontSize: 10.5,
                    fontWeight: 500,
                    padding: '2px 7px',
                    borderRadius: 4,
                    background: 'var(--surface-alt)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-mid)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {TYPE_SHORT[pt as ProjectTypeCode] ?? pt}
                </span>
              ))}
              {m.project_types.length > 3 && (
                <span
                  style={{
                    fontSize: 10.5,
                    fontWeight: 500,
                    padding: '2px 7px',
                    borderRadius: 4,
                    background: 'transparent',
                    color: 'var(--text-soft)',
                  }}
                >
                  +{m.project_types.length - 3}
                </span>
              )}
            </div>

            {/* Status */}
            <div>
              {m.moratorium_active ? (
                <span
                  style={{
                    fontSize: 10.5,
                    fontWeight: 600,
                    letterSpacing: '0.04em',
                    color: 'var(--rust)',
                    background: 'rgba(168,90,74,0.10)',
                    border: '1px solid rgba(168,90,74,0.25)',
                    borderRadius: 4,
                    padding: '2px 7px',
                    textTransform: 'uppercase',
                  }}
                >
                  Moratorium
                </span>
              ) : (
                <span style={{ fontSize: 11, color: 'var(--text-soft)' }}>—</span>
              )}
            </div>

            {/* Refresh date */}
            <div style={{ fontSize: 12, color: 'var(--text-soft)' }} className="tnum">
              {m.last_refreshed_at
                ? new Date(m.last_refreshed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                : '—'}
            </div>

            {/* Arrow */}
            <div style={{ fontSize: 13, color: 'var(--text-soft)', textAlign: 'right' }}>→</div>
          </Link>
        ))}
      </div>

      {towns.length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--text-soft)', marginTop: 16, lineHeight: 1.6 }}>
          No municipalities seeded yet — run <code>python ingest/seed_municipalities.py</code>
        </div>
      )}
    </div>
  );
}

function MunicipalityDetail({ townId }: { townId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ['municipality', townId],
    queryFn: () => api.getMunicipality(townId),
  });
  const { data: doer } = useQuery({
    queryKey: ['doer-status', townId],
    queryFn: () => doerApi.townStatus(townId),
  });
  const [active, setActive] = useState<ProjectTypeCode>('solar_rooftop');
  if (isLoading || !data)
    return (
      <div style={{ padding: 36, color: 'var(--text-dim)', fontSize: 13 }}>Loading…</div>
    );
  const bylaws = data.project_type_bylaws[active] || null;

  return (
    <div style={{ padding: '36px 40px 80px', maxWidth: 1280 }}>
      <div style={{ marginBottom: 14 }}>
        <Link
          to="/municipalities"
          style={{ fontSize: 12, color: 'var(--text-dim)', textDecoration: 'none' }}
        >
          ← Municipalities
        </Link>
      </div>
      <div className="eyebrow" style={{ marginBottom: 10 }}>
        Municipality
      </div>
      <h1
        className="display"
        style={{ fontSize: 42, margin: 0, letterSpacing: '-0.022em', lineHeight: 1 }}
      >
        {data.town_name}
      </h1>
      <p
        className="tnum"
        style={{ fontSize: 13, color: 'var(--text-dim)', margin: '10px 0 0' }}
      >
        town_id {data.town_id} · refreshed{' '}
        {data.last_refreshed_at
          ? new Date(data.last_refreshed_at).toLocaleDateString()
          : '—'}
      </p>
      <hr className="rule" style={{ margin: '28px 0' }} />

      {data.moratorium_active && (
        <section
          style={{
            marginBottom: 24,
            padding: '14px 18px',
            background: 'color-mix(in srgb, var(--bad) 8%, transparent)',
            border: '1px solid color-mix(in srgb, var(--bad) 30%, transparent)',
            borderRadius: 10,
            display: 'flex',
            gap: 12,
            alignItems: 'flex-start',
          }}
        >
          <span style={{ fontSize: 16, lineHeight: 1 }}>⛔</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--bad)', marginBottom: 3 }}>
              Active moratorium
            </div>
            {data.moratoriums && Object.entries(data.moratoriums).map(([type, m]: [string, any]) => (
              <div key={type} style={{ fontSize: 12, color: 'var(--text-mid)', lineHeight: 1.6 }}>
                <strong>{type.replace(/_/g, ' ')}:</strong>{' '}
                {m.notes || 'No new applications accepted.'}
                {m.end_date && ` Expires ${new Date(m.end_date).toLocaleDateString()}.`}
                {m.source_url && (
                  <> <a href={m.source_url} target="_blank" rel="noreferrer" className="link-accent">Source ↗</a></>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {doer && (
        <section style={{ marginBottom: 28 }}>
          <div className="eyebrow-dim" style={{ marginBottom: 10 }}>
            DOER model bylaw status
          </div>
          <DoerAlignmentStrip status={doer} />
        </section>
      )}

      <section className="card" style={{ overflow: 'hidden' }}>
        <header
          style={{
            padding: '18px 22px 14px',
            borderBottom: '1px solid var(--border-soft)',
          }}
        >
          <h3
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 18,
              fontWeight: 500,
              letterSpacing: '-0.012em',
              margin: 0,
              color: 'var(--text)',
            }}
          >
            Zoning matrix
          </h3>
        </header>

        <div
          style={{
            display: 'flex',
            gap: 2,
            padding: '10px 16px 0',
            borderBottom: '1px solid var(--border-soft)',
            overflowX: 'auto',
          }}
        >
          {PROJECT_TYPES.map((pt) => (
            <button
              key={pt.code}
              onClick={() => setActive(pt.code)}
              style={{
                padding: '10px 14px',
                fontSize: 13,
                fontFamily: 'inherit',
                color: active === pt.code ? 'var(--text)' : 'var(--text-dim)',
                fontWeight: active === pt.code ? 500 : 400,
                borderBottom:
                  active === pt.code ? '2px solid var(--accent)' : '2px solid transparent',
                marginBottom: -1,
                background: 'transparent',
                border: 'none',
                borderTop: 'none',
                borderLeft: 'none',
                borderRight: 'none',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'color 120ms ease, border-color 120ms ease',
              }}
            >
              {pt.label}
            </button>
          ))}
        </div>

        <div style={{ padding: '22px 24px' }}>
          {bylaws ? (
            <BylawPanel bylaws={bylaws} />
          ) : (
            <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>
              No data for this project type.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function BylawPanel({ bylaws }: { bylaws: any }) {
  const range = bylaws.estimated_timeline_months;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 32 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
        <Block label="Approval authority" value={bylaws.approval_authority} />
        <Block label="Process" value={String(bylaws.process || '—').replace(/_/g, ' ')} />
        <Block
          label="Estimated timeline"
          value={range ? `${range[0]}–${range[1]} months` : '—'}
        />
        {bylaws.notes && <Block label="Notes" value={bylaws.notes} />}
        {bylaws.key_triggers?.length > 0 && (
          <div>
            <div className="label" style={{ marginBottom: 12 }}>
              Key triggers
            </div>
            <ul
              style={{
                listStyle: 'none',
                padding: 0,
                margin: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: 14,
              }}
            >
              {bylaws.key_triggers.map((t: any, i: number) => (
                <li
                  key={i}
                  style={{
                    borderLeft: '2px solid var(--accent)',
                    paddingLeft: 14,
                  }}
                >
                  <div style={{ fontSize: 14, lineHeight: 1.55, color: 'var(--text)' }}>
                    {t.description}
                  </div>
                  {t.bylaw_ref && (
                    <div
                      className="tnum"
                      style={{ fontSize: 11, marginTop: 4, color: 'var(--text-dim)' }}
                    >
                      {t.bylaw_ref}
                    </div>
                  )}
                  {t.source_url && (
                    <a
                      href={t.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="link-accent"
                      style={{ fontSize: 12, marginTop: 4, display: 'inline-block' }}
                    >
                      Source ↗
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <aside style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {bylaws.setbacks_ft && (
          <div
            style={{
              background: 'var(--surface)',
              border: '1px solid var(--border-soft)',
              borderRadius: 14,
              padding: '18px 20px',
            }}
          >
            <div className="label" style={{ marginBottom: 10 }}>
              Setbacks (ft)
            </div>
            <div
              className="tnum"
              style={{ fontSize: 13, display: 'flex', flexDirection: 'column', gap: 4 }}
            >
              <div>Front: {bylaws.setbacks_ft.front ?? '—'}</div>
              <div>Side: {bylaws.setbacks_ft.side ?? '—'}</div>
              <div>Rear: {bylaws.setbacks_ft.rear ?? '—'}</div>
            </div>
            {bylaws.setbacks_ft.note && (
              <div
                style={{
                  fontSize: 11,
                  marginTop: 10,
                  lineHeight: 1.5,
                  color: 'var(--text-dim)',
                  fontFamily: "'Fraunces', Georgia, serif",
                  fontStyle: 'italic',
                }}
              >
                {bylaws.setbacks_ft.note}
              </div>
            )}
          </div>
        )}
        {bylaws.citations?.length > 0 && (
          <div
            style={{
              background: 'var(--surface)',
              border: '1px solid var(--border-soft)',
              borderRadius: 14,
              padding: '18px 20px',
            }}
          >
            <div className="label" style={{ marginBottom: 10 }}>
              Citations
            </div>
            <ul
              style={{
                listStyle: 'none',
                padding: 0,
                margin: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              {bylaws.citations.map((c: any, i: number) => (
                <li key={i}>
                  <a
                    href={c.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="link-accent"
                    style={{ fontSize: 12, lineHeight: 1.45 }}
                  >
                    {c.document_title} ↗
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
        {bylaws.verification_note && (
          <div
            style={{
              fontSize: 11,
              lineHeight: 1.5,
              fontStyle: 'italic',
              padding: '0 2px',
              color: 'var(--text-dim)',
              fontFamily: "'Fraunces', Georgia, serif",
            }}
          >
            {bylaws.verification_note}
          </div>
        )}
      </aside>
    </div>
  );
}

function Block({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="label" style={{ marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 15, lineHeight: 1.5, color: 'var(--text)' }}>{value}</div>
    </div>
  );
}
