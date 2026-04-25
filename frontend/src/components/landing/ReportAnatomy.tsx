/**
 * "Anatomy of a report" — a larger annotated mock showing what Civo's
 * suitability report actually looks like, with dashed leader lines out
 * to short editorial captions explaining specific features.
 */
export default function ReportAnatomy() {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 520px 1fr',
        alignItems: 'start',
        gap: 48,
        position: 'relative',
      }}
    >
      {/* LEFT annotations */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 68,
          paddingTop: 60,
          paddingRight: 16,
          textAlign: 'right',
        }}
      >
        <Annotation
          title="One clear verdict"
          body="Suitable · Conditional · Constrained. Three buckets, derived from the statute — no invented rubric."
        />
        <Annotation
          title="Limiting factor, surfaced"
          body="The lowest-scoring criterion is named at the top. The rest of the report explains why — and what to do about it."
        />
        <Annotation
          title="Every claim, cited"
          body="Every score points to MassGIS, a statute, or a filing. Dead URLs auto-fall back to the Wayback archive."
        />
      </div>

      {/* CENTER mock */}
      <div style={{ position: 'relative' }}>
        <AnatomyMock />
      </div>

      {/* RIGHT annotations */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 68,
          paddingTop: 40,
          paddingLeft: 16,
        }}
      >
        <Annotation
          title="Active moratoria"
          body="If the town has paused a project type, Civo flags the dates and the source — with a note on AG enforceability."
          leaderFromLeft
        />
        <Annotation
          title="Mitigation, grounded"
          body="Cost ranges come from observed precedents in this town. HCA triggered? We tell you, and cite the filings we saw it in."
          leaderFromLeft
        />
        <Annotation
          title="PDF in one keystroke"
          body="Sidebar + topbar strip on print. The report — not the app — is what makes it into your client folder."
          leaderFromLeft
        />
      </div>
    </div>
  );
}

function Annotation({
  title,
  body,
  leaderFromLeft,
}: {
  title: string;
  body: string;
  leaderFromLeft?: boolean;
}) {
  return (
    <div style={{ maxWidth: 260, position: 'relative' }}>
      {/* small number tick */}
      <div
        style={{
          width: 24,
          height: 1,
          background: 'var(--accent)',
          marginBottom: 12,
          marginLeft: leaderFromLeft ? 0 : 'auto',
        }}
      />
      <h4
        style={{
          fontFamily: "'Fraunces', Georgia, serif",
          fontSize: 20,
          fontWeight: 500,
          letterSpacing: '-0.012em',
          margin: 0,
          color: 'var(--text)',
          lineHeight: 1.2,
        }}
      >
        {title}
      </h4>
      <p
        style={{
          fontSize: 14,
          lineHeight: 1.6,
          color: 'var(--text-mid)',
          margin: '8px 0 0',
        }}
      >
        {body}
      </p>
    </div>
  );
}

