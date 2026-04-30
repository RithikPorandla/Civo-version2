import { Link } from 'react-router-dom';

type Status = 'Suitable' | 'Conditional' | 'Constrained';

interface ReportRow { score: number; address: string; timeAgo: string; status: Status; }
interface FeedItem  { severity: 'red' | 'green' | 'amber'; headline: string; body: string; timeAgo: string; }

const RECENT_REPORTS: ReportRow[] = [
  { score: 65, address: '50 Nagog Park, Acton',     timeAgo: '2 hours ago', status: 'Conditional' },
  { score: 82, address: '280 Main St, Acton',        timeAgo: 'Yesterday',   status: 'Suitable'    },
  { score: 78, address: '12 Mill Rd, Burlington',    timeAgo: 'Yesterday',   status: 'Suitable'    },
  { score: 41, address: '45 Cedar St, Natick',       timeAgo: '3 days ago',  status: 'Constrained' },
  { score: 71, address: '8 Concord Rd, Acton',       timeAgo: '4 days ago',  status: 'Conditional' },
];

const FEED_ITEMS: FeedItem[] = [
  { severity: 'red',   headline: 'Acton ConCom denied BESS project',  body: 'Similar constraint profile to your watched site at 50 Nagog Park. Wetland buffer was the deciding factor.', timeAgo: '3 hours ago' },
  { severity: 'green', headline: 'Falmouth adopted DOER BESS bylaw',  body: 'Three parcels in your portfolio are in Falmouth. Their permitting path just improved.',                      timeAgo: '1 day ago'   },
  { severity: 'amber', headline: 'ESMP timeline updated',             body: 'North Acton substation moved from 2033 to 2028. Grid access improves for nearby parcels.',                   timeAgo: '2 days ago'  },
];

// Sparkline data per tile — last 8 weeks
const TILES = [
  { label: 'Reports this month', value: '23', delta: '↑12% from last month', spark: [6,8,5,9,11,10,14,15], color: '#c9a464' },
  { label: 'Sites in portfolio',  value: '8',  delta: '↑2 new this week',    spark: [4,4,5,5,5,6,7,8],     color: '#6b7e5a' },
  { label: 'Towns covered',       value: '14', delta: 'Across 3 sub-regions', spark: [8,9,9,10,11,12,13,14], color: '#8b7355' },
  { label: 'Avg. score',          value: '67', delta: 'Professional tier',    spark: [71,68,64,70,65,69,66,67], color: '#a85a4a' },
];

// Score distribution — bar chart data
const SCORE_DIST = [
  { label: '0–40',  count: 2, cls: 's-low'  },
  { label: '41–55', count: 4, cls: 's-low'  },
  { label: '56–70', count: 8, cls: 's-mid'  },
  { label: '71–80', count: 6, cls: 's-mid'  },
  { label: '81–90', count: 5, cls: 's-high' },
  { label: '91+',   count: 3, cls: 's-high' },
];

const BAR_COLOR: Record<string, string> = {
  's-high': '#6b7e5a',
  's-mid':  '#c9a464',
  's-low':  '#a85a4a',
};

const DOT_COLORS: Record<FeedItem['severity'], string> = {
  red:   '#a85a4a',
  green: '#6b7e5a',
  amber: '#c9a464',
};

function scoreClass(n: number) {
  if (n >= 75) return 's-high';
  if (n >= 50) return 's-mid';
  return 's-low';
}

const CHIP_CLASS: Record<Status, string> = {
  Suitable:    'chip suit',
  Conditional: 'chip cond',
  Constrained: 'chip cons',
};

// Sparkline: 8-point line chart, 64×28
function Sparkline({ data, color }: { data: number[]; color: string }) {
  const w = 64, h = 28, pad = 2;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const xs = data.map((_, i) => pad + (i / (data.length - 1)) * (w - pad * 2));
  const ys = data.map((v) => h - pad - ((v - min) / range) * (h - pad * 2));
  const pts = xs.map((x, i) => `${x},${ys[i]}`).join(' ');
  const area = `M${xs[0]},${ys[0]} ` + xs.slice(1).map((x, i) => `L${x},${ys[i + 1]}`).join(' ') + ` L${xs[xs.length - 1]},${h} L${xs[0]},${h} Z`;

  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      <defs>
        <linearGradient id={`sg-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.22" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#sg-${color.replace('#', '')})`} />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={xs[xs.length - 1]} cy={ys[ys.length - 1]} r="2.5" fill={color} />
    </svg>
  );
}

