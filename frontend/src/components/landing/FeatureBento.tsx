import {
  IconBolt,
  IconCitation,
  IconCompass,
  IconDoc,
  IconLayers,
  IconParcel,
  IconShield,
  IconStamp,
} from './FeatureIcons';

/**
 * Asymmetric feature bento — 8 cards across 12 columns, 3 rows.
 * Mixes larger "hero" feature cells with smaller utility cells so
 * the grid reads dynamic rather than evenly spaced.
 */

type Feature = {
  icon: React.ReactNode;
  title: string;
  body: string;
  span: string; // CSS grid-column span like "span 6"
  rowSpan?: string;
  tone?: 'paper' | 'stone' | 'sage' | 'rust' | 'ink';
};

export default function FeatureBento() {
  const features: Feature[] = [
    {
      icon: <IconParcel />,
      title: 'Score any MA parcel',
      body: 'Paste any Massachusetts address. Civo resolves it to MassGIS parcel geometry and scores it against 225 CMR 29 in seconds.',
      span: 'span 7',
      tone: 'paper',
    },
    {
      icon: <IconBolt />,
      title: 'Sub-10 second reports',
      body: 'Pre-joined spatial + regulatory graph means the full scoring pipeline fits in a request round trip.',
      span: 'span 5',
      tone: 'stone',
    },
    {
      icon: <IconCitation />,
      title: 'Every claim, cited',
      body: 'Each criterion links to the statute, filing, or MassGIS source. Wayback snapshots when the URL rots.',
      span: 'span 4',
      tone: 'sage',
    },
    {
      icon: <IconShield />,
      title: 'Moratorium alerts',
      body: 'Active moratoria on solar, storage, or transmission surface on the report with dates + source.',
      span: 'span 4',
      tone: 'rust',
    },
    {
      icon: <IconStamp />,
      title: 'Statute-native',
      body: '225 CMR 29 is the scoring model. Weights and exemptions come from the regulation, not a product decision.',
      span: 'span 4',
      tone: 'paper',
    },
    {
      icon: <IconLayers />,
      title: 'HCA + mitigation costs',
      body: 'Host community agreement triggers, precedent dollar ranges, and offsite mitigation benchmarks — grounded in observed filings.',
      span: 'span 5',
      tone: 'ink',
    },
    {
      icon: <IconCompass />,
      title: 'Site discovery',
      body: 'Pick a planned ESMP anchor, set project type + radius, get back a ranked list of nearby developable parcels.',
      span: 'span 4',
      tone: 'sage',
    },
    {
      icon: <IconDoc />,
      title: 'Print-ready PDF',
      body: 'Every report exports cleanly. Sidebar + chrome strip on print — just the cited document.',
      span: 'span 3',
      tone: 'stone',
    },
  ];

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(12, 1fr)',
        gap: 14,
      }}
    >
      {features.map((f) => (
        <BentoCard key={f.title} feature={f} />
      ))}
    </div>
  );
}

function BentoCard({ feature }: { feature: Feature }) {
  const bgMap: Record<NonNullable<Feature['tone']>, string> = {
    paper: '#f7f3ea',
    stone: '#eef0ee',
    sage: '#e8ece2',
    rust: '#f3e7df',
    ink: '#1f2223',
  };
  const isInk = feature.tone === 'ink';
  const bg = feature.tone ? bgMap[feature.tone] : 'var(--surface)';
  const text = isInk ? '#f2efe8' : 'var(--text)';
  const mid = isInk ? 'rgba(242,239,232,0.72)' : 'var(--text-mid)';
  const accent = isInk ? '#c89b6e' : 'var(--accent)';

  return (
    <article
      style={{
        gridColumn: feature.span,
        background: bg,
        border: isInk ? '1px solid rgba(242,239,232,0.08)' : '1px solid var(--border-soft)',
        borderRadius: 18,
        padding: '28px 28px 26px',
        minHeight: 220,
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
      }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 10,
          background: isInk ? 'rgba(200,155,110,0.12)' : 'var(--bg)',
          border: isInk ? '1px solid rgba(200,155,110,0.2)' : '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: accent,
        }}
      >
        {feature.icon}
      </div>
      <h3
        style={{
          fontFamily: "'Fraunces', Georgia, serif",
          fontSize: 24,
          fontWeight: 500,
          letterSpacing: '-0.018em',
          margin: 0,
          lineHeight: 1.15,
          color: text,
        }}
      >
        {feature.title}
      </h3>
      <p
        style={{
          fontSize: 14,
          lineHeight: 1.65,
          color: mid,
          margin: 0,
          maxWidth: 360,
        }}
      >
        {feature.body}
      </p>
    </article>
  );
}
