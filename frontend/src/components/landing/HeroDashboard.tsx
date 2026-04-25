/**
 * Bigger, denser hero mock — a simulated Civo dashboard with the
 * report panel on the left and a criteria breakdown + citation stack
 * on the right. Used as the hero visual so the landing has an
 * immediate "this is the product" moment.
 */
export default function HeroDashboard() {
  return (
    <div
      style={{
        background: 'var(--bg)',
        border: '1px solid var(--border)',
        borderRadius: 16,
        boxShadow:
          '0 40px 100px -30px rgba(10,10,10,0.22), 0 4px 10px rgba(10,10,10,0.06)',
        overflow: 'hidden',
        maxWidth: 1100,
        margin: '0 auto',
      }}
    >
      {/* browser chrome */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '11px 16px',
          background: 'var(--surface)',
          borderBottom: '1px solid var(--border-soft)',
        }}
      >
        <ChromeDot c="#d88b74" />
        <ChromeDot c="#d9be6a" />
        <ChromeDot c="#9fb27c" />
        <div
          style={{
            marginLeft: 16,
            flex: 1,
            background: 'var(--bg)',
            border: '1px solid var(--border-soft)',
            borderRadius: 6,
            padding: '3px 10px',
            fontSize: 11,
            color: 'var(--text-dim)',
            fontFamily: 'var(--sans)',
            maxWidth: 360,
          }}
        >
          🔒 civo.energy/report/m_152_acton_4829
        </div>
      </div>

      {/* two-column body */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1.55fr 1fr',
          minHeight: 440,
        }}
      >
        {/* LEFT — the report */}
        <div style={{ padding: '24px 28px' }}>
          {/* moratorium banner */}
          <div
            style={{
              background: 'var(--gold-soft, #f7efe0)',
              border: '1px solid #e2c48a',
              borderRadius: 8,
              padding: '8px 12px',
              fontSize: 11.5,
              color: 'var(--gold, #c08a3e)',
              marginBottom: 18,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontWeight: 500,
            }}
          >
            <span style={dotStyle('var(--gold, #c08a3e)')} />
            Active moratorium · battery storage · through 2026-09-12
          </div>

          <div style={eyebrowStyle}>Suitability Report</div>
          <h3 style={displayH3}>50 Nagog Park, Acton</h3>
          <div style={metaStyle}>M_152_ACTON_4829 · v1.2 · Apr 19, 2026</div>

          {/* score row */}
          <div
            style={{
              marginTop: 20,
              display: 'grid',
              gridTemplateColumns: '1.3fr 1fr 1fr 1fr',
              gap: 8,
            }}
          >
            <BigTile />
            <Tile label="Assessment" value="Conditional" tone="var(--gold, #c08a3e)" />
            <Tile label="Primary" value="Climate" tone="var(--rust)" />
            <Tile label="Type" value="Solar GM" tone="var(--sage)" />
          </div>

          {/* criteria */}
          <div
            style={{
              marginTop: 22,
              paddingTop: 16,
              borderTop: '1px solid var(--border-soft)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                justifyContent: 'space-between',
                marginBottom: 10,
              }}
            >
              <div
                style={{
                  fontFamily: "'Fraunces', Georgia, serif",
                  fontSize: 14,
                  fontWeight: 500,
                  color: 'var(--ink)',
                }}
              >
                Findings
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.08em', textTransform: 'uppercase', fontWeight: 500 }}>
                7 weighted criteria
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
              <Row name="Biodiversity" score={8.4} weight="20%" tone="good" />
              <Row name="Climate resilience" score={4.2} weight="15%" tone="warn" />
              <Row name="Carbon storage" score={6.9} weight="15%" tone="good" />
              <Row name="Grid alignment" score={7.8} weight="15%" tone="good" />
              <Row name="Burdens" score={5.1} weight="10%" tone="warn" />
              <Row name="Agriculture" score={7.1} weight="15%" tone="good" />
              <Row name="Benefits" score={6.2} weight="10%" tone="good" />
            </div>
          </div>
        </div>

        {/* RIGHT — citations panel */}
        <aside
          style={{
            background: 'var(--surface)',
            borderLeft: '1px solid var(--border-soft)',
            padding: '24px 24px',
          }}
        >
          <div style={eyebrowStyle}>Sources — 14 citations</div>
          <div
            style={{
              marginTop: 14,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}
          >
            {[
              ['225 CMR 29.05', 'Regulatory', true],
              ['MassGIS L3 Parcels', 'Spatial', true],
              ['BioMap 2020 Core', 'Spatial', true],
              ['Acton Bylaw §5.4.2', 'Municipal', true],
              ['FEMA NFHL', 'Spatial', true],
              ['310 CMR 10.55', 'Regulatory', true],
              ['MassDEP Wetlands', 'Spatial', true],
              ['EFSB 23-04 (archived)', 'Precedent', false],
            ].map(([name, kind, healthy]) => (
              <CitationRow
                key={name as string}
                name={name as string}
                kind={kind as string}
                healthy={healthy as boolean}
              />
            ))}
          </div>

          {/* mini chart */}
          <div
            style={{
              marginTop: 22,
              paddingTop: 18,
              borderTop: '1px solid var(--border-soft)',
            }}
          >
            <div style={eyebrowStyle}>Score trend · last 30 days</div>
            <svg viewBox="0 0 200 50" style={{ width: '100%', height: 50, marginTop: 10 }} preserveAspectRatio="none">
              <defs>
                <linearGradient id="heroFill" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <path
                d="M 0 36 L 14 34 L 28 32 L 42 30 L 56 29 L 70 26 L 84 24 L 98 22 L 112 20 L 126 18 L 140 17 L 154 15 L 168 13 L 182 11 L 200 10 L 200 50 L 0 50 Z"
                fill="url(#heroFill)"
              />
              <path
                d="M 0 36 L 14 34 L 28 32 L 42 30 L 56 29 L 70 26 L 84 24 L 98 22 L 112 20 L 126 18 L 140 17 L 154 15 L 168 13 L 182 11 L 200 10"
                stroke="var(--accent)"
                strokeWidth={1.4}
                fill="none"
              />
            </svg>
            <div
              className="tnum"
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginTop: 4,
                fontSize: 10,
                color: 'var(--text-dim)',
              }}
            >
              <span>Mar 20</span>
              <span style={{ color: 'var(--ink)', fontWeight: 600 }}>67 ↑ 8</span>
              <span>Apr 19</span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

