import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';

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
      <div style={{ maxWidth: 1040, margin: '0 auto', padding: '48px 32px', color: 'var(--text-dim)' }}>
        Loading portfolio…
      </div>
    );
  if (error || !data)
    return (
      <div style={{ maxWidth: 1040, margin: '0 auto', padding: '48px 32px', color: 'var(--bad)' }}>
        Error: {String(error)}
      </div>
    );

  return (
    <div style={{ maxWidth: 1040, margin: '0 auto', padding: '48px 32px 96px' }}>
      <div className="eyebrow" style={{ marginBottom: 10 }}>
        Portfolio
      </div>
      <h1
        className="display"
        style={{ fontSize: 54, margin: 0, letterSpacing: '-0.028em', lineHeight: 1.02 }}
      >
        {data.name || 'Untitled'}
      </h1>
      <div
        className="tnum"
        style={{ fontSize: 13, color: 'var(--text-mid)', marginTop: 10, marginBottom: 32 }}
      >
        {data.id} · {data.items.length} parcels · {data.project_type || 'generic'} · scored{' '}
        {new Date(data.scored_at).toLocaleDateString()}
      </div>

      <div
        className="card"
        style={{ overflow: 'hidden' }}
      >
        <div
          className="label"
          style={{
            display: 'grid',
            padding: '14px 24px',
            borderBottom: '1px solid var(--border-soft)',
            gridTemplateColumns: '40px 1fr 100px 220px 60px',
          }}
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
              ? { c: 'var(--good)', bg: 'var(--sage-soft, #eaf2e7)' }
              : it.bucket === 'CONDITIONALLY SUITABLE'
              ? { c: 'var(--gold, #c08a3e)', bg: 'var(--gold-soft, #f7efe0)' }
              : { c: 'var(--bad)', bg: 'var(--bad-soft, #f5e8e4)' };
          return (
            <div
              key={it.rank}
              style={{
                display: 'grid',
                alignItems: 'center',
                padding: '16px 24px',
                borderBottom: '1px solid var(--border-soft)',
                gridTemplateColumns: '40px 1fr 100px 220px 60px',
              }}
            >
              <div
                className="tnum"
                style={{ fontFamily: DISPLAY, fontStyle: 'italic', color: 'var(--text-dim)' }}
              >
                {String(it.rank).padStart(2, '0')}
              </div>
              <div>
                <div style={{ fontFamily: DISPLAY, fontSize: 16, fontWeight: 500, letterSpacing: '-0.008em' }}>
                  {it.address}
                </div>
                {it.parcel_id && (
                  <div className="tnum" style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
                    {it.parcel_id}
                  </div>
                )}
              </div>
              <div
                className="tnum"
                style={{ fontFamily: DISPLAY, fontSize: 22, letterSpacing: '-0.018em' }}
              >
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
                      borderRadius: 999,
                      fontSize: 12,
                      fontWeight: 500,
                    }}
                  >
                    {it.bucket}
                  </span>
                ) : (
                  <span style={{ fontSize: 13, color: 'var(--text-dim)' }}>{it.error || '—'}</span>
                )}
              </div>
              <div style={{ textAlign: 'right' }}>
                {it.score_report_id && (
                  <Link to={`/report/${it.score_report_id}`} className="link-accent" style={{ fontSize: 13 }}>
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
