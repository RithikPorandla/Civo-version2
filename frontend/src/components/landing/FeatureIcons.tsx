/**
 * Simple geometric feature icons for the landing-page bento grid.
 * Each is a 40px square SVG, stroke 1.6, styled via currentColor so
 * the parent controls the tone.
 */

type IconProps = { size?: number };

const base = (size = 40) => ({
  width: size,
  height: size,
  viewBox: '0 0 40 40',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
});

// Parcel with a siting dot — "site scoring"
export const IconParcel = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M 8 12 L 30 8 L 32 28 L 8 32 Z" />
    <circle cx={20} cy={20} r={2.4} fill="currentColor" stroke="none" />
  </svg>
);

// Stacked layers — "spatial corpus"
export const IconLayers = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M 8 14 L 20 10 L 32 14 L 20 18 Z" />
    <path d="M 8 20 L 20 16 L 32 20" opacity={0.6} />
    <path d="M 8 26 L 20 22 L 32 26" opacity={0.35} />
  </svg>
);

// Stamp/seal — "statute-native"
export const IconStamp = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <circle cx={20} cy={20} r={12} />
    <circle cx={20} cy={20} r={8} />
    <path d="M 15 20 L 19 24 L 25 16" strokeWidth={2} />
  </svg>
);

// Citation chip — "sourced"
export const IconCitation = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M 8 12 h 18 a 4 4 0 0 1 4 4 v 10 a 4 4 0 0 1 -4 4 h -18 a 4 4 0 0 1 -4 -4 V 16 a 4 4 0 0 1 4 -4 Z" />
    <path d="M 10 18 h 10" strokeWidth={1.4} />
    <path d="M 10 22 h 14" strokeWidth={1.4} />
    <path d="M 10 26 h 6" strokeWidth={1.4} />
    <circle cx={28} cy={12} r={3} fill="currentColor" stroke="none" />
  </svg>
);

// Shield — "moratorium / protection flag"
export const IconShield = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M 20 6 L 32 10 V 20 C 32 26 27 30 20 34 C 13 30 8 26 8 20 V 10 Z" />
    <path d="M 15 19 L 19 23 L 26 15" strokeWidth={1.8} />
  </svg>
);

// Compass rose — "orientation / discovery"
export const IconCompass = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <circle cx={20} cy={20} r={12} />
    <path d="M 20 8 L 23 20 L 20 32 L 17 20 Z" fill="currentColor" stroke="none" opacity={0.7} />
    <path d="M 8 20 L 20 17 L 32 20 L 20 23 Z" fill="currentColor" stroke="none" opacity={0.45} />
  </svg>
);

// Document with lines — "PDF output"
export const IconDoc = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M 10 6 h 14 l 6 6 v 20 a 2 2 0 0 1 -2 2 h -18 a 2 2 0 0 1 -2 -2 V 8 a 2 2 0 0 1 2 -2 Z" />
    <path d="M 24 6 v 6 h 6" />
    <path d="M 14 18 h 12" strokeWidth={1.3} />
    <path d="M 14 22 h 12" strokeWidth={1.3} />
    <path d="M 14 26 h 8" strokeWidth={1.3} />
  </svg>
);

// Spark / bolt — "fast scoring"
export const IconBolt = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M 22 4 L 10 22 h 8 L 16 36 L 30 16 h -8 Z" />
  </svg>
);