// ─── atoms ─────────────────────────────────────────────────

function ChromeDot({ c }: { c: string }) {
  return (
    <span
      style={{ width: 10, height: 10, borderRadius: 999, background: c, display: 'inline-block' }}
    />
  );
}

function dotStyle(c: string): React.CSSProperties {
  return { width: 7, height: 7, borderRadius: 999, background: c, flex: 'none' };
}

const eyebrowStyle: React.CSSProperties = {
  fontSize: 10,
  letterSpacing: '0.14em',
  textTransform: 'uppercase',
  color: 'var(--accent)',
  fontWeight: 600,
};

const displayH3: React.CSSProperties = {
  fontFamily: "'Fraunces', Georgia, serif",
  fontSize: 30,
  fontWeight: 500,
  letterSpacing: '-0.022em',
  margin: '6px 0 4px',
  lineHeight: 1.02,
  color: 'var(--ink)',
};

const metaStyle: React.CSSProperties = {
  fontSize: 11.5,
  color: 'var(--text-dim)',
  fontFamily: 'var(--sans)',
  letterSpacing: '0.01em',
  fontVariantNumeric: 'tabular-nums',
};

function BigTile() {
  return (
    <div
      style={{
        background: '#f7f3ea',
        border: '1px solid var(--border)',
        borderRadius: 10,
        padding: '12px 14px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        minHeight: 86,
      }}
    >
      <div style={{ fontSize: 10, color: 'var(--text-mid)', fontWeight: 500 }}>Total score</div>
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: 4,
          fontFamily: "'Fraunces', Georgia, serif",
        }}
      >
        <span
          className="tnum"
          style={{
            fontSize: 44,
            fontWeight: 400,
            letterSpacing: '-0.032em',
            lineHeight: 1,
            color: 'var(--ink)',
          }}
        >
          67
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-mid)', marginLeft: 2 }}>/ 100</span>
      </div>
    </div>
  );
}

function Tile({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div
      style={{
        background: 'var(--bg)',
        border: '1px solid var(--border-soft)',
        borderRadius: 10,
        padding: '10px 12px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        minHeight: 86,
      }}
    >
      <div style={{ fontSize: 10, color: 'var(--text-mid)', fontWeight: 500 }}>{label}</div>
      <div
        style={{
          fontFamily: "'Fraunces', Georgia, serif",
          fontSize: 18,
          letterSpacing: '-0.015em',
          lineHeight: 1.05,
          color: 'var(--ink)',
        }}
      >
        {value}
      </div>
      <div
        style={{
          width: 26,
          height: 2,
          background: tone,
          borderRadius: 999,
        }}
      />
    </div>
  );
}

function Row({
  name,
  score,
  weight,
  tone,
}: {
  name: string;
  score: number;
  weight: string;
  tone: 'good' | 'warn' | 'bad';
}) {
  const c =
    tone === 'good' ? 'var(--good)' : tone === 'warn' ? 'var(--gold, #c08a3e)' : 'var(--bad)';
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1.5fr 34px 1fr 32px',
        alignItems: 'center',
        gap: 10,
      }}
    >
      <span style={{ fontSize: 12.5, color: 'var(--ink)', fontWeight: 500 }}>{name}</span>
      <span
        className="tnum"
        style={{
          fontSize: 11,
          color: 'var(--text-dim)',
          textAlign: 'right',
        }}
      >
        {weight}
      </span>
      <div
        style={{
          height: 4,
          background: 'var(--surface-alt)',
          borderRadius: 999,
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            width: `${score * 10}%`,
            background: c,
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

function CitationRow({
  name,
  kind,
  healthy,
}: {
  name: string;
  kind: string;
  healthy: boolean;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 8,
        padding: '7px 10px',
        background: 'var(--bg)',
        border: '1px solid var(--border-soft)',
        borderRadius: 8,
        fontSize: 11.5,
      }}
    >
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 8,
          color: 'var(--ink)',
          fontWeight: 500,
        }}
      >
        <span
          style={{
            width: 5,
            height: 5,
            borderRadius: 999,
            background: healthy ? 'var(--good)' : 'var(--gold, #c08a3e)',
            flex: 'none',
          }}
        />
        {name}
      </span>
      <span
        style={{
          fontSize: 10,
          color: 'var(--text-dim)',
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          fontWeight: 500,
        }}
      >
        {kind}
      </span>
    </div>
  );
}