// The actual mock — a fuller report rendering than the hero card.
function AnatomyMock() {
  return (
    <div
      style={{
        background: 'var(--bg)',
        border: '1px solid var(--border)',
        borderRadius: 18,
        boxShadow: '0 30px 80px -30px rgba(26,26,26,0.22), 0 2px 4px rgba(26,26,26,0.05)',
        overflow: 'hidden',
      }}
    >
      {/* window chrome */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '12px 16px',
          background: 'var(--surface)',
          borderBottom: '1px solid var(--border-soft)',
        }}
      >
        <span style={chromeDot('#e0b8a8')} />
        <span style={chromeDot('#e5d3a0')} />
        <span style={chromeDot('#bfc9b2')} />
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

      <div style={{ padding: '24px 26px' }}>
        {/* moratorium banner */}
        <div
          style={{
            background: 'var(--gold-soft, #f7efe0)',
            border: '1px solid var(--gold, #c08a3e)',
            borderRadius: 10,
            padding: '10px 14px',
            fontSize: 12,
            color: 'var(--gold, #c08a3e)',
            marginBottom: 18,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span
            aria-hidden="true"
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: 'var(--gold, #c08a3e)',
              flex: 'none',
            }}
          />
          <span style={{ fontWeight: 600 }}>Active moratorium</span>
          <span style={{ color: 'var(--text-mid)' }}>
            battery storage · through 2026-09-12
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
            fontSize: 28,
            fontWeight: 500,
            letterSpacing: '-0.02em',
            margin: 0,
            lineHeight: 1.05,
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
            marginTop: 8,
          }}
        >
          M_152_ACTON_4829 · v1.2 · Apr 19, 2026
        </div>

        {/* stat tiles */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 8,
            marginTop: 16,
          }}
        >
          <MockTile label="Total score" value="67" suffix="/ 100" bg="#f7f3ea" />
          <MockTile label="Assessment" value="Conditional" bg="#eef0ee" />
          <MockTile label="Primary" value="Climate" bg="#e8ece2" />
          <MockTile label="Type" value="Solar GM" bg="#f3e7df" />
        </div>

        {/* criteria */}
        <div
          style={{
            marginTop: 20,
            paddingTop: 18,
            borderTop: '1px solid var(--border-soft)',
          }}
        >
          <div
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 14,
              fontWeight: 500,
              marginBottom: 12,
              color: 'var(--text)',
            }}
          >
            Findings
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <CRow name="Biodiversity" weight="20%" score={8.4} tone="good" />
            <CRow name="Climate resilience" weight="15%" score={4.2} tone="warn" />
            <CRow name="Carbon storage" weight="15%" score={6.9} tone="good" />
            <CRow name="Grid alignment" weight="15%" score={7.8} tone="good" />
            <CRow name="Burdens" weight="10%" score={5.1} tone="warn" />
            <CRow name="Agriculture" weight="15%" score={7.1} tone="good" />
          </div>
        </div>

        {/* citations */}
        <div
          style={{
            marginTop: 18,
            paddingTop: 16,
            borderTop: '1px solid var(--border-soft)',
            display: 'flex',
            flexWrap: 'wrap',
            gap: 6,
          }}
        >
          <MockCite active>225 CMR 29.05</MockCite>
          <MockCite active>MassGIS L3</MockCite>
          <MockCite active>BioMap 2020</MockCite>
          <MockCite active>FEMA NFHL</MockCite>
          <MockCite active>Acton §5.4.2</MockCite>
          <MockCite>EFSB 23-04 · archived</MockCite>
        </div>
      </div>
    </div>
  );
}

function chromeDot(color: string): React.CSSProperties {
  return {
    width: 10,
    height: 10,
    borderRadius: 999,
    background: color,
    display: 'inline-block',
  };
}

function MockTile({
  label,
  value,
  suffix,
  bg,
}: {
  label: string;
  value: string;
  suffix?: string;
  bg: string;
}) {
  return (
    <div
      style={{
        background: bg,
        border: '1px solid var(--border)',
        borderRadius: 10,
        padding: '10px 12px',
        minHeight: 66,
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
          fontSize: 22,
          fontWeight: 400,
          letterSpacing: '-0.022em',
          lineHeight: 1,
          marginTop: 6,
          color: 'var(--text)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {value}
        {suffix && (
          <span style={{ fontSize: 10, color: 'var(--text-mid)' }}>{' '}{suffix}</span>
        )}
      </div>
    </div>
  );
}

function CRow({
  name,
  weight,
  score,
  tone,
}: {
  name: string;
  weight: string;
  score: number;
  tone: 'good' | 'warn' | 'bad';
}) {
  const color =
    tone === 'good' ? 'var(--good)' : tone === 'warn' ? 'var(--gold, #c08a3e)' : 'var(--bad)';
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1.4fr 40px 1fr 32px',
        alignItems: 'center',
        gap: 12,
      }}
    >
      <span style={{ fontSize: 12.5, color: 'var(--text)', fontWeight: 500 }}>{name}</span>
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
            background: color,
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

function MockCite({ children, active }: { children: React.ReactNode; active?: boolean }) {
  return (
    <span
      style={{
        fontSize: 10.5,
        padding: '3px 9px',
        background: active ? 'var(--accent-soft)' : 'var(--surface-alt)',
        color: active ? 'var(--accent)' : 'var(--text-dim)',
        borderRadius: 999,
        fontWeight: 500,
        letterSpacing: '0.01em',
        textDecoration: active ? 'none' : 'none',
        fontStyle: active ? 'normal' : 'italic',
      }}
    >
      {children}
    </span>
  );
}
