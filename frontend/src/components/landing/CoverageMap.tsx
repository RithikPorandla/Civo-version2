/**
 * Stylized Massachusetts coverage map — a simplified silhouette filled
 * with a warm dot pattern (suggesting parcels), with the covered
 * municipalities marked in accent + labeled.
 *
 * Not geographically precise — a visual shorthand for "our footprint."
 */

// Hand-smoothed MA outline approximation (viewBox 0..600, 0..320).
// Not used for geocoding — only for visual silhouette.
const MA_OUTLINE =
  'M 24 162 L 38 140 L 58 128 L 88 118 L 132 108 L 168 100 L 214 92 L 264 86 L 316 84 L 358 88 L 398 96 L 432 108 L 454 128 L 458 152 L 446 168 L 432 180 L 420 186 L 404 194 L 400 214 L 418 224 L 448 232 L 482 240 L 516 248 L 544 254 L 566 260 L 562 272 L 536 280 L 510 280 L 484 272 L 464 260 L 444 248 L 428 244 L 414 252 L 402 262 L 384 264 L 358 258 L 328 252 L 296 246 L 266 240 L 240 232 L 216 222 L 194 210 L 172 198 L 150 188 L 130 180 L 108 174 L 84 170 L 58 166 Z';

// Covered towns with approximate positions in the viewBox.
// These are tuned for visual balance, not lat/long precision.
const COVERED = [
  { name: 'Whately', x: 96, y: 132 },
  { name: 'Acton', x: 300, y: 152 },
  { name: 'Burlington', x: 332, y: 142 },
  { name: 'Cambridge', x: 368, y: 170 },
  { name: 'East Freetown', x: 396, y: 238 },
];

export default function CoverageMap() {
  // Dot grid — fills the silhouette with a quiet parcel pattern.
  const dots: Array<{ x: number; y: number }> = [];
  for (let x = 28; x <= 560; x += 14) {
    for (let y = 88; y <= 272; y += 14) {
      dots.push({ x, y });
    }
  }

  return (
    <svg
      viewBox="0 0 600 320"
      style={{ width: '100%', height: 'auto', display: 'block' }}
      aria-label="Massachusetts coverage"
    >
      <defs>
        <clipPath id="ma-clip">
          <path d={MA_OUTLINE} />
        </clipPath>
      </defs>

      {/* silhouette fill */}
      <path
        d={MA_OUTLINE}
        fill="var(--surface)"
        stroke="var(--border)"
        strokeWidth={1.2}
      />

      {/* dotted parcel grid — clipped to the silhouette */}
      <g clipPath="url(#ma-clip)">
        {dots.map((d, i) => (
          <circle
            key={i}
            cx={d.x}
            cy={d.y}
            r={1.1}
            fill="var(--accent)"
            opacity={0.35}
          />
        ))}
      </g>

      {/* covered towns */}
      {COVERED.map((t) => (
        <g key={t.name}>
          {/* pulse halo */}
          <circle
            cx={t.x}
            cy={t.y}
            r={14}
            fill="var(--accent)"
            opacity={0.14}
          />
          <circle
            cx={t.x}
            cy={t.y}
            r={6}
            fill="var(--accent)"
            stroke="var(--bg)"
            strokeWidth={2}
          />
          {/* label leader */}
          <line
            x1={t.x}
            y1={t.y - 6}
            x2={t.x}
            y2={t.y - 24}
            stroke="var(--accent)"
            strokeWidth={0.8}
          />
          <text
            x={t.x}
            y={t.y - 30}
            fontFamily="'Fraunces', Georgia, serif"
            fontSize={13}
            fontWeight={500}
            fill="var(--text)"
            textAnchor="middle"
          >
            {t.name}
          </text>
        </g>
      ))}

      {/* "201 to go" counter bottom-right */}
      <g transform="translate(462, 296)">
        <rect
          x={0}
          y={-16}
          width={128}
          height={22}
          rx={11}
          fill="var(--bg)"
          stroke="var(--border-soft)"
        />
        <text
          x={10}
          y={-1}
          fontFamily="var(--sans)"
          fontSize={11}
          fontWeight={500}
          fill="var(--text-dim)"
          letterSpacing="0.05em"
        >
          5 covered · 346 to go
        </text>
      </g>
    </svg>
  );
}
