import { Link } from 'react-router-dom';

const EXAMPLES = [
  { id: 1, address: 'Kendall Square, Cambridge, MA', score: 92.5, bucket: 'SUITABLE' },
  { id: 2, address: '50 Nagog Park, Acton, MA', score: 64.1, bucket: 'CONDITIONALLY SUITABLE' },
  { id: 3, address: 'East Freetown, MA', score: 35.4, bucket: 'CONSTRAINED' },
];

const bucketTone: Record<string, { c: string; bg: string; label: string }> = {
  SUITABLE: { c: 'var(--good)', bg: 'var(--sage-soft, #eaf2e7)', label: 'Suitable' },
  'CONDITIONALLY SUITABLE': {
    c: 'var(--gold, #c08a3e)',
    bg: 'var(--gold-soft, #f7efe0)',
    label: 'Conditional',
  },
  CONSTRAINED: { c: 'var(--bad)', bg: 'var(--bad-soft, #f5e8e4)', label: 'Constrained' },
};

export default function SiteSuitability() {
  const bucketCounts = EXAMPLES.reduce<Record<string, number>>((acc, e) => {
    acc[e.bucket] = (acc[e.bucket] || 0) + 1;
    return acc;
  }, {});

  const stats: Array<{
    label: string;
    value: string;
    delta: string;
    tile: 'tile-paper' | 'tile-stone' | 'tile-sage' | 'tile-rust';
  }> = [
    { label: 'Total reports', value: String(EXAMPLES.length), delta: '+3', tile: 'tile-paper' },
    {
      label: 'Suitable',
      value: String(bucketCounts.SUITABLE || 0),
      delta: '33%',
      tile: 'tile-sage',
    },
    {
      label: 'Conditional',
      value: String(bucketCounts['CONDITIONALLY SUITABLE'] || 0),
      delta: '33%',
      tile: 'tile-stone',
    },
    {
      label: 'Constrained',
      value: String(bucketCounts.CONSTRAINED || 0),
      delta: '33%',
      tile: 'tile-rust',
    },
  ];

  return (
    <div style={{ padding: '36px 40px 80px', maxWidth: 1280 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: 24,
          marginBottom: 10,
        }}
      >
        <div>
          <div className="eyebrow" style={{ marginBottom: 10 }}>
            Site Suitability
          </div>
          <h1
            className="display"
            style={{ fontSize: 34, margin: 0, letterSpacing: '-0.018em', lineHeight: 1.05 }}
          >
            Every parcel, scored.
          </h1>
          <p
            style={{
              fontSize: 15,
              lineHeight: 1.6,
              color: 'var(--text-mid)',
              maxWidth: 560,
              margin: '14px 0 0',
            }}
          >
            Scoring runs against 225 CMR 29.00 and town-level bylaws. Every criterion cites its
            source — nothing is inferred without a reference.
          </p>
        </div>
        <Link to="/app/lookup" className="btn btn-primary">
          Run a new report <span className="arr">→</span>
        </Link>
      </div>
      <hr className="rule" style={{ margin: '28px 0 18px' }} />

      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 14,
          marginBottom: 20,
        }}
      >
        {stats.map((s) => (
          <div key={s.label} className={`stat-tile ${s.tile}`}>
            <div style={{ fontSize: 12, color: 'var(--text-mid)', fontWeight: 500 }}>
              {s.label}
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                justifyContent: 'space-between',
                gap: 8,
                marginTop: 10,
              }}
            >
              <div className="tile-num tnum">{s.value}</div>
              <div className="tnum" style={{ fontSize: 12, color: 'var(--text-dim)' }}>
                {s.delta}
              </div>
            </div>
          </div>
        ))}
      </section>

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
          <h3
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 18,
              fontWeight: 500,
              letterSpacing: '-0.012em',
              margin: 0,
            }}
          >
            Reference parcels
          </h3>
          <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
            Three canonical examples
          </span>
        </header>
        <div
          className="label"
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 100px 160px 80px',
            padding: '10px 22px',
            background: 'var(--surface)',
            borderBottom: '1px solid var(--border-soft)',
          }}
        >
          <div>Address</div>
          <div>Score</div>
          <div>Status</div>
          <div />
        </div>
        {EXAMPLES.map((e, i) => {
          const tone = bucketTone[e.bucket];
          return (
            <div
              key={e.id}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 100px 160px 80px',
                alignItems: 'center',
                padding: '16px 22px',
                borderTop: i === 0 ? 'none' : '1px solid var(--border-soft)',
              }}
            >
              <div style={{ fontSize: 14, fontWeight: 500 }}>{e.address}</div>
              <div
                className="tnum"
                style={{
                  fontFamily: "'Fraunces', Georgia, serif",
                  fontSize: 22,
                  fontWeight: 400,
                  letterSpacing: '-0.018em',
                }}
              >
                {e.score}
              </div>
              <div>
                <span
                  style={{
                    fontSize: 12,
                    color: tone.c,
                    background: tone.bg,
                    padding: '4px 10px',
                    borderRadius: 999,
                    fontWeight: 500,
                  }}
                >
                  {tone.label}
                </span>
              </div>
              <div style={{ textAlign: 'right' }}>
                <Link to={`/report/${e.id}`} className="link-accent" style={{ fontSize: 13 }}>
                  Open →
                </Link>
              </div>
            </div>
          );
        })}
      </section>
      <p
        style={{
          fontSize: 12,
          color: 'var(--text-dim)',
          margin: '12px 4px 0',
          fontStyle: 'italic',
          fontFamily: "'Fraunces', Georgia, serif",
        }}
      >
        Reference rows assume report IDs 1–3 exist in your local database.
      </p>
    </div>
  );
}
