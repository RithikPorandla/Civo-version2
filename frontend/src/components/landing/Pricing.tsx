import { Link } from 'react-router-dom';

/**
 * Three-tier placeholder pricing. Labeled "Preview pricing" so it's
 * clearly not a commitment yet — real numbers come post-launch.
 */
export default function Pricing() {
  const tiers: Array<{
    name: string;
    tag?: string;
    price: string;
    cadence: string;
    summary: string;
    features: string[];
    cta: { label: string; to: string };
    featured?: boolean;
  }> = [
    {
      name: 'Preview',
      price: '$0',
      cadence: 'during MA pilot',
      summary: 'Score any address. Read the full report. Good for consultants piloting Civo.',
      features: [
        'Unlimited address lookups',
        '5 covered towns',
        'Cited report + PDF export',
        'Moratorium + HCA flags',
      ],
      cta: { label: 'Start free', to: '/app/lookup' },
    },
    {
      name: 'Consultant',
      tag: 'Most fitted',
      price: '$ — ',
      cadence: '/ seat / month',
      summary: 'The working plan for MA permitting firms — portfolio scoring, batch reports, shared workspace.',
      features: [
        'Everything in Preview',
        'Portfolio of parcels + batch scoring',
        'Discover candidate sites from ESMP anchors',
        'Branded PDF exports',
        'Priority town ingestion',
      ],
      cta: { label: 'Talk to us', to: '/app' },
      featured: true,
    },
    {
      name: 'Developer / Utility',
      price: '$ — ',
      cadence: 'annual, contracted',
      summary: 'For developers and utilities running repeat site screening at scale. Includes API access + custom ingest.',
      features: [
        'Everything in Consultant',
        'API + webhooks',
        'Custom town ingest on request',
        'Mitigation cost benchmarks, firm-specific',
        'SLA + dedicated support',
      ],
      cta: { label: 'Request a call', to: '/app' },
    },
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
      {tiers.map((t) => (
        <article
          key={t.name}
          style={{
            background: t.featured ? 'var(--text)' : 'var(--bg)',
            color: t.featured ? 'var(--bg)' : 'var(--text)',
            border: t.featured
              ? '1px solid var(--text)'
              : '1px solid var(--border-soft)',
            borderRadius: 18,
            padding: '32px 28px 28px',
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
            position: 'relative',
            transform: t.featured ? 'translateY(-8px)' : 'none',
            boxShadow: t.featured
              ? '0 30px 80px -30px rgba(26,26,26,0.35)'
              : 'none',
          }}
        >
          {t.tag && (
            <span
              style={{
                position: 'absolute',
                top: -12,
                left: 28,
                fontSize: 10,
                letterSpacing: '0.16em',
                textTransform: 'uppercase',
                color: 'var(--bg)',
                background: 'var(--accent)',
                padding: '4px 10px',
                borderRadius: 999,
                fontWeight: 500,
              }}
            >
              {t.tag}
            </span>
          )}

          <div>
            <div
              style={{
                fontFamily: "'Fraunces', Georgia, serif",
                fontSize: 24,
                fontWeight: 500,
                letterSpacing: '-0.015em',
              }}
            >
              {t.name}
            </div>
            <div
              style={{
                marginTop: 14,
                display: 'flex',
                alignItems: 'baseline',
                gap: 8,
              }}
            >
              <span
                className="tnum"
                style={{
                  fontFamily: "'Fraunces', Georgia, serif",
                  fontSize: 52,
                  fontWeight: 400,
                  letterSpacing: '-0.032em',
                  lineHeight: 1,
                }}
              >
                {t.price}
              </span>
              <span
                style={{
                  fontSize: 12,
                  opacity: 0.75,
                  letterSpacing: '0.02em',
                }}
              >
                {t.cadence}
              </span>
            </div>
            <p
              style={{
                fontSize: 14,
                lineHeight: 1.6,
                opacity: t.featured ? 0.85 : 1,
                color: t.featured ? 'inherit' : 'var(--text-mid)',
                margin: '14px 0 0',
              }}
            >
              {t.summary}
            </p>
          </div>

          <ul
            style={{
              listStyle: 'none',
              padding: 0,
              margin: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
              flex: 1,
            }}
          >
            {t.features.map((f) => (
              <li
                key={f}
                style={{
                  fontSize: 13,
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 10,
                  lineHeight: 1.5,
                  opacity: t.featured ? 0.92 : 1,
                }}
              >
                <span
                  style={{
                    color: t.featured ? '#c89b6e' : 'var(--accent)',
                    fontWeight: 600,
                    marginTop: 2,
                  }}
                >
                  ✓
                </span>
                {f}
              </li>
            ))}
          </ul>

          <Link
            to={t.cta.to}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              padding: '11px 18px',
              borderRadius: 10,
              fontSize: 13.5,
              fontWeight: 500,
              textDecoration: 'none',
              background: t.featured ? '#c89b6e' : 'var(--text)',
              color: t.featured ? 'var(--text)' : 'var(--bg)',
              transition: 'filter 150ms ease',
              marginTop: 6,
            }}
            onMouseEnter={(e) => (e.currentTarget.style.filter = 'brightness(1.08)')}
            onMouseLeave={(e) => (e.currentTarget.style.filter = 'none')}
          >
            {t.cta.label} <span>→</span>
          </Link>
        </article>
      ))}
    </div>
  );
}
