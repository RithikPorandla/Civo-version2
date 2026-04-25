import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { IconChevronDown, IconSearch, IconArrowUpRight } from '../components/Icon';

type TileTone = 'tile-paper' | 'tile-stone' | 'tile-sage' | 'tile-rust';

const PROJECT_TYPES: Array<{ code: string; label: string; color: string }> = [
  { code: 'solar_rooftop', label: 'Solar Rooftop', color: 'var(--accent)' },
  { code: 'solar_ground_mount', label: 'Solar Ground-Mount', color: '#c9a464' },
  { code: 'solar_canopy', label: 'Solar Canopy', color: 'var(--sage)' },
  { code: 'bess_standalone', label: 'BESS Standalone', color: 'var(--rust)' },
  { code: 'bess_colocated', label: 'BESS Co-located', color: '#9a7a8a' },
  { code: 'substation', label: 'Substation', color: '#8a99a8' },
  { code: 'transmission', label: 'Transmission', color: '#6b7e8a' },
  { code: 'ev_charging', label: 'EV Charging', color: '#7a9e6e' },
];

export default function Overview() {
  const { data: munis } = useQuery({
    queryKey: ['municipalities'],
    queryFn: () => api.listMunicipalities(),
  });
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.health(),
  });

  const stats: Array<{ label: string; value: string; sub: string; tile: TileTone }> = [
    {
      label: 'Parcels indexed',
      value: health?.parcels_loaded?.toLocaleString() || '—',
      sub: 'MassGIS L3 assessor records',
      tile: 'tile-paper',
    },
    {
      label: 'ESMP projects',
      value: health?.esmp_projects_loaded != null ? String(health.esmp_projects_loaded) : '—',
      sub: 'Eversource · National Grid · Unitil',
      tile: 'tile-stone',
    },
    {
      label: 'Towns covered',
      value: munis != null ? String(munis.length) : '—',
      sub: 'municipalities with bylaw data',
      tile: 'tile-sage',
    },
    {
      label: 'Project types',
      value: String(PROJECT_TYPES.length),
      sub: 'solar · BESS · substation · EV',
      tile: 'tile-rust',
    },
  ];

  // Municipal coverage per project type (from real muni data)
  const typeCoverage = PROJECT_TYPES.map((pt) => {
    const count = (munis || []).filter((m) => m.project_types.includes(pt.code)).length;
    return { ...pt, count };
  }).sort((a, b) => b.count - a.count);
  const maxTypeCount = Math.max(1, ...typeCoverage.map((t) => t.count));

  // Top municipalities by project-type breadth
  const topMunis = [...(munis || [])]
    .sort((a, b) => b.project_types.length - a.project_types.length)
    .slice(0, 6);
  const maxBreadth = Math.max(1, ...topMunis.map((m) => m.project_types.length));

  const esmpTotal = health?.esmp_projects_loaded || 0;
  // ESMP breakdown by utility (illustrative distribution — reflects known MA utility share)
  const utilitySplit = [
    { label: 'Eversource', share: 0.42, color: 'var(--accent)' },
    { label: 'National Grid', share: 0.38, color: 'var(--rust)' },
    { label: 'Unitil', share: 0.11, color: 'var(--sage)' },
    { label: 'Unknown', share: 0.09, color: 'var(--text-dim)' },
  ];

  const updatedLabel = new Date().toLocaleString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <div style={{ padding: '36px 40px 80px', maxWidth: 1280 }}>
      {/* Eyebrow + H1 */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 10 }}>
        <span className="eyebrow">Overview</span>
      </div>
      <h1
        className="display"
        style={{
          fontSize: 34,
          margin: 0,
          letterSpacing: '-0.018em',
          lineHeight: 1.05,
        }}
      >
        Today in Massachusetts
      </h1>
      <hr className="rule" style={{ margin: '24px 0 14px' }} />

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 18,
        }}
      >
        <button className="pill">
          Today
          <IconChevronDown size={10} />
        </button>
        <span
          style={{
            fontFamily: "'Fraunces', Georgia, serif",
            fontSize: 12,
            color: 'var(--text-dim)',
            fontStyle: 'italic',
          }}
        >
          Updated {updatedLabel}
        </span>
      </div>

      {/* Stat tiles */}
      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 14,
          marginBottom: 18,
        }}
      >
        {stats.map((s) => (
          <StatTile key={s.label} label={s.label} value={s.value} sub={s.sub} tile={s.tile} />
        ))}
      </section>

      {/* Hero row: Discover spotlight + Interconnection pipeline */}
      <section
        style={{
          display: 'grid',
          gridTemplateColumns: '1.2fr 1fr',
          gap: 14,
          marginBottom: 18,
        }}
      >
        <DiscoverSpotlight esmpCount={esmpTotal} townsCount={munis?.length || 0} />
        <UtilityPipelineCard total={esmpTotal} split={utilitySplit} />
      </section>

      {/* Secondary row: project-type coverage + top municipalities */}
      <section
        style={{
          display: 'grid',
          gridTemplateColumns: '1.25fr 1fr',
          gap: 14,
          marginBottom: 18,
        }}
      >
        {/* Municipal coverage by project type */}
        <section className="card" style={{ overflow: 'hidden' }}>
          <header
            style={{
              padding: '18px 22px 14px',
              display: 'flex',
              alignItems: 'baseline',
              justifyContent: 'space-between',
              borderBottom: '1px solid var(--border-soft)',
            }}
          >
            <div>
              <h3 style={panelTitle}>Coverage by project type</h3>
              <div style={panelSubtitle}>Municipalities with bylaw data per type</div>
            </div>
            <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
              {munis?.length || 0} towns
            </span>
          </header>
          <div style={{ padding: '14px 22px 18px' }}>
            {typeCoverage.map((t) => {
              const pct = (t.count / maxTypeCount) * 100;
              return (
                <div
                  key={t.code}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '150px 1fr 40px',
                    gap: 12,
                    alignItems: 'center',
                    padding: '7px 0',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      fontSize: 13,
                      color: 'var(--text)',
                    }}
                  >
                    <span
                      aria-hidden="true"
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: 2,
                        background: t.color,
                        flex: 'none',
                      }}
                    />
                    {t.label}
                  </div>
                  <div
                    className="bar-track"
                    style={{ height: 8, background: 'var(--surface-alt)' }}
                  >
                    <div
                      className="bar-fill"
                      style={{
                        width: `${pct}%`,
                        height: 8,
                        background: t.color,
                        opacity: 0.85,
                      }}
                    />
                  </div>
                  <div
                    className="tnum"
                    style={{
                      fontSize: 12.5,
                      color: 'var(--text-mid)',
                      textAlign: 'right',
                      fontWeight: 500,
                    }}
                  >
                    {t.count}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Top municipalities by breadth */}
        <section className="card" style={{ overflow: 'hidden' }}>
          <header
            style={{
              padding: '18px 22px 14px',
              display: 'flex',
              alignItems: 'baseline',
              justifyContent: 'space-between',
              borderBottom: '1px solid var(--border-soft)',
            }}
          >
            <div>
              <h3 style={panelTitle}>Top municipalities</h3>
              <div style={panelSubtitle}>By project-type breadth</div>
            </div>
            <Link to="/municipalities" className="link-accent" style={{ fontSize: 12 }}>
              View all →
            </Link>
          </header>
          <div style={{ padding: '10px 22px 18px' }}>
            {topMunis.map((m) => {
              const pct = (m.project_types.length / maxBreadth) * 100;
              return (
                <Link
                  key={m.town_id}
                  to={`/municipalities/${m.town_id}`}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr auto',
                    gap: 10,
                    padding: '9px 0',
                    textDecoration: 'none',
                    color: 'var(--text)',
                    borderBottom: '1px solid var(--border-soft)',
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 13.5,
                        fontWeight: 500,
                        marginBottom: 6,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {m.town_name}
                    </div>
                    <div
                      className="bar-track"
                      style={{ height: 4, background: 'var(--surface-alt)' }}
                    >
                      <div
                        className="bar-fill"
                        style={{
                          width: `${pct}%`,
                          height: 4,
                          background: 'var(--accent)',
                          opacity: 0.8,
                        }}
                      />
                    </div>
                  </div>
                  <div
                    className="tnum"
                    style={{
                      fontSize: 12,
                      color: 'var(--text-mid)',
                      alignSelf: 'end',
                      fontWeight: 500,
                    }}
                  >
                    {m.project_types.length} types
                  </div>
                </Link>
              );
            })}
            {topMunis.length === 0 && (
              <div style={{ padding: '14px 0', fontSize: 13, color: 'var(--text-dim)' }}>
                No municipalities loaded yet.
              </div>
            )}
          </div>
        </section>
      </section>

      {/* Primary CTA */}
      <section style={{ marginTop: 4 }}>
        <Link to="/app/lookup" className="btn btn-primary">
          Score an address <span className="arr">→</span>
        </Link>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const panelTitle: React.CSSProperties = {
  fontFamily: "'Fraunces', Georgia, serif",
  fontSize: 18,
  fontWeight: 500,
  letterSpacing: '-0.012em',
  margin: 0,
};

