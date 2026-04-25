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

const TILE_CLASSES = ['tile-paper', 'tile-stone', 'tile-sage', 'tile-rust'] as const;

export default function MunicipalitiesRoute() {
  const { townId } = useParams();
  if (townId) return <MunicipalityDetail townId={Number(townId)} />;
  return <MunicipalityIndex />;
}

function MunicipalityIndex() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['municipalities'],
    queryFn: () => api.listMunicipalities(),
  });
  if (isPending)
    return (
      <div style={{ padding: 36, color: 'var(--text-dim)', fontSize: 13 }}>Loading…</div>
    );
  if (isError)
    return (
      <div style={{ padding: 36, maxWidth: 560 }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--bad)', marginBottom: 6 }}>
          Could not load municipalities
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.6 }}>
          {String(error)}
        </div>
      </div>
    );

  const refreshedCount = (data || []).filter((m) => m.last_refreshed_at).length;
  const latestRefresh = (data || [])
    .map((m) => m.last_refreshed_at)
    .filter(Boolean)
    .sort()
    .at(-1);
  const stats = [
    { label: 'Towns indexed', value: String(data?.length || 0) },
    {
      label: 'Project types',
      value: String(new Set((data || []).flatMap((m) => m.project_types)).size),
    },
    {
      label: 'Last refreshed',
      value: latestRefresh ? new Date(latestRefresh).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '—',
    },
    { label: 'With bylaw data', value: String(refreshedCount) },
  ];

  return (
    <div style={{ padding: '36px 40px 80px', maxWidth: 1280 }}>
      <div className="eyebrow" style={{ marginBottom: 10 }}>
        Coverage
      </div>
      <h1
        className="display"
        style={{ fontSize: 34, margin: 0, letterSpacing: '-0.018em', lineHeight: 1.05 }}
      >
        Municipalities
      </h1>
      <p
        style={{
          fontSize: 15,
          lineHeight: 1.6,
          color: 'var(--text-mid)',
          maxWidth: 620,
          margin: '14px 0 0',
        }}
      >
        Zoning and permitting posture for every MA town in the corpus — refreshed nightly, cited
        to the source bylaw.
      </p>
      <hr className="rule" style={{ margin: '28px 0 18px' }} />

      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 14,
          marginBottom: 20,
        }}
      >
        {stats.map((s, i) => (
          <div key={s.label} className={`stat-tile ${TILE_CLASSES[i % TILE_CLASSES.length]}`}>
            <div style={{ fontSize: 12, color: 'var(--text-mid)', fontWeight: 500 }}>
              {s.label}
            </div>
            <div className="tile-num tnum" style={{ marginTop: 8 }}>{s.value}</div>
          </div>
        ))}
      </section>

      {data?.length === 0 && (
        <div style={{ fontSize: 13, color: 'var(--text-dim)', padding: '14px 0' }}>
          No municipalities seeded yet — run <code>python ingest/seed_municipalities.py</code> to add towns.
        </div>
      )}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: 14,
        }}
      >
        {(data || []).map((m) => (
          <Link
            key={m.town_id}
            to={`/municipalities/${m.town_id}`}
            className="card muni-card"
            style={{
              padding: '20px 22px',
              textDecoration: 'none',
              color: 'inherit',
              display: 'block',
              transition: 'border-color 120ms ease, background 120ms ease',
              borderColor: m.moratorium_active ? 'var(--bad)' : undefined,
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                justifyContent: 'space-between',
                gap: 12,
              }}
            >
              <h3
                style={{
                  fontFamily: "'Fraunces', Georgia, serif",
                  fontSize: 20,
                  fontWeight: 500,
                  letterSpacing: '-0.015em',
                  margin: 0,
                  color: 'var(--text)',
                }}
              >
                {m.town_name}
              </h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                {m.moratorium_active && (
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      letterSpacing: '0.04em',
                      color: 'var(--bad)',
                      background: 'color-mix(in srgb, var(--bad) 10%, transparent)',
                      border: '1px solid color-mix(in srgb, var(--bad) 25%, transparent)',
                      borderRadius: 4,
                      padding: '2px 6px',
                      textTransform: 'uppercase',
                    }}
                  >
                    Moratorium
                  </span>
                )}
                <span className="chip">{m.project_types.length} types</span>
              </div>
            </div>
            <div
              className="tnum"
              style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 8 }}
            >
              Refreshed{' '}
              {m.last_refreshed_at
                ? new Date(m.last_refreshed_at).toLocaleDateString()
                : '—'}
            </div>
          </Link>
        ))}
      </div>
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
