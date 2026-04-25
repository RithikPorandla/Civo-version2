/**
 * A stylized product screenshot for the showcase section — not a real
 * UI capture, but faithful enough to the Civo dashboard to communicate
 * shape, density, and hierarchy.
 */

type Kind = 'report' | 'discover' | 'municipality';

export default function ProductShot({ kind }: { kind: Kind }) {
  return (
    <div
      style={{
        background: 'var(--bg)',
        border: '1px solid var(--border)',
        borderRadius: 16,
        boxShadow: '0 30px 80px -30px rgba(26,26,26,0.18), 0 2px 4px rgba(26,26,26,0.04)',
        overflow: 'hidden',
      }}
    >
      <WindowChrome url={`civo.energy / ${kind}`} />
      {kind === 'report' && <ReportShot />}
      {kind === 'discover' && <DiscoverShot />}
      {kind === 'municipality' && <MunicipalityShot />}
    </div>
  );
}

function WindowChrome({ url }: { url: string }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '10px 14px',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border-soft)',
      }}
    >
      <Dot color="#e0b8a8" />
      <Dot color="#e5d3a0" />
      <Dot color="#bfc9b2" />
      <span
        style={{
          marginLeft: 'auto',
          fontSize: 10,
          color: 'var(--text-dim)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          fontFamily: 'var(--sans)',
        }}
      >
        {url}
      </span>
    </div>
  );
}

function Dot({ color }: { color: string }) {
  return (
    <span
      style={{ width: 9, height: 9, borderRadius: 999, background: color, display: 'inline-block' }}
    />
  );
}

function ReportShot() {
  return (
    <div style={{ padding: '18px 20px 22px' }}>
      <Eyebrow>Suitability Report</Eyebrow>
      <h4 style={displayH4}>Kendall Square, Cambridge</h4>
      <div style={meta}>M_035_CAMBRIDGE_0812 · v1.2 · Apr 19</div>

      <div style={tiles}>
        <Tile bg="#f7f3ea" label="Total score" value="92" suffix="/ 100" />
        <Tile bg="#e8ece2" label="Assessment" value="Suitable" />
        <Tile bg="#eef0ee" label="Primary" value="Grid" />
        <Tile bg="#f3e7df" label="Type" value="BESS" />
      </div>

      <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <Row name="Biodiversity" score={9.2} tone="good" />
        <Row name="Grid alignment" score={9.8} tone="good" />
        <Row name="Climate" score={7.6} tone="good" />
        <Row name="Burdens" score={6.4} tone="warn" />
      </div>

      <div
        style={{
          marginTop: 14,
          display: 'flex',
          flexWrap: 'wrap',
          gap: 5,
          paddingTop: 12,
          borderTop: '1px solid var(--border-soft)',
        }}
      >
        <Chip>225 CMR 29.05</Chip>
        <Chip>MassGIS L3</Chip>
        <Chip>Cambridge §22.20</Chip>
        <Chip>FEMA NFHL</Chip>
      </div>
    </div>
  );
}