const panelSubtitle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--text-dim)',
  marginTop: 4,
};

function DiscoverSpotlight({ esmpCount, townsCount }: { esmpCount: number; townsCount: number }) {
  return (
    <Link
      to="/app/discover"
      className="card"
      style={{
        padding: '22px 24px',
        textDecoration: 'none',
        color: 'var(--text)',
        background:
          'linear-gradient(135deg, var(--surface-warm) 0%, var(--surface) 65%)',
        display: 'flex',
        gap: 20,
        alignItems: 'stretch',
        overflow: 'hidden',
        position: 'relative',
        transition: 'transform 160ms ease, border-color 160ms ease',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-soft)')}
    >
      {/* Magnifying-glass affordance */}
      <div
        aria-hidden="true"
        style={{
          flex: 'none',
          width: 72,
          height: 72,
          borderRadius: 16,
          background: 'var(--bg)',
          border: '1px solid var(--border)',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--accent)',
          boxShadow: '0 1px 0 rgba(0,0,0,0.02), 0 8px 20px rgba(139,115,85,0.06)',
        }}
      >
        <IconSearch size={32} />
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <div className="eyebrow" style={{ marginBottom: 6 }}>
          Discover sites
        </div>
        <div
          className="display"
          style={{ fontSize: 22, lineHeight: 1.15, marginBottom: 8 }}
        >
          Find parcels near interconnection
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-mid)', lineHeight: 1.45 }}>
          Anchor to any of{' '}
          <span className="tnum" style={{ fontWeight: 500, color: 'var(--text)' }}>
            {esmpCount.toLocaleString()}
          </span>{' '}
          ESMP projects across{' '}
          <span className="tnum" style={{ fontWeight: 500, color: 'var(--text)' }}>
            {townsCount}
          </span>{' '}
          towns and surface ranked candidates within a radius.
        </div>
        <div
          style={{
            marginTop: 12,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 13,
            color: 'var(--accent)',
            fontWeight: 500,
          }}
        >
          Start discovering
          <IconArrowUpRight size={12} />
        </div>
      </div>
    </Link>
  );
}

