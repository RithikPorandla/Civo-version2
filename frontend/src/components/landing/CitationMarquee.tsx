/**
 * Horizontal auto-scrolling band of real statute + dataset citations.
 * Signals "this is a lot of sources" without a wall of text. Pauses
 * on hover so a curious visitor can read what's actually there.
 */

const CITATIONS = [
  '225 CMR 29.00',
  'G.L. c.40A §3',
  'MassGIS L3 Parcels',
  'BioMap 2020',
  'NHESP Priority',
  'FEMA NFHL',
  'MassDEP Wetlands',
  '310 CMR 10.55',
  'DOER Model Bylaw',
  'EFSB Docket',
  'G.L. c.164 §69J',
  'MassGIS LU/LC 2016',
  'NFPA 855',
  '225 CMR 29.07(1)',
  'Chapter 61A',
  'MA AG Moratorium Rulings',
  'SMART 3.0',
  'USDA Prime Farmland',
  'ResilientMass',
  'MMPC Precedents',
];

export default function CitationMarquee() {
  // Duplicate the list so the scroll loop reads seamless.
  const items = [...CITATIONS, ...CITATIONS];

  return (
    <section
      aria-label="Data sources and citations"
      style={{
        borderTop: '1px solid var(--border-soft)',
        borderBottom: '1px solid var(--border-soft)',
        background: 'var(--surface)',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* feathered edges so chips fade in/out instead of hard-cutting */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'linear-gradient(to right, var(--surface) 0%, transparent 8%, transparent 92%, var(--surface) 100%)',
          zIndex: 2,
        }}
      />
      <div
        className="marquee-track"
        style={{
          display: 'flex',
          gap: 14,
          padding: '20px 0',
          width: 'max-content',
          animation: 'marquee 60s linear infinite',
        }}
      >
        {items.map((c, i) => (
          <span
            key={i}
            style={{
              fontSize: 12.5,
              letterSpacing: '0.03em',
              fontWeight: 500,
              color: 'var(--text)',
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 999,
              padding: '7px 14px',
              whiteSpace: 'nowrap',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <span
              aria-hidden="true"
              style={{
                width: 4,
                height: 4,
                borderRadius: '50%',
                background: 'var(--accent)',
                flex: 'none',
              }}
            />
            {c}
          </span>
        ))}
      </div>
      <style>{`
        @keyframes marquee {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
        .marquee-track:hover { animation-play-state: paused; }
      `}</style>
    </section>
  );
}