export default function Overview() {
  const maxCount = Math.max(...SCORE_DIST.map((d) => d.count));

  return (
    <div className="page" style={{ fontFamily: 'var(--sans)' }}>

      {/* Page header */}
      <div style={{ marginBottom: 24 }}>
        <div className="page-eyebrow">Dashboard</div>
        <h1 className="page-h1">Welcome back, Rithik</h1>
        <p className="page-sub">Your portfolio at a glance</p>
      </div>

      {/* Stat tiles with sparklines */}
      <div className="tiles">
        {TILES.map((t) => (
          <div className="tile" key={t.label}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div className="tile-label">{t.label}</div>
              <Sparkline data={t.spark} color={t.color} />
            </div>
            <div className="tile-num">{t.value}</div>
            <div className="tile-delta">{t.delta}</div>
          </div>
        ))}
      </div>

      {/* Two-column layout */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1.6fr 1fr',
          gap: 'var(--gap)',
          alignItems: 'start',
          marginBottom: 'var(--gap)',
        }}
      >
        {/* Recent reports */}
        <section className="card" style={{ overflow: 'hidden' }}>
          <header
            style={{
              padding: '14px 20px 12px',
              borderBottom: '1px solid var(--border-soft)',
              display: 'flex',
              alignItems: 'baseline',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div style={{ fontFamily: 'var(--display)', fontSize: 15, fontWeight: 500, letterSpacing: '-0.01em', color: 'var(--text)' }}>
                Recent reports
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--text-soft)', marginTop: 2 }}>
                Your last 30 days of site activity
              </div>
            </div>
            <Link to="/app/lookup" style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 500, textDecoration: 'none' }}>
              New report →
            </Link>
          </header>

          <div>
            {RECENT_REPORTS.map((row, idx) => (
              <Link key={idx} to="/app/lookup" className="report-row">
                <div className={`score ${scoreClass(row.score)}`}>{row.score}</div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.3 }}>
                    {row.address}
                  </div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-soft)', marginTop: 2 }}>
                    {row.timeAgo}
                  </div>
                </div>
                <div className={CHIP_CLASS[row.status]}>{row.status}</div>
              </Link>
            ))}
          </div>
        </section>

        {/* Intelligence feed */}
        <section className="card" style={{ overflow: 'hidden' }}>
          <header style={{ padding: '14px 20px 12px', borderBottom: '1px solid var(--border-soft)' }}>
            <div style={{ fontFamily: 'var(--display)', fontSize: 15, fontWeight: 500, letterSpacing: '-0.01em', color: 'var(--text)' }}>
              Intelligence feed
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--text-soft)', marginTop: 2 }}>
              Regulatory signals relevant to your portfolio
            </div>
          </header>
          <div>
            {FEED_ITEMS.map((item, idx) => (
              <div key={idx} className="feed-item">
                <div className="feed-dot" style={{ background: DOT_COLORS[item.severity] }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="feed-title">{item.headline}</div>
                  <div className="feed-body">{item.body}</div>
                  <div className="feed-time">{item.timeAgo}</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Score distribution bar chart */}
      <section className="card" style={{ overflow: 'hidden' }}>
        <header style={{ padding: '14px 20px 12px', borderBottom: '1px solid var(--border-soft)', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontFamily: 'var(--display)', fontSize: 15, fontWeight: 500, letterSpacing: '-0.01em', color: 'var(--text)' }}>
              Score distribution
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--text-soft)', marginTop: 2 }}>
              All sites scored this month
            </div>
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--text-soft)' }}>28 sites total</div>
        </header>

        <div style={{ padding: '20px 24px 16px', display: 'flex', alignItems: 'flex-end', gap: 10 }}>
          {SCORE_DIST.map((d) => {
            const pct = (d.count / maxCount) * 100;
            return (
              <div key={d.label} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                {/* Count label */}
                <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-mid)', lineHeight: 1 }}>{d.count}</div>
                {/* Bar */}
                <div
                  style={{
                    width: '100%',
                    height: `${Math.max(pct * 1.0, 6)}px`,
                    minHeight: 6,
                    maxHeight: 100,
                    background: BAR_COLOR[d.cls],
                    borderRadius: '4px 4px 0 0',
                    opacity: 0.85,
                    transition: 'height 300ms ease',
                  }}
                />
                {/* Label */}
                <div style={{ fontSize: 10.5, color: 'var(--text-soft)', textAlign: 'center', lineHeight: 1.2 }}>{d.label}</div>
              </div>
            );
          })}

          {/* Y-axis reference lines overlay */}
        </div>

        {/* Legend */}
        <div style={{ padding: '0 24px 16px', display: 'flex', gap: 16 }}>
          {[
            { color: BAR_COLOR['s-high'], label: 'Suitable (75+)'     },
            { color: BAR_COLOR['s-mid'],  label: 'Conditional (50–74)' },
            { color: BAR_COLOR['s-low'],  label: 'Constrained (<50)'   },
          ].map((l) => (
            <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: l.color, opacity: 0.85 }} />
              <span style={{ fontSize: 11, color: 'var(--text-soft)' }}>{l.label}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
