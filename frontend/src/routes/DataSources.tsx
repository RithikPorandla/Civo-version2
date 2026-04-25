import { useEffect, useState } from 'react';
import { api, type DataSource, type DataSourcesResponse } from '../lib/api';

type CategoryKey = 'all' | 'spatial' | 'regulatory' | 'municipal' | 'benchmark' | 'external';

const CATEGORY_LABELS: Record<Exclude<CategoryKey, 'all'>, string> = {
  spatial: 'Spatial',
  regulatory: 'Regulatory',
  municipal: 'Municipal',
  benchmark: 'Benchmarks',
  external: 'External services',
};

export default function DataSources() {
  const [data, setData] = useState<DataSourcesResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [active, setActive] = useState<CategoryKey>('all');

  useEffect(() => {
    api
      .dataSources()
      .then(setData)
      .catch((e) => setErr(e.message ?? 'Failed to load data sources'));
  }, []);

  if (err) return <ErrorState message={err} />;
  if (!data) return <LoadingState />;

  const filtered =
    active === 'all' ? data.sources : data.sources.filter((s) => s.category === active);

  const ingestedCount = data.sources.filter((s) => s.status === 'ingested').length;
  const plannedCount = data.sources.filter((s) => s.status === 'planned').length;
  const externalCount = data.sources.filter((s) => s.status === 'external').length;

  return (
    <div style={{ maxWidth: 1040, margin: '0 auto', padding: '48px 32px 96px' }}>
      <header style={{ marginBottom: 32 }}>
        <div className="eyebrow" style={{ marginBottom: 10 }}>
          Provenance
        </div>
        <h1
          className="display"
          style={{ fontSize: 44, margin: 0, letterSpacing: '-0.022em', lineHeight: 1.02 }}
        >
          Data sources
        </h1>
        <p
          style={{
            fontSize: 15,
            color: 'var(--text-mid)',
            marginTop: 14,
            maxWidth: 640,
            lineHeight: 1.6,
          }}
        >
          Every score on every Civo report traces back to one of the datasets below. This
          index is the single source of truth — when a citation appears on a report, it came
          from one of these rows.
        </p>
        <StatsStrip
          total={data.total_sources}
          ingested={ingestedCount}
          planned={plannedCount}
          external={externalCount}
          lastReviewed={data.last_reviewed}
        />
      </header>

      <CategoryTabs
        active={active}
        onChange={setActive}
        counts={data.by_category as Record<string, number>}
        total={data.total_sources}
      />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr',
          gap: 12,
          marginTop: 24,
        }}
      >
        {filtered.map((s) => (
          <SourceCard key={s.id} source={s} />
        ))}
      </div>

      <footer
        style={{
          marginTop: 48,
          paddingTop: 22,
          borderTop: '1px solid var(--border-soft)',
          fontSize: 12,
          color: 'var(--text-dim)',
          lineHeight: 1.6,
          fontFamily: "'Fraunces', Georgia, serif",
          fontStyle: 'italic',
        }}
      >
        Coverage gaps (status · planned) are disclosed deliberately. We'd rather tell you what
        isn't yet ingested than hide it. Last reviewed {data.last_reviewed}.
      </footer>
    </div>
  );
}

function StatsStrip({
  total,
  ingested,
  planned,
  external,
  lastReviewed,
}: {
  total: number;
  ingested: number;
  planned: number;
  external: number;
  lastReviewed: string;
}) {
  const stat = (label: string, value: string | number) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div className="label">{label}</div>
      <div
        className="tnum"
        style={{
          fontFamily: "'Fraunces', Georgia, serif",
          fontSize: 22,
          fontWeight: 400,
          letterSpacing: '-0.018em',
          color: 'var(--text)',
        }}
      >
        {value}
      </div>
    </div>
  );

  return (
    <div
      style={{
        display: 'flex',
        gap: 40,
        marginTop: 24,
        padding: '18px 0',
        borderTop: '1px solid var(--border-soft)',
        borderBottom: '1px solid var(--border-soft)',
      }}
    >
      {stat('Total sources', total)}
      {stat('Ingested', ingested)}
      {stat('Planned', planned)}
      {stat('External', external)}
      {stat('Last reviewed', lastReviewed || '—')}
    </div>
  );
}

