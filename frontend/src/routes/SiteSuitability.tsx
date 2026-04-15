import { Link } from 'react-router-dom';

const DISPLAY = "'Fraunces', Georgia, serif";

const EXAMPLES = [
  { id: 1, address: 'Kendall Square, Cambridge, MA', score: 92.5, bucket: 'SUITABLE' },
  { id: 2, address: '50 Nagog Park, Acton, MA', score: 64.1, bucket: 'CONDITIONALLY SUITABLE' },
  { id: 3, address: 'East Freetown, MA', score: 35.4, bucket: 'CONSTRAINED' },
];

export default function SiteSuitability() {
  return (
    <div className="px-12 py-12 max-w-6xl">
      <div className="eyebrow mb-3">Site Suitability</div>
      <h1
        style={{
          fontFamily: DISPLAY,
          fontSize: 54,
          letterSpacing: -1.5,
          lineHeight: 1.05,
          fontWeight: 400,
        }}
      >
        Your scored reports.
      </h1>
      <p className="text-textMid mt-6 max-w-2xl mb-12">
        Civo scores every MassGIS parcel against 225 CMR 29.00 — seven weighted criteria,
        every finding cited. Open an existing report or run a new one from Address Lookup.
      </p>

      <Link to="/lookup" className="btn-pill btn-pill-primary inline-flex mb-10">
        Run a new report →
      </Link>

      <div className="eyebrow mb-4">Reference parcels</div>
      <div className="border hairline rounded-md overflow-hidden bg-surface">
        <div
          className="grid text-[12px] uppercase tracking-wider text-textDim px-6 py-3 border-b hairline"
          style={{ gridTemplateColumns: '1fr 140px 200px 80px' }}
        >
          <div>Address</div>
          <div>Score</div>
          <div>Bucket</div>
          <div />
        </div>
        {EXAMPLES.map((e) => (
          <div
            key={e.id}
            className="grid items-center px-6 py-4 border-b hairline last:border-b-0"
            style={{ gridTemplateColumns: '1fr 140px 200px 80px' }}
          >
            <div style={{ fontFamily: DISPLAY, fontSize: 17 }}>{e.address}</div>
            <div style={{ fontFamily: DISPLAY, fontSize: 22 }}>{e.score}</div>
            <div className="text-[12px] text-textMid">{e.bucket}</div>
            <div className="text-right">
              <Link
                to={`/report/${e.id}`}
                style={{ color: '#8b7355', fontSize: 13 }}
              >
                Open →
              </Link>
            </div>
          </div>
        ))}
      </div>
      <div className="text-[11px] text-textDim mt-3">
        The reference rows assume report IDs 1-3 exist in your local database.
        Run a fresh score from Address Lookup to populate new ones.
      </div>
    </div>
  );
}
