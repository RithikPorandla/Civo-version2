import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import SiteHeader from '../components/SiteHeader';
import BrandMark from '../components/BrandMark';
import HeroDashboard from '../components/landing/HeroDashboard';

/**
 * Civo landing — data-dense editorial in a dark-espresso + black + white
 * palette. Keeps to three pages (/, /score, /report/:id).
 *
 *   1. Hero — bold black display, italic serif accent, pill input, live ticker
 *   2. Sources strip — named MA data providers
 *   3. Numbered feature cards (01–04)
 *   4. Results — four big data stats
 *   5. Quote pull
 *   6. Closing CTA (dark espresso)
 *   7. Footer
 */
export default function Landing() {
  return (
    <div style={{ background: 'var(--bg)', minHeight: '100vh' }}>
      <SiteHeader />
      <LiveTicker />
      <Hero />
      <SourcesStrip />
      <NumberedFeatures />
      <ResultsStats />
      <QuoteBlock />
      <BigCta />
      <Footer />
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────
// Live ticker — sits right below the nav
// ──────────────────────────────────────────────────────────────────
function LiveTicker() {
  const events = [
    { at: '4 min ago', addr: '50 Nagog Park, Acton', score: 67, tag: 'Conditional' },
    { at: '12 min ago', addr: 'Kendall Square, Cambridge', score: 92, tag: 'Suitable' },
    { at: '28 min ago', addr: 'East Freetown', score: 35, tag: 'Constrained' },
    { at: '41 min ago', addr: '180 Pleasant, Ashland', score: 76, tag: 'Conditional' },
    { at: '1 hr ago', addr: 'Whately town center', score: 84, tag: 'Suitable' },
    { at: '2 hr ago', addr: '8 Mill Pond Dr, Framingham', score: 71, tag: 'Conditional' },
  ];
  const doubled = [...events, ...events];

  return (
    <div
      aria-label="Recent scoring activity"
      style={{
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border-soft)',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'linear-gradient(to right, var(--surface) 0%, transparent 6%, transparent 94%, var(--surface) 100%)',
          zIndex: 2,
        }}
      />
      <div
        style={{
          display: 'flex',
          gap: 40,
          padding: '12px 0',
          width: 'max-content',
          animation: 'tickerScroll 70s linear infinite',
        }}
        className="ticker-track"
      >
        {doubled.map((e, i) => {
          const tone =
            e.tag === 'Suitable'
              ? 'var(--good)'
              : e.tag === 'Conditional'
              ? 'var(--gold, #c08a3e)'
              : 'var(--rust)';
          return (
            <span
              key={i}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 10,
                fontSize: 12,
                color: 'var(--text-mid)',
                fontFamily: 'var(--sans)',
                whiteSpace: 'nowrap',
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: 999,
                  background: tone,
                  flex: 'none',
                }}
              />
              <span className="tnum" style={{ color: 'var(--text-dim)', letterSpacing: '0.04em' }}>
                {e.at}
              </span>
              <span style={{ color: 'var(--ink)', fontWeight: 500 }}>{e.addr}</span>
              <span
                className="tnum"
                style={{
                  color: 'var(--ink)',
                  fontWeight: 600,
                  fontFamily: "'Fraunces', Georgia, serif",
                  fontSize: 14,
                }}
              >
                · {e.score}
              </span>
              <span
                style={{
                  fontSize: 10,
                  color: tone,
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                  fontWeight: 600,
                }}
              >
                {e.tag}
              </span>
            </span>
          );
        })}
      </div>
      <style>{`
        @keyframes tickerScroll {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
        .ticker-track:hover { animation-play-state: paused; }
      `}</style>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────
// Hero
// ──────────────────────────────────────────────────────────────────
function Hero() {
  const [address, setAddress] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const nav = useNavigate();

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!address.trim()) return;
    setErr(null);
    setBusy(true);
    try {
      const env = await api.score(address);
      nav(`/report/${env.report_id}`);
    } catch (e: unknown) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      style={{
        position: 'relative',
        padding: '64px 32px 0',
        textAlign: 'center',
        overflow: 'hidden',
      }}
    >
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: 'radial-gradient(rgba(90,58,31,0.10) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
          maskImage: 'radial-gradient(ellipse 80% 55% at 50% 25%, #000 20%, transparent 100%)',
          WebkitMaskImage:
            'radial-gradient(ellipse 80% 55% at 50% 25%, #000 20%, transparent 100%)',
          pointerEvents: 'none',
        }}
      />

      <div style={{ position: 'relative', zIndex: 3, maxWidth: 1100, margin: '0 auto' }}>
        <h1
          style={{
            fontFamily: 'var(--sans)',
            fontSize: 'clamp(56px, 8.4vw, 132px)',
            fontWeight: 800,
            letterSpacing: '-0.045em',
            lineHeight: 0.92,
            margin: 0,
            color: 'var(--ink)',
            textWrap: 'balance',
          }}
        >
          Permitting.{' '}
          <span
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontStyle: 'italic',
              fontWeight: 400,
              color: 'var(--accent)',
            }}
          >
            Every claim
            <br />
            cited
          </span>
          <span style={{ color: 'var(--accent)' }}>.</span>
        </h1>

        <p
          style={{
            fontSize: 19,
            lineHeight: 1.5,
            color: 'var(--text-mid)',
            maxWidth: 640,
            margin: '32px auto 40px',
          }}
        >
          Civo scores any Massachusetts parcel against 225 CMR 29 in seconds. Every number
          traces to a source you can open — a statute, a filing, a MassGIS layer.
        </p>

        <form
          onSubmit={submit}
          style={{
            display: 'flex',
            alignItems: 'stretch',
            gap: 10,
            background: 'var(--bg)',
            border: '1px solid var(--border)',
            borderRadius: 999,
            padding: '6px 6px 6px 22px',
            maxWidth: 620,
            margin: '0 auto',
            boxShadow:
              '0 10px 30px -10px rgba(10,10,10,0.14), 0 1px 2px rgba(10,10,10,0.04)',
          }}
        >
          <input
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="Paste any Massachusetts address"
            style={{
              flex: 1,
              background: 'transparent',
              border: 0,
              outline: 'none',
              fontSize: 15,
              padding: '14px 0',
              color: 'var(--ink)',
              fontFamily: 'inherit',
            }}
          />
          <button
            disabled={busy}
            style={{
              background: 'var(--ink)',
              color: 'var(--bg)',
              border: 0,
              borderRadius: 999,
              padding: '0 22px',
              fontSize: 14,
              fontWeight: 600,
              cursor: busy ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              transition: 'filter 150ms ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.filter = 'brightness(1.15)')}
            onMouseLeave={(e) => (e.currentTarget.style.filter = 'none')}
          >
            {busy ? 'Scoring…' : 'Score site'}
            <span>→</span>
          </button>
        </form>
        {err && (
          <div style={{ color: 'var(--bad)', fontSize: 13, marginTop: 10 }}>{err}</div>
        )}

        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 10,
            marginTop: 18,
            fontSize: 12,
            color: 'var(--text-dim)',
            flexWrap: 'wrap',
            justifyContent: 'center',
          }}
        >
          <span>Try:</span>
          {['Kendall Square, Cambridge', '50 Nagog Park, Acton', 'East Freetown'].map((s) => (
            <button
              key={s}
              onClick={() => setAddress(s + ', MA')}
              style={{
                background: 'transparent',
                border: '1px solid var(--border-soft)',
                color: 'var(--text-mid)',
                padding: '4px 10px',
                borderRadius: 999,
                fontSize: 12,
                cursor: 'pointer',
                fontFamily: 'inherit',
                transition: 'background 120ms ease, border-color 120ms ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--surface)';
                e.currentTarget.style.borderColor = 'var(--border)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.borderColor = 'var(--border-soft)';
              }}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Hero product dashboard */}
        <div style={{ marginTop: 72, marginBottom: -120, position: 'relative' }}>
          <HeroDashboard />
          <div
            aria-hidden="true"
            style={{
              position: 'absolute',
              bottom: -30,
              left: '8%',
              right: '8%',
              height: 80,
              background:
                'radial-gradient(ellipse at center, rgba(90,58,31,0.22), transparent 70%)',
              filter: 'blur(20px)',
              zIndex: -1,
            }}
          />
        </div>
      </div>
    </section>
  );
}

