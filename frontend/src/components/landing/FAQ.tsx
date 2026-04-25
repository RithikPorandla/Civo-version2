import { useState } from 'react';

const ITEMS: Array<{ q: string; a: string }> = [
  {
    q: 'How accurate is the scoring?',
    a: "225 CMR 29.00 is the scoring model — the weights, exemptions, and buckets come directly from the statute. Where a criterion depends on interpretation (town-level bylaws, Article 97 classification), Civo annotates the score with an explicit confidence value and cites the source filing. We'd rather tell you \"data confidence: 0.72\" than fake certainty.",
  },
  {
    q: "What if a town isn't yet covered?",
    a: "The spatial corpus — 206,352 parcels — covers all of Massachusetts, so basic scoring works statewide. What takes time per town is the bylaw ingest: zoning maps, ordinances, setback tables. If we haven't ingested a town, the report labels the municipal section \"not yet indexed\" rather than guessing. We're adding towns continuously; ping us to prioritize yours.",
  },
  {
    q: 'What happens when a source URL goes dead?',
    a: "Citations are checked nightly against their HTTP status. When a source 404s or moves, Civo auto-falls back to the most recent Wayback Machine snapshot — the chip shows \"archived\" so you know it's from the Wayback cache, not the live URL. Dead links that aren't archived get visually marked so you can flag them.",
  },
  {
    q: 'Can I export a report as a PDF?',
    a: 'Every report prints cleanly to PDF via Cmd/Ctrl-P. The sidebar, top bar, and interactive chrome strip out in the print stylesheet so you get just the cited document — the thing that goes into a client folder or a permit application.',
  },
  {
    q: 'Is Civo a replacement for a consultant?',
    a: "No. Civo is a tool consultants use — it handles the hours of data-gathering (MassGIS layers, town bylaws, precedent filings) so the consultant's time goes to judgment, narrative, and client relationship. The product was designed alongside a working MA permitting firm for exactly this reason.",
  },
  {
    q: 'Who is Civo built for?',
    a: 'MA permitting professionals — consultants, municipal planners, and development firms working in the Commonwealth. The product assumes the reader knows what 225 CMR 29 is and doesn\'t explain the basics. If you\'re evaluating solar, BESS, substation, or transmission projects in MA, Civo is for you.',
  },
];

export default function FAQ() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        borderTop: '1px solid var(--border-soft)',
      }}
    >
      {ITEMS.map((it, i) => {
        const isOpen = open === i;
        return (
          <div
            key={i}
            style={{
              borderBottom: '1px solid var(--border-soft)',
            }}
          >
            <button
              onClick={() => setOpen(isOpen ? null : i)}
              style={{
                width: '100%',
                background: 'transparent',
                border: 'none',
                padding: '24px 0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                cursor: 'pointer',
                gap: 24,
                textAlign: 'left',
                fontFamily: 'inherit',
              }}
            >
              <span
                style={{
                  fontFamily: "'Fraunces', Georgia, serif",
                  fontSize: 'clamp(18px, 2vw, 24px)',
                  fontWeight: 500,
                  letterSpacing: '-0.012em',
                  color: 'var(--text)',
                  lineHeight: 1.25,
                }}
              >
                {it.q}
              </span>
              <span
                aria-hidden="true"
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 999,
                  border: '1px solid var(--border)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flex: 'none',
                  color: 'var(--text-mid)',
                  fontSize: 18,
                  transform: isOpen ? 'rotate(45deg)' : 'none',
                  transition: 'transform 180ms ease, background 150ms ease',
                  background: isOpen ? 'var(--surface)' : 'transparent',
                }}
              >
                +
              </span>
            </button>
            <div
              style={{
                maxHeight: isOpen ? 400 : 0,
                opacity: isOpen ? 1 : 0,
                overflow: 'hidden',
                transition: 'max-height 280ms ease, opacity 200ms ease, padding 200ms ease',
                paddingBottom: isOpen ? 26 : 0,
              }}
            >
              <p
                style={{
                  fontSize: 15,
                  lineHeight: 1.7,
                  color: 'var(--text-mid)',
                  margin: 0,
                  maxWidth: 720,
                }}
              >
                {it.a}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