function DiscoverShot() {
  return (
    <div style={{ padding: '18px 20px 22px' }}>
      <Eyebrow>Discover · ESMP Anchor</Eyebrow>
      <h4 style={displayH4}>Eversource · Framingham sub 22kV</h4>
      <div style={meta}>12 candidates · 38 pre-filter · 2 mi radius</div>

      <div
        style={{
          marginTop: 14,
          border: '1px solid var(--border-soft)',
          borderRadius: 10,
          overflow: 'hidden',
        }}
      >
        {[
          { r: 1, addr: '42 Prospect Rd, Framingham', score: 88, ac: 14.2, dist: 0.8 },
          { r: 2, addr: '150 Pleasant St, Ashland', score: 76, ac: 22.8, dist: 1.2 },
          { r: 3, addr: '8 Mill Pond Dr, Framingham', score: 71, ac: 9.4, dist: 1.6 },
          { r: 4, addr: '220 Main St, Sherborn', score: 64, ac: 18.1, dist: 1.9 },
        ].map((c, i) => (
          <div
            key={c.r}
            style={{
              display: 'grid',
              gridTemplateColumns: '28px 1fr 44px 46px 46px',
              alignItems: 'center',
              padding: '9px 12px',
              borderTop: i === 0 ? 'none' : '1px solid var(--border-soft)',
              fontSize: 11.5,
            }}
          >
            <span style={{ color: 'var(--text-dim)', fontFamily: "'Fraunces', Georgia, serif", fontStyle: 'italic' }}>
              {String(c.r).padStart(2, '0')}
            </span>
            <span style={{ color: 'var(--text)', fontWeight: 500 }}>{c.addr}</span>
            <span
              className="tnum"
              style={{
                fontSize: 11,
                color: c.score >= 80 ? 'var(--good)' : c.score >= 65 ? 'var(--gold, #c08a3e)' : 'var(--rust)',
                background:
                  c.score >= 80
                    ? 'var(--sage-soft, #eaf2e7)'
                    : c.score >= 65
                    ? 'var(--gold-soft, #f7efe0)'
                    : 'var(--bad-soft, #f5e8e4)',
                padding: '2px 6px',
                borderRadius: 999,
                fontWeight: 500,
                textAlign: 'center',
              }}
            >
              {c.score}
            </span>
            <span className="tnum" style={{ color: 'var(--text-mid)', textAlign: 'right' }}>
              {c.ac} ac
            </span>
            <span className="tnum" style={{ color: 'var(--text-dim)', textAlign: 'right' }}>
              {c.dist} mi
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MunicipalityShot() {
  return (
    <div style={{ padding: '18px 20px 22px' }}>
      <Eyebrow>Municipality</Eyebrow>
      <h4 style={displayH4}>Acton</h4>
      <div style={meta}>town_id 001 · refreshed 4/16/2026 · 8 project types</div>

      <div
        style={{
          marginTop: 14,
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: 8,
        }}
      >
        <MiniTile label="Approval authority" value="Planning Board" />
        <MiniTile label="Process" value="Special Permit" />
        <MiniTile label="Timeline" value="6–9 months" />
        <MiniTile label="Setback · front" value="50 ft" />
      </div>

      <div
        style={{
          marginTop: 14,
          padding: 12,
          background: 'var(--surface)',
          border: '1px solid var(--border-soft)',
          borderRadius: 10,
        }}
      >
        <div style={{ fontSize: 10, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--text-dim)', fontWeight: 500, marginBottom: 8 }}>
          Key triggers
        </div>
        <div style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.5, paddingLeft: 10, borderLeft: '2px solid var(--accent)' }}>
          § 5.4.2 · Ground-mount over 50 kW requires special permit + site plan review
        </div>
      </div>
    </div>
  );
}

// shared atoms
const displayH4: React.CSSProperties = {
  fontFamily: "'Fraunces', Georgia, serif",
  fontSize: 22,
  fontWeight: 500,
  letterSpacing: '-0.018em',
  margin: '8px 0 4px',
  lineHeight: 1.05,
  color: 'var(--text)',
};

const meta: React.CSSProperties = {
  fontSize: 11,
  color: 'var(--text-dim)',
  fontFamily: 'var(--sans)',
  letterSpacing: '0.01em',
};

const tiles: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(4, 1fr)',
  gap: 6,
  marginTop: 14,
};

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 10,
        letterSpacing: '0.14em',
        textTransform: 'uppercase',
        color: 'var(--accent)',
        fontWeight: 500,
      }}
    >
      {children}
    </div>
  );
}

function Tile({
  bg,
  label,
  value,
  suffix,
}: {
  bg: string;
  label: string;
  value: string;
  suffix?: string;
}) {
  return (
    <div
      style={{
        background: bg,
        border: '1px solid var(--border)',
        borderRadius: 8,
        padding: '8px 10px',
        minHeight: 58,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
      }}
    >
      <div style={{ fontSize: 10, color: 'var(--text-mid)', fontWeight: 500 }}>{label}</div>
      <div
        className="tnum"
        style={{
          fontFamily: "'Fraunces', Georgia, serif",
          fontSize: 18,
          letterSpacing: '-0.02em',
          color: 'var(--text)',
        }}
      >
        {value}
        {suffix && <span style={{ fontSize: 10, color: 'var(--text-mid)' }}>{' '}{suffix}</span>}
      </div>
    </div>
  );
}

function MiniTile({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        border: '1px solid var(--border-soft)',
        borderRadius: 8,
        padding: '10px 12px',
      }}
    >
      <div style={{ fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.04em', fontWeight: 500 }}>
        {label}
      </div>
      <div style={{ fontSize: 13, color: 'var(--text)', fontWeight: 500, marginTop: 4 }}>
        {value}
      </div>
    </div>
  );
}

function Row({
  name,
  score,
  tone,
}: {
  name: string;
  score: number;
  tone: 'good' | 'warn' | 'bad';
}) {
  const color =
    tone === 'good' ? 'var(--good)' : tone === 'warn' ? 'var(--gold, #c08a3e)' : 'var(--bad)';
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 80px 32px', alignItems: 'center', gap: 10 }}>
      <span style={{ fontSize: 12, color: 'var(--text)', fontWeight: 500 }}>{name}</span>
      <div
        style={{
          height: 4,
          background: 'var(--surface-alt)',
          borderRadius: 999,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            width: `${score * 10}%`,
            background: color,
            borderRadius: 999,
          }}
        />
      </div>
      <span className="tnum" style={{ fontSize: 11, color: 'var(--text-mid)', textAlign: 'right' }}>
        {score.toFixed(1)}
      </span>
    </div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        fontSize: 10,
        padding: '3px 9px',
        background: 'var(--accent-soft)',
        color: 'var(--accent)',
        borderRadius: 999,
        fontWeight: 500,
      }}
    >
      {children}
    </span>
  );
}
