/**
 * A stylized miniature of a Civo suitability report. Floats in the hero
 * to make the product tangible — not a real report, but faithful enough
 * that it reads as "this is what you get."
 */
export default function ReportCardMock() {
  return (
    <div
      style={{
        background: 'var(--bg)',
        border: '1px solid var(--border)',
        borderRadius: 16,
        boxShadow: '0 24px 60px -20px rgba(26,26,26,0.18), 0 2px 4px rgba(26,26,26,0.04)',
        padding: '20px 22px 22px',
        width: '100%',
        maxWidth: 380,
        fontFamily: 'var(--sans)',
      }}
    >
      {/* window chrome */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          paddingBottom: 14,
          borderBottom: '1px solid var(--border-soft)',
          marginBottom: 16,
        }}
      >
        <span style={dot('#e0b8a8')} />
        <span style={dot('#e5d3a0')} />
        <span style={dot('#bfc9b2')} />
        <span
          className="tnum"
          style={{
            marginLeft: 'auto',
            fontSize: 10,
            color: 'var(--text-dim)',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
          }}
        >
          civo.energy / report / m-acton-4829
        </span>
      </div>

      <div
        style={{
          fontSize: 10,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: 'var(--accent)',
          fontWeight: 500,
          marginBottom: 8,
        }}
      >
        Suitability Report
      </div>
      <h3
        style={{
          fontFamily: "'Fraunces', Georgia, serif",
          fontSize: 22,
          fontWeight: 500,
          letterSpacing: '-0.018em',
          margin: 0,
          lineHeight: 1.1,
          color: 'var(--text)',
        }}
      >
        50 Nagog Park, Acton
      </h3>
      <div
        className="tnum"
        style={{
          fontSize: 11,
          color: 'var(--text-dim)',
          marginTop: 6,
          letterSpacing: '0.01em',
        }}
      >
        M_152_ACTON_4829 · v1.2 · Apr 19
      </div>

      {/* score tiles */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 8,
          marginTop: 14,
        }}
      >
        <div
          style={{
            background: '#f7f3ea',
            border: '1px solid var(--border)',
            borderRadius: 10,
            padding: '10px 12px',
          }}
        >
          <div style={{ fontSize: 10, color: 'var(--text-mid)', fontWeight: 500 }}>
            Total score
          </div>
          <div
            className="tnum"
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 26,
              fontWeight: 400,
              letterSpacing: '-0.025em',
              lineHeight: 1,
              marginTop: 4,
              color: 'var(--text)',
            }}
          >
            67<span style={{ fontSize: 12, color: 'var(--text-mid)' }}> / 100</span>
          </div>
        </div>
        <div
          style={{
            background: '#f7efe0',
            border: '1px solid var(--border)',
            borderRadius: 10,
            padding: '10px 12px',
          }}
        >
          <div style={{ fontSize: 10, color: 'var(--text-mid)', fontWeight: 500 }}>
            Assessment
          </div>
          <div
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 20,
              fontWeight: 400,
              letterSpacing: '-0.015em',
              lineHeight: 1.1,
              marginTop: 4,
              color: 'var(--text)',
            }}
          >
            Conditional
          </div>
        </div>
      </div>

      {/* criteria rows */}
      <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <CriterionRow name="Biodiversity" score={8.4} weight={0.2} tone="good" />
        <CriterionRow name="Climate resilience" score={4.2} weight={0.15} tone="warn" />
        <CriterionRow name="Agriculture" score={7.1} weight={0.15} tone="good" />
      </div>

      {/* citation chips */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 5,
          marginTop: 16,
          paddingTop: 14,
          borderTop: '1px solid var(--border-soft)',
        }}
      >
        <Chip>MassGIS L3</Chip>
        <Chip>225 CMR 29.05</Chip>
        <Chip>BioMap 2020</Chip>
        <Chip>Acton §5.4.2</Chip>
      </div>
    </div>
  );
}

function dot(color: string): React.CSSProperties {
  return {
    width: 9,
    height: 9,
    borderRadius: 999,
    background: color,
    display: 'inline-block',
  };
}

function CriterionRow({
  name,
  score,
  tone,
}: {
  name: string;
  score: number;
  weight: number;
  tone: 'good' | 'warn' | 'bad';
}) {
  const barColor =
    tone === 'good' ? 'var(--good)' : tone === 'warn' ? 'var(--gold, #c08a3e)' : 'var(--bad)';
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 60px 30px', alignItems: 'center', gap: 10 }}>
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
            right: 'auto',
            width: `${score * 10}%`,
            background: barColor,
            borderRadius: 999,
          }}
        />
      </div>
      <span
        className="tnum"
        style={{
          fontSize: 11,
          color: 'var(--text-mid)',
          textAlign: 'right',
        }}
      >
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
        padding: '3px 8px',
        background: 'var(--accent-soft)',
        color: 'var(--accent)',
        borderRadius: 999,
        fontWeight: 500,
        letterSpacing: '0.01em',
      }}
    >
      {children}
    </span>
  );
}
