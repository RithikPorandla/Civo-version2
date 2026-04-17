import { Link } from 'react-router-dom';
import { IconArrowUpRight } from '../components/Icon';

const EXAMPLES = [
  { id: 1, address: 'Kendall Square, Cambridge, MA', score: 92.5, bucket: 'SUITABLE' },
  { id: 2, address: '50 Nagog Park, Acton, MA', score: 64.1, bucket: 'CONDITIONALLY SUITABLE' },
  { id: 3, address: 'East Freetown, MA', score: 35.4, bucket: 'CONSTRAINED' },
];

const bucketTone: Record<string, { c: string; bg: string; label: string }> = {
  SUITABLE: { c: '#1f8a3d', bg: '#e4f3e7', label: 'Suitable' },
  'CONDITIONALLY SUITABLE': { c: '#b6781c', bg: '#fbecd6', label: 'Conditional' },
  CONSTRAINED: { c: '#c0392b', bg: '#f9e3df', label: 'Constrained' },
};

export default function SiteSuitability() {
  const bucketCounts = EXAMPLES.reduce<Record<string, number>>((acc, e) => {
    acc[e.bucket] = (acc[e.bucket] || 0) + 1;
    return acc;
  }, {});

  const stats = [
    { label: 'Total reports', value: String(EXAMPLES.length), delta: '+3', bg: '#e3ebf5' },
    { label: 'Suitable', value: String(bucketCounts.SUITABLE || 0), delta: '33%', bg: '#dbe8cc' },
    {
      label: 'Conditional',
      value: String(bucketCounts['CONDITIONALLY SUITABLE'] || 0),
      delta: '33%',
      bg: '#fbecd6',
    },
    {
      label: 'Constrained',
      value: String(bucketCounts.CONSTRAINED || 0),
      delta: '33%',
      bg: '#f9e3df',
    },
  ];

  return (
    <div style={{ padding: '24px 28px 40px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 20,
        }}
      >
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, letterSpacing: -0.3, margin: 0 }}>
            Site Suitability
          </h1>
          <p className="text-textMid" style={{ fontSize: 13, margin: '4px 0 0' }}>
            Every parcel scored against 225 CMR 29.00.
          </p>
        </div>
        <Link to="/lookup" className="btn btn-primary">
          Run a new report →
        </Link>
      </div>

      {/* Stats */}
      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 16,
          marginBottom: 20,
        }}
      >
        {stats.map((s) => (
          <div key={s.label} className="stat-tile" style={{ background: s.bg }}>
            <div style={{ fontSize: 13, fontWeight: 500 }}>{s.label}</div>
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                justifyContent: 'space-between',
              }}
            >
              <div
                style={{
                  fontSize: 30,
                  fontWeight: 600,
                  letterSpacing: -0.5,
                  lineHeight: 1.05,
                }}
              >
                {s.value}
              </div>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  fontSize: 12,
                }}
              >
                {s.delta}
                <IconArrowUpRight size={12} />
              </div>
            </div>
          </div>
        ))}
      </section>

      {/* Reference parcels table */}
      <section className="card" style={{ overflow: 'hidden' }}>
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid #e8eaed',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 600 }}>Reference parcels</div>
          <span className="text-textDim" style={{ fontSize: 12 }}>
            Three canonical examples
          </span>
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 100px 160px 80px',
            padding: '10px 20px',
            fontSize: 11,
            color: '#8a8a8a',
            letterSpacing: 0.3,
            textTransform: 'uppercase',
            fontWeight: 500,
            background: '#fafbfc',
            borderBottom: '1px solid #e8eaed',
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
                padding: '16px 20px',
                borderTop: i === 0 ? 'none' : '1px solid #e8eaed',
              }}
            >
              <div style={{ fontSize: 14, fontWeight: 500 }}>{e.address}</div>
              <div style={{ fontSize: 20, fontWeight: 600, letterSpacing: -0.4 }}>
                {e.score}
              </div>
              <div>
                <span
                  style={{
                    fontSize: 12,
                    color: tone.c,
                    background: tone.bg,
                    padding: '4px 10px',
                    borderRadius: 100,
                    fontWeight: 500,
                  }}
                >
                  {tone.label}
                </span>
              </div>
              <div style={{ textAlign: 'right' }}>
                <Link
                  to={`/report/${e.id}`}
                  className="text-accent"
                  style={{ fontSize: 13, textDecoration: 'none' }}
                >
                  Open →
                </Link>
              </div>
            </div>
          );
        })}
      </section>
      <p className="text-textDim" style={{ fontSize: 12, margin: '10px 4px 0' }}>
        Reference rows assume report IDs 1–3 exist in your local database.
      </p>
    </div>
  );
}
