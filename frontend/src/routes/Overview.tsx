import { Link } from 'react-router-dom';

type Status = 'Suitable' | 'Conditional' | 'Constrained';

interface ReportRow { score: number; address: string; timeAgo: string; status: Status; projectType: string; }
interface FeedItem  { severity: 'red' | 'green' | 'amber'; headline: string; body: string; timeAgo: string; }

const RECENT_REPORTS: ReportRow[] = [
  { score: 65, address: '50 Nagog Park, Acton',      timeAgo: '2 hours ago', status: 'Conditional', projectType: 'BESS' },
  { score: 82, address: '280 Main St, Acton',         timeAgo: 'Yesterday',   status: 'Suitable',    projectType: 'BESS' },
  { score: 78, address: '12 Mill Rd, Burlington',     timeAgo: 'Yesterday',   status: 'Suitable',    projectType: 'Solar' },
  { score: 41, address: '45 Cedar St, Natick',        timeAgo: '3 days ago',  status: 'Constrained', projectType: 'Solar' },
  { score: 71, address: '8 Concord Rd, Acton',        timeAgo: '4 days ago',  status: 'Conditional', projectType: 'BESS' },
];

const FEED_ITEMS: FeedItem[] = [
  { severity: 'red',   headline: 'Acton ConCom denied BESS project',  body: 'Similar constraint profile to your watched site at 50 Nagog Park. Wetland buffer was the deciding factor.', timeAgo: '3 hours ago' },
  { severity: 'green', headline: 'Falmouth adopted DOER BESS bylaw',  body: 'Three parcels in your portfolio are in Falmouth. Their permitting path just improved.',                      timeAgo: '1 day ago'   },
  { severity: 'amber', headline: 'ESMP timeline updated',             body: 'North Acton substation moved from 2033 to 2028. Grid access improves for nearby parcels.',                   timeAgo: '2 days ago'  },
];

const TILES = [
  { label: 'Reports this month', value: '23', trend: '+12%', up: true,  spark: [6,8,5,9,11,10,14,15], color: '#c9a464' },
  { label: 'Sites in portfolio',  value: '8',  trend: '+2',   up: true,  spark: [4,4,5,5,5,6,7,8],     color: '#6b7e5a' },
  { label: 'Towns covered',       value: '14', trend: '+3',   up: true,  spark: [8,9,9,10,11,12,13,14], color: '#8b7355' },
  { label: 'Avg. score',          value: '67', trend: '−2',   up: false, spark: [71,68,64,70,65,69,66,67], color: '#a85a4a' },
];

const SCORE_DIST = [
  { label: '0–40',  count: 2, cls: 's-low'  },
  { label: '41–55', count: 4, cls: 's-low'  },
  { label: '56–70', count: 8, cls: 's-mid'  },
  { label: '71–80', count: 6, cls: 's-mid'  },
  { label: '81–90', count: 5, cls: 's-high' },
  { label: '91+',   count: 3, cls: 's-high' },
];

const TOP_CONSTRAINTS = [
  { label: 'ConCom jurisdiction', count: 11, pct: 48 },
  { label: 'Wetland setback',     count: 9,  pct: 39 },
  { label: 'Grid capacity',       count: 7,  pct: 30 },
  { label: 'ACEC overlay',        count: 4,  pct: 17 },
  { label: 'Moratorium',          count: 2,  pct: 9  },
];

const BAR_COLOR: Record<string, string> = { 's-high': '#6b7e5a', 's-mid': '#c9a464', 's-low': '#a85a4a' };
const DOT_COLORS: Record<FeedItem['severity'], string> = { red: '#a85a4a', green: '#6b7e5a', amber: '#c9a464' };

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

function Sparkline({ data, color }: { data: number[]; color: string }) {
  const w = 56, h = 24, pad = 2;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const xs = data.map((_, i) => pad + (i / (data.length - 1)) * (w - pad * 2));
  const ys = data.map((v) => h - pad - ((v - min) / range) * (h - pad * 2));
  const pts = xs.map((x, i) => `${x},${ys[i]}`).join(' ');
  const area = `M${xs[0]},${ys[0]} ` + xs.slice(1).map((x, i) => `L${x},${ys[i + 1]}`).join(' ') + ` L${xs[xs.length - 1]},${h} L${xs[0]},${h} Z`;
  const id = `sg${color.replace('#', '')}`;
  return (
    <svg width={w} height={h} style={{ display: 'block', flexShrink: 0 }}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.2" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${id})`} />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={xs[xs.length-1]} cy={ys[ys.length-1]} r="2" fill={color} />
    </svg>
  );
}