function CategoryTabs({
  active,
  onChange,
  counts,
  total,
}: {
  active: CategoryKey;
  onChange: (k: CategoryKey) => void;
  counts: Record<string, number>;
  total: number;
}) {
  const tab = (k: CategoryKey, label: string, count: number) => {
    const on = active === k;
    return (
      <button
        key={k}
        onClick={() => onChange(k)}
        style={{
          background: on ? 'var(--text)' : 'transparent',
          color: on ? 'var(--bg)' : 'var(--text)',
          border: on ? '1px solid var(--text)' : '1px solid var(--border)',
          borderRadius: 999,
          padding: '7px 16px',
          fontSize: 13,
          fontWeight: 500,
          cursor: 'pointer',
          fontFamily: 'inherit',
          transition: 'background 120ms ease, color 120ms ease, border-color 120ms ease',
        }}
      >
        {label} <span style={{ opacity: 0.55 }} className="tnum">· {count}</span>
      </button>
    );
  };

  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {tab('all', 'All', total)}
      {(Object.keys(CATEGORY_LABELS) as Array<keyof typeof CATEGORY_LABELS>).map((k) =>
        tab(k, CATEGORY_LABELS[k], counts[k] ?? 0)
      )}
    </div>
  );
}

function SourceCard({ source: s }: { source: DataSource }) {
  return (
    <div
      id={s.id}
      className="card"
      style={{
        padding: '20px 22px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <div
              style={{
                fontFamily: "'Fraunces', Georgia, serif",
                fontSize: 17,
                fontWeight: 500,
                letterSpacing: '-0.012em',
                color: 'var(--text)',
              }}
            >
              {s.name}
            </div>
            <StatusPill status={s.status} />
            {s.docket && <Tag>{s.docket}</Tag>}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-mid)', marginTop: 4 }}>
            {s.agency}
          </div>
        </div>
        {s.row_count != null && (
          <div
            className="tnum"
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 18,
              fontWeight: 400,
              letterSpacing: '-0.015em',
              color: 'var(--text)',
              whiteSpace: 'nowrap',
            }}
            title="Current DB row count"
          >
            {s.row_count.toLocaleString()}{' '}
            <span style={{ color: 'var(--text-dim)', fontSize: 12, fontFamily: 'var(--sans)' }}>
              rows
            </span>
          </div>
        )}
      </div>

      {s.coverage && (
        <div style={{ fontSize: 13.5, color: 'var(--text)', lineHeight: 1.55 }}>
          {s.coverage}
        </div>
      )}

      {s.used_by.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div className="label">Feeds</div>
          <ul
            style={{
              margin: 0,
              padding: '0 0 0 16px',
              fontSize: 13,
              color: 'var(--text-mid)',
              lineHeight: 1.5,
            }}
          >
            {s.used_by.map((u, i) => (
              <li key={i}>{u}</li>
            ))}
          </ul>
        </div>
      )}

      {s.notes && (
        <div
          style={{
            fontSize: 12,
            color: 'var(--text-mid)',
            lineHeight: 1.5,
            fontStyle: 'italic',
            fontFamily: "'Fraunces', Georgia, serif",
          }}
        >
          {s.notes}
        </div>
      )}

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: 2,
        }}
      >
        {s.url ? (
          <a
            href={s.url}
            target="_blank"
            rel="noreferrer"
            className="link-accent"
            style={{ fontSize: 12 }}
          >
            {s.url.replace(/^https?:\/\//, '').slice(0, 60)}
            {s.url.length > 60 ? '…' : ''} ↗
          </a>
        ) : (
          <span />
        )}
        <div className="tnum" style={{ fontSize: 11, color: 'var(--text-dim)' }}>
          {s.last_refreshed && `Refreshed ${s.last_refreshed}`}
          {s.last_reviewed && !s.last_refreshed && `Reviewed ${s.last_reviewed}`}
        </div>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const cfg: Record<string, { bg: string; fg: string; label: string }> = {
    ingested: { bg: 'var(--sage-soft, #eaf2e7)', fg: 'var(--good)', label: 'Ingested' },
    planned: { bg: 'var(--gold-soft, #f7efe0)', fg: 'var(--gold, #c08a3e)', label: 'Planned' },
    external: { bg: 'var(--surface-alt)', fg: 'var(--accent)', label: 'External' },
  };
  const c = cfg[status] ?? cfg.ingested;
  return (
    <span
      style={{
        display: 'inline-block',
        background: c.bg,
        color: c.fg,
        borderRadius: 999,
        padding: '2px 10px',
        fontSize: 11,
        fontWeight: 500,
      }}
    >
      {c.label}
    </span>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        display: 'inline-block',
        background: 'var(--surface-alt)',
        color: 'var(--text-mid)',
        borderRadius: 999,
        padding: '2px 10px',
        fontSize: 11,
        fontWeight: 500,
      }}
    >
      {children}
    </span>
  );
}

function LoadingState() {
  return (
    <div style={{ padding: 40, color: 'var(--text-dim)', fontSize: 14 }}>Loading sources…</div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div style={{ padding: 40 }}>
      <div
        style={{
          fontFamily: "'Fraunces', Georgia, serif",
          fontSize: 20,
          fontWeight: 500,
          color: 'var(--bad)',
        }}
      >
        Couldn't load sources
      </div>
      <div style={{ fontSize: 13, color: 'var(--text-mid)', marginTop: 6 }}>{message}</div>
    </div>
  );
}