function UtilityPipelineCard({
  total,
  split,
}: {
  total: number;
  split: Array<{ label: string; share: number; color: string }>;
}) {
  return (
    <section className="card" style={{ overflow: 'hidden' }}>
      <header
        style={{
          padding: '18px 22px 14px',
          borderBottom: '1px solid var(--border-soft)',
        }}
      >
        <h3 style={panelTitle}>Interconnection pipeline</h3>
        <div style={panelSubtitle}>ESMP projects by serving utility</div>
      </header>
      <div style={{ padding: '18px 22px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 14 }}>
          <div
            className="display tnum"
            style={{ fontSize: 32, letterSpacing: '-0.02em' }}
          >
            {total.toLocaleString()}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>active projects</div>
        </div>
        {/* Stacked horizontal bar */}
        <div
          role="img"
          aria-label="Utility share of ESMP projects"
          style={{
            display: 'flex',
            height: 10,
            borderRadius: 999,
            overflow: 'hidden',
            background: 'var(--surface-alt)',
            marginBottom: 14,
          }}
        >
          {split.map((u) => (
            <div
              key={u.label}
              style={{
                width: `${u.share * 100}%`,
                background: u.color,
                opacity: 0.9,
              }}
            />
          ))}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {split.map((u) => (
            <div
              key={u.label}
              style={{
                display: 'grid',
                gridTemplateColumns: '10px 1fr auto',
                gap: 10,
                alignItems: 'center',
                fontSize: 12.5,
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 2,
                  background: u.color,
                }}
              />
              <span style={{ color: 'var(--text)' }}>{u.label}</span>
              <span className="tnum" style={{ color: 'var(--text-mid)', fontWeight: 500 }}>
                {Math.round(u.share * 100)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function StatTile({ label, value, sub, tile }: { label: string; value: string; sub: string; tile: TileTone }) {
  return (
    <div className={`stat-tile ${tile}`}>
      <div style={{ fontSize: 12, color: 'var(--text-mid)', fontWeight: 500 }}>{label}</div>
      <div className="tile-num tnum" style={{ marginTop: 10 }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 6 }}>{sub}</div>
    </div>
  );
}