// ──────────────────────────────────────────────────────────────────
// Sources strip — named MA data providers
// ──────────────────────────────────────────────────────────────────
function SourcesStrip() {
  return (
    <section
      style={{
        padding: '180px 32px 60px',
        textAlign: 'center',
      }}
    >
      <div style={{ maxWidth: 1080, margin: '0 auto' }}>
        <div
          style={{
            fontSize: 11,
            color: 'var(--text-dim)',
            letterSpacing: '0.18em',
            textTransform: 'uppercase',
            fontWeight: 600,
            marginBottom: 24,
          }}
        >
          Built on public data from
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 24,
            flexWrap: 'wrap',
          }}
        >
          {['MassGIS', 'MassDEP', 'DOER', 'FEMA', 'NFPA', 'EFSB', 'MA Attorney General'].map(
            (s) => (
              <div
                key={s}
                style={{
                  fontFamily: "'Fraunces', Georgia, serif",
                  fontSize: 22,
                  fontWeight: 500,
                  letterSpacing: '-0.015em',
                  color: 'var(--ink)',
                  opacity: 0.78,
                }}
              >
                {s}
              </div>
            )
          )}
        </div>
      </div>
    </section>
  );
}

// ──────────────────────────────────────────────────────────────────
// Numbered feature cards — 01 / 02 / 03 / 04
// ──────────────────────────────────────────────────────────────────
function NumberedFeatures() {
  const items = [
    {
      num: '01',
      title: 'Scored to the statute',
      body: '225 CMR 29 is the model. Weights, exemptions, and buckets come from the regulation — not a PM\'s rubric.',
      stat: '7 weighted criteria',
    },
    {
      num: '02',
      title: 'Cited end-to-end',
      body: 'Every number points at MassGIS, a filing, or a statute. Dead URLs auto-fall back to the Wayback archive.',
      stat: '14+ sources / report',
    },
    {
      num: '03',
      title: 'Moratoria & HCA',
      body: 'Active moratoria surface with dates + source. HCA triggers and mitigation costs grounded in observed precedents.',
      stat: 'Flagged in real time',
    },
    {
      num: '04',
      title: 'Print-ready',
      body: 'One document. Export to PDF in a keystroke — sidebar and chrome strip automatically for the client folder.',
      stat: '⌘P → deliverable',
    },
  ];

  return (
    <section
      style={{
        padding: '100px 32px 120px',
        borderTop: '1px solid var(--border-soft)',
      }}
    >
      <div style={{ maxWidth: 1280, margin: '0 auto' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 56,
            alignItems: 'end',
            marginBottom: 56,
          }}
        >
          <div>
            <div
              style={{
                fontSize: 11,
                color: 'var(--accent)',
                letterSpacing: '0.18em',
                textTransform: 'uppercase',
                fontWeight: 600,
                marginBottom: 18,
              }}
            >
              The product
            </div>
            <h2
              style={{
                fontFamily: 'var(--sans)',
                fontSize: 'clamp(40px, 5.2vw, 72px)',
                fontWeight: 800,
                letterSpacing: '-0.035em',
                lineHeight: 0.96,
                margin: 0,
                color: 'var(--ink)',
              }}
            >
              Four things the{' '}
              <span
                style={{
                  fontFamily: "'Fraunces', Georgia, serif",
                  fontStyle: 'italic',
                  fontWeight: 400,
                  color: 'var(--accent)',
                }}
              >
                report always does
              </span>
              .
            </h2>
          </div>
          <p
            style={{
              fontSize: 16,
              lineHeight: 1.65,
              color: 'var(--text-mid)',
              maxWidth: 420,
              margin: 0,
            }}
          >
            Not a dashboard. A single cited document per parcel — forward it, print it, follow a
            source straight out of it.
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 1,
            background: 'var(--border-soft)',
            border: '1px solid var(--border-soft)',
            borderRadius: 20,
            overflow: 'hidden',
          }}
        >
          {items.map((it) => (
            <article
              key={it.num}
              style={{
                background: 'var(--bg)',
                padding: '36px 28px 32px',
                display: 'flex',
                flexDirection: 'column',
                gap: 16,
                minHeight: 320,
              }}
            >
              <div
                className="tnum"
                style={{
                  fontFamily: "'Fraunces', Georgia, serif",
                  fontSize: 52,
                  fontWeight: 400,
                  letterSpacing: '-0.028em',
                  lineHeight: 1,
                  color: 'var(--accent)',
                }}
              >
                {it.num}
              </div>
              <h3
                style={{
                  fontFamily: 'var(--sans)',
                  fontSize: 20,
                  fontWeight: 700,
                  letterSpacing: '-0.015em',
                  margin: 0,
                  lineHeight: 1.2,
                  color: 'var(--ink)',
                }}
              >
                {it.title}
              </h3>
              <p
                style={{
                  fontSize: 14,
                  lineHeight: 1.65,
                  color: 'var(--text-mid)',
                  margin: 0,
                  flex: 1,
                }}
              >
                {it.body}
              </p>
              <div
                style={{
                  paddingTop: 14,
                  borderTop: '1px solid var(--border-soft)',
                  fontSize: 11,
                  color: 'var(--accent)',
                  fontWeight: 600,
                  letterSpacing: '0.05em',
                  textTransform: 'uppercase',
                }}
              >
                {it.stat}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

// ──────────────────────────────────────────────────────────────────
// Results — big stats block
// ──────────────────────────────────────────────────────────────────
function ResultsStats() {
  const stats = [
    {
      value: '206,352',
      label: 'parcels indexed statewide',
      sparkline: 'M 0 28 L 20 26 L 40 24 L 60 22 L 80 20 L 100 17 L 120 15 L 140 12 L 160 10 L 180 7 L 200 4',
    },
    {
      value: '56',
      label: 'ESMP projects across 3 utilities',
      sparkline: 'M 0 14 L 25 14 L 50 14 L 75 14 L 100 14 L 125 14 L 150 14 L 175 14 L 200 14',
    },
    {
      value: '5',
      label: 'towns fully ingested',
      sparkline: 'M 0 28 L 40 26 L 80 22 L 120 16 L 160 10 L 200 4',
    },
    {
      value: '< 10s',
      label: 'report latency, address → verdict',
      sparkline: 'M 0 10 L 25 12 L 50 11 L 75 13 L 100 10 L 125 12 L 150 9 L 175 11 L 200 10',
    },
  ];

  return (
    <section
      style={{
        padding: '120px 32px',
        background: 'var(--surface)',
        borderTop: '1px solid var(--border-soft)',
        borderBottom: '1px solid var(--border-soft)',
      }}
    >
      <div style={{ maxWidth: 1280, margin: '0 auto' }}>
        <div style={{ marginBottom: 56, maxWidth: 820 }}>
          <div
            style={{
              fontSize: 11,
              color: 'var(--accent)',
              letterSpacing: '0.18em',
              textTransform: 'uppercase',
              fontWeight: 600,
              marginBottom: 18,
            }}
          >
            Coverage — April 2026
          </div>
          <h2
            style={{
              fontFamily: 'var(--sans)',
              fontSize: 'clamp(40px, 5.2vw, 72px)',
              fontWeight: 800,
              letterSpacing: '-0.035em',
              lineHeight: 0.96,
              margin: 0,
              color: 'var(--ink)',
            }}
          >
            The work,{' '}
            <span
              style={{
                fontFamily: "'Fraunces', Georgia, serif",
                fontStyle: 'italic',
                fontWeight: 400,
                color: 'var(--accent)',
              }}
            >
              in numbers
            </span>
            .
          </h2>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 1,
            background: 'var(--border-soft)',
            border: '1px solid var(--border-soft)',
            borderRadius: 20,
            overflow: 'hidden',
          }}
        >
          {stats.map((s) => (
            <div
              key={s.label}
              style={{
                background: 'var(--bg)',
                padding: '32px 28px 28px',
                display: 'flex',
                flexDirection: 'column',
                gap: 20,
                minHeight: 240,
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div
                  className="tnum"
                  style={{
                    fontFamily: "'Fraunces', Georgia, serif",
                    fontSize: 64,
                    fontWeight: 400,
                    letterSpacing: '-0.038em',
                    lineHeight: 1,
                    color: 'var(--ink)',
                  }}
                >
                  {s.value}
                </div>
                <div
                  style={{
                    marginTop: 12,
                    fontSize: 13,
                    color: 'var(--text-mid)',
                    lineHeight: 1.5,
                    maxWidth: 200,
                  }}
                >
                  {s.label}
                </div>
              </div>
              <svg
                viewBox="0 0 200 32"
                preserveAspectRatio="none"
                style={{ width: '100%', height: 32, display: 'block' }}
                aria-hidden="true"
              >
                <path
                  d={s.sparkline}
                  stroke="var(--accent)"
                  strokeWidth={1.4}
                  fill="none"
                  opacity={0.85}
                />
              </svg>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ──────────────────────────────────────────────────────────────────
// Quote block
// ──────────────────────────────────────────────────────────────────
function QuoteBlock() {
  return (
    <section
      style={{
        padding: '140px 32px',
        textAlign: 'center',
      }}
    >
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        <div
          style={{
            fontSize: 11,
            color: 'var(--accent)',
            letterSpacing: '0.18em',
            textTransform: 'uppercase',
            fontWeight: 600,
            marginBottom: 26,
          }}
        >
          How Civo sounds
        </div>
        <blockquote
          style={{
            fontFamily: "'Fraunces', Georgia, serif",
            fontSize: 'clamp(28px, 3.6vw, 48px)',
            fontWeight: 400,
            letterSpacing: '-0.022em',
            lineHeight: 1.2,
            margin: 0,
            color: 'var(--ink)',
            textWrap: 'balance',
          }}
        >
          A senior consultant briefing a client.{' '}
          <em style={{ fontStyle: 'italic', color: 'var(--accent)' }}>
            Concise, cited, comfortable saying what the sources don't yet say.
          </em>{' '}
          Never oversells certainty — "data confidence: 0.72" beats a fake guarantee every time.
        </blockquote>
        <div
          style={{
            marginTop: 36,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 10,
            fontSize: 12,
            color: 'var(--text-dim)',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
          }}
        >
          <span style={{ width: 24, height: 1, background: 'var(--accent)' }} />
          Civo voice · design doc
        </div>
      </div>
    </section>
  );
}

// ──────────────────────────────────────────────────────────────────
// Big CTA — dark espresso contrast
// ──────────────────────────────────────────────────────────────────
function BigCta() {
  return (
    <section
      style={{
        padding: '140px 32px',
        background: 'var(--accent-dark)',
        color: '#faf8f3',
        textAlign: 'center',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage:
            'radial-gradient(rgba(250,248,243,0.08) 1px, transparent 1px)',
          backgroundSize: '28px 28px',
          maskImage: 'radial-gradient(ellipse 70% 60% at 50% 50%, #000 30%, transparent 100%)',
          WebkitMaskImage:
            'radial-gradient(ellipse 70% 60% at 50% 50%, #000 30%, transparent 100%)',
          pointerEvents: 'none',
        }}
      />
      <div style={{ position: 'relative', zIndex: 3, maxWidth: 900, margin: '0 auto' }}>
        <h2
          style={{
            fontFamily: 'var(--sans)',
            fontSize: 'clamp(48px, 7vw, 112px)',
            fontWeight: 800,
            letterSpacing: '-0.042em',
            lineHeight: 0.96,
            margin: 0,
            color: '#faf8f3',
          }}
        >
          The parcel is the{' '}
          <span
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontStyle: 'italic',
              fontWeight: 400,
              color: '#d9b88a',
            }}
          >
            unit of truth
          </span>
          .
        </h2>
        <p
          style={{
            fontSize: 17,
            lineHeight: 1.6,
            color: 'rgba(250,248,243,0.72)',
            maxWidth: 540,
            margin: '32px auto 40px',
          }}
        >
          Score a site in under ten seconds. Open the report. Follow a citation. That's the
          whole loop — and the whole product.
        </p>
        <Link
          to="/score"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 10,
            background: '#faf8f3',
            color: 'var(--accent-dark)',
            padding: '14px 26px',
            borderRadius: 999,
            fontSize: 14,
            fontWeight: 600,
            textDecoration: 'none',
            transition: 'transform 150ms ease, filter 150ms ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-1px)';
            e.currentTarget.style.filter = 'brightness(1.02)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'none';
            e.currentTarget.style.filter = 'none';
          }}
        >
          Score an address →
        </Link>
      </div>
    </section>
  );
}

// ──────────────────────────────────────────────────────────────────
// Footer
// ──────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer
      style={{
        padding: '36px 32px',
        background: 'var(--bg)',
      }}
    >
      <div
        style={{
          maxWidth: 1280,
          margin: '0 auto',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: 12,
          color: 'var(--text-dim)',
          flexWrap: 'wrap',
          gap: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <BrandMark size={20} />
          <span
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 16,
              fontWeight: 500,
              color: 'var(--ink)',
              letterSpacing: '-0.02em',
            }}
          >
            Civo
          </span>
          <span
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontStyle: 'italic',
              marginLeft: 12,
            }}
          >
            v1.0 · Preview
          </span>
        </div>
        <a
          href="mailto:hello@civo.energy"
          style={{ color: 'inherit', textDecoration: 'none' }}
        >
          hello@civo.energy
        </a>
        <span
          style={{
            fontFamily: "'Fraunces', Georgia, serif",
            fontStyle: 'italic',
          }}
        >
          Updated April 19, 2026
        </span>
      </div>
    </footer>
  );
}
