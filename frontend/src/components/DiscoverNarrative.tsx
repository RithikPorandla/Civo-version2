interface Citation {
  claim: string;
  source: string;
}

interface Props {
  narrative: string;
  citations: Citation[];
}

export function DiscoverNarrative({ narrative, citations }: Props) {
  return (
    <div
      style={{
        background: 'var(--surface-alt)',
        borderLeft: '3px solid var(--accent)',
        borderRadius: '0 10px 10px 0',
        padding: '14px 16px',
        margin: '0 0 2px',
      }}
    >
      <div className="eyebrow" style={{ marginBottom: 8 }}>
        Analysis
      </div>
      <p
        style={{
          fontSize: 13.5,
          lineHeight: 1.65,
          color: 'var(--text)',
          margin: 0,
        }}
      >
        {narrative}
      </p>
      {citations.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 10 }}>
          {citations.map((c, i) => (
            <span
              key={i}
              title={c.source}
              style={{
                fontSize: 10,
                fontWeight: 500,
                padding: '3px 8px',
                borderRadius: 999,
                background: 'var(--surface-warm)',
                border: '1px solid var(--border)',
                color: 'var(--accent)',
                letterSpacing: '0.01em',
                cursor: 'default',
              }}
            >
              {c.source}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
