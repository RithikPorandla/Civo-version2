import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';

const C = {
  border: '#ececec',
  text: '#1a1a1a',
  textMid: '#6b6b6b',
  textDim: '#9b9b9b',
  accent: '#8b7355',
  surface: '#ffffff',
  good: '#4a7c4f',
  goodSoft: '#eaf2e7',
  warn: '#c08a3e',
  warnSoft: '#f7efe0',
  bad: '#a85a4a',
  badSoft: '#f5e8e4',
};
const DISPLAY = "'Fraunces', Georgia, serif";

export default function Portfolio() {
  const { portfolioId } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ['portfolio', portfolioId],
    queryFn: () => api.portfolio(portfolioId!),
    enabled: !!portfolioId,
  });
  if (isLoading)
    return (
      <div className="max-w-5xl mx-auto px-8 pt-rhythm" style={{ color: C.textDim }}>
        Loading portfolio…
      </div>
    );
  if (error || !data)
    return (
      <div className="max-w-5xl mx-auto px-8 pt-rhythm text-bad">Error: {String(error)}</div>
    );

  return (
    <div className="max-w-5xl mx-auto px-8 pt-rhythm pb-rhythm-lg">
      <div className="eyebrow mb-3">Portfolio</div>
      <h1 style={{ fontFamily: DISPLAY, fontSize: 54, letterSpacing: -1.5, lineHeight: 1.05, fontWeight: 400 }}>
        {data.name || 'Untitled'}
      </h1>
      <div className="text-sm text-textMid mt-2 mb-10">
        {data.id} · {data.items.length} parcels · {data.project_type || 'generic'} · scored{' '}
        {new Date(data.scored_at).toLocaleDateString()}
      </div>
      <div className="border hairline rounded-md overflow-hidden bg-surface">
        <div
          className="grid text-[12px] uppercase tracking-wider text-textDim px-6 py-3 border-b hairline"
          style={{ gridTemplateColumns: '40px 1fr 100px 220px 60px' }}
        >
          <div>#</div>
          <div>Address</div>
          <div>Score</div>
          <div>Bucket</div>
          <div />
        </div>
        {data.items.map((it) => {
          const tone =
            it.bucket === 'SUITABLE'
              ? { c: C.good, bg: C.goodSoft }
              : it.bucket === 'CONDITIONALLY SUITABLE'
              ? { c: C.warn, bg: C.warnSoft }
              : { c: C.bad, bg: C.badSoft };
          return (
            <div
              key={it.rank}
              className="grid items-center px-6 py-4 border-b hairline"
              style={{ gridTemplateColumns: '40px 1fr 100px 220px 60px' }}
            >
              <div style={{ fontFamily: DISPLAY, fontStyle: 'italic', color: C.textDim }}>
                {String(it.rank).padStart(2, '0')}
              </div>
              <div>
                <div className="text-[15px]" style={{ fontFamily: DISPLAY }}>
                  {it.address}
                </div>
                {it.parcel_id && (
                  <div className="text-[12px] text-textDim">{it.parcel_id}</div>
                )}
              </div>
              <div style={{ fontFamily: DISPLAY, fontSize: 22 }}>
                {it.ok && it.total_score !== null ? Math.round(it.total_score!) : '—'}
              </div>
              <div>
                {it.bucket ? (
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '4px 12px',
                      background: tone.bg,
                      color: tone.c,
                      borderRadius: 100,
                      fontSize: 12,
                      fontWeight: 500,
                    }}
                  >
                    {it.bucket}
                  </span>
                ) : (
                  <span className="text-textDim text-sm">{it.error || '—'}</span>
                )}
              </div>
              <div className="text-right">
                {it.score_report_id && (
                  <Link
                    to={`/report/${it.score_report_id}`}
                    style={{ color: C.accent, fontSize: 13 }}
                  >
                    View →
                  </Link>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
