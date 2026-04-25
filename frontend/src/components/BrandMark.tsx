interface Props {
  size?: number;
  color?: string;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Civo mark — the "Parcel" concept from the brand system.
 * A tilted quadrilateral with a siting point: the subject of the
 * product (a piece of land, analyzed). Inline SVG so it scales to
 * any size and recolors via the `color` prop.
 */
export default function BrandMark({ size = 28, color = '#8b7355', className, style }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      className={className}
      style={style}
      aria-hidden="true"
    >
      <path
        d="M 8 10 L 32 7 L 34 30 L 6 33 Z"
        stroke={color}
        strokeWidth={2.2}
        strokeLinejoin="round"
        fill="none"
      />
      <circle cx={20} cy={19} r={3} fill={color} />
    </svg>
  );
}

/**
 * Mark + Fraunces wordmark lockup, with optional "MA Permitting"
 * eyebrow underneath. Used in the sidebar and in footers.
 */
export function BrandLockup({
  size = 26,
  wordSize = 22,
  color = '#8b7355',
  tag,
}: {
  size?: number;
  wordSize?: number;
  color?: string;
  tag?: string;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <BrandMark size={size} color={color} />
      <div>
        <div
          style={{
            fontFamily: "'Fraunces', Georgia, serif",
            fontSize: wordSize,
            fontWeight: 500,
            letterSpacing: '-0.025em',
            lineHeight: 1,
            color: 'var(--text)',
          }}
        >
          Civo
        </div>
        {tag && (
          <span
            style={{
              display: 'block',
              fontSize: 9,
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              color: 'var(--text-dim)',
              marginTop: 3,
              fontWeight: 500,
            }}
          >
            {tag}
          </span>
        )}
      </div>
    </div>
  );
}