export default function Overview() {
  const maxCount = Math.max(...SCORE_DIST.map((d) => d.count));

  return (
    <div className="page" style={{ fontFamily: 'var(--sans)' }}>

      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <div className="page-eyebrow">Dashboard</div>
        <h1 className="page-h1">Good morning, Rithik</h1>
        <p className="page-sub">23 reports this month · 8 sites tracked · last updated 2 hours ago</p>
      </div>

      {/* Stat tiles */}
      <div className="tiles">
        {TILES.map((t) => (
          <div className="tile" key={t.label}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div className="tile-label">{t.label}</div>
              <Sparkline data={t.spark} color={t.color} />
            </div>
            <div className="tile-num">{t.value}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: t.up ? '#6b7e5a' : '#a85a4a' }}>
                {t.up ? '↑' : '↓'} {t.trend}
              </span>
              <span className="tile-delta">vs last month</span>
            </div>
          </div>
        ))}
      </div>

      {/* Main two-column */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 'var(--gap)', alignItems: 'start', marginBottom: 'var(--gap)' }}>

        {/* Recent reports */}
        <section className="card" style={{ overflow: 'hidden' }}>
          <header style={{ padding: '12px 18px 10px', borderBottom: '1px solid var(--border-soft)', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontFamily: 'var(--display)', fontSize: 14, fontWeight: 500, color: 'var(--text)', letterSpacing: '-0.01em' }}>Recent reports</div>
              <div style={{ fontSize: 11.5, color: 'var(--text-soft)', marginTop: 2 }}>Last 30 days of site activity</div>
            </div>
            <Link to="/app/lookup" style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 500, textDecoration: 'none' }}>New report →</Link>
          </header>
          <div>
            {RECENT_REPORTS.map((row, idx) => (
              <Link
                key={idx}
                to="/app/lookup"
                className="report-row"
              >
                <div className={`score ${scoreClass(row.score)}`}>{row.score}</div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.3 }}>
                    {row.address}
                  </div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-soft)', marginTop: 2 }}>
                    {row.projectType} · {row.timeAgo}
                  </div>
                </div>
                <div className={CHIP_CLASS[row.status]}>{row.status}</div>
              </Link>
            ))}
          </div>
        </section>

        {/* Intelligence feed */}
        <section className="card" style={{ overflow: 'hidden' }}>
          <header style={{ padding: '12px 18px 10px', borderBottom: '1px solid var(--border-soft)' }}>
            <div style={{ fontFamily: 'var(--display)', fontSize: 14, fontWeight: 500, color: 'var(--text)', letterSpacing: '-0.01em' }}>Intelligence feed</div>
            <div style={{ fontSize: 11.5, color: 'var(--text-soft)', marginTop: 2 }}>Regulatory signals for your portfolio</div>
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

      {/* Bottom row: score distribution + top constraints */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap)' }}>

        {/* Score distribution */}
        <section className="card" style={{ overflow: 'hidden' }}>
          <header style={{ padding: '12px 18px 10px', borderBottom: '1px solid var(--border-soft)', display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div style={{ fontFamily: 'var(--display)', fontSize: 14, fontWeight: 500, color: 'var(--text)', letterSpacing: '-0.01em' }}>Score distribution</div>
            <div style={{ fontSize: 11.5, color: 'var(--text-soft)' }}>28 sites this month</div>
          </header>
          <div style={{ padding: '16px 18px 8px', display: 'flex', alignItems: 'flex-end', gap: 8 }}>
            {SCORE_DIST.map((d) => {
              const barH = Math.max((d.count / maxCount) * 80, 6);
              return (
                <div key={d.label} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-mid)' }}>{d.count}</div>
                  <div style={{ width: '100%', height: barH, background: BAR_COLOR[d.cls], borderRadius: '3px 3px 0 0', opacity: 0.82 }} />
                  <div style={{ fontSize: 10, color: 'var(--text-soft)', textAlign: 'center' }}>{d.label}</div>
                </div>
              );
            })}
          </div>
          <div style={{ padding: '0 18px 12px', display: 'flex', gap: 14 }}>
            {[['#6b7e5a','Suitable 75+'],['#c9a464','Conditional 50–74'],['#a85a4a','Constrained <50']].map(([c,l]) => (
              <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <div style={{ width: 7, height: 7, borderRadius: 2, background: c, opacity: 0.82 }} />
                <span style={{ fontSize: 10.5, color: 'var(--text-soft)' }}>{l}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Top constraints */}
        <section className="card" style={{ overflow: 'hidden' }}>
          <header style={{ padding: '12px 18px 10px', borderBottom: '1px solid var(--border-soft)', display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div style={{ fontFamily: 'var(--display)', fontSize: 14, fontWeight: 500, color: 'var(--text)', letterSpacing: '-0.01em' }}>Top constraints</div>
            <div style={{ fontSize: 11.5, color: 'var(--text-soft)' }}>Across all sites</div>
          </header>
          <div style={{ padding: '10px 18px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {TOP_CONSTRAINTS.map((c) => (
              <div key={c.label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
                  <span style={{ fontSize: 12.5, color: 'var(--text-mid)', fontWeight: 500 }}>{c.label}</span>
                  <span style={{ fontSize: 11.5, color: 'var(--text-soft)' }}>{c.count} sites · {c.pct}%</span>
                </div>
                <div style={{ height: 4, background: 'var(--border-soft)', borderRadius: 999 }}>
                  <div style={{ width: `${c.pct}%`, height: 4, background: 'var(--accent)', borderRadius: 999, opacity: 0.6 }} />
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

    </div>
  );
}
