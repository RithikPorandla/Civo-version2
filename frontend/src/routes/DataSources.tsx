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
      <header style={{ marginBottom: 40 }}>
        <div
          style={{
            fontSize: 11,
            color: '#6B6B66',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            fontWeight: 500,
            marginBottom: 10,
          }}
        >
          Provenance
        </div>
        <h1
          style={{
            fontSize: 36,
            fontWeight: 600,
            letterSpacing: '-0.02em',
            margin: 0,
            color: '#141514',
          }}
        >
          Data sources
        </h1>
        <p
          style={{
            fontSize: 15,
            color: '#6B6B66',
            marginTop: 10,
            maxWidth: 640,
            lineHeight: 1.6,
          }}
        >
          Every score on every Civo report traces back to one of the datasets below. This
          index is the single source of truth — when a citation appears on a report, it
          came from one of these rows.
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
          paddingTop: 24,
          borderTop: '1px solid #E8E5DD',
          fontSize: 12,
          color: '#8A8A8A',
          lineHeight: 1.6,
        }}
      >
        Coverage gaps (status · <em>planned</em>) are disclosed deliberately. We'd rather
        tell you what isn't yet ingested than hide it. Last reviewed {data.last_reviewed}.
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <div
        style={{
          fontSize: 10,
          color: '#6B6B66',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          fontWeight: 500,
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 600, color: '#141514' }}>{value}</div>
    </div>
  );

  return (
    <div
      style={{
        display: 'flex',
        gap: 40,
        marginTop: 24,
        padding: '16px 0',
        borderTop: '1px solid #E8E5DD',
        borderBottom: '1px solid #E8E5DD',
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
          background: on ? '#141514' : 'transparent',
          color: on ? '#F7F5F0' : '#141514',
          border: on ? '1px solid #141514' : '1px solid #E8E5DD',
          borderRadius: 100,
          padding: '7px 16px',
          fontSize: 13,
          fontWeight: 500,
          cursor: 'pointer',
        }}
      >
        {label} <span style={{ opacity: 0.55 }}>· {count}</span>
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
      style={{
        background: '#FFFFFF',
        border: '1px solid #E8E5DD',
        borderRadius: 14,
        padding: '18px 22px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#141514' }}>{s.name}</div>
            <StatusPill status={s.status} />
            {s.docket && <Tag>{s.docket}</Tag>}
          </div>
          <div style={{ fontSize: 12, color: '#6B6B66', marginTop: 2 }}>{s.agency}</div>
        </div>
        {s.row_count != null && (
          <div
            style={{
              fontSize: 13,
              color: '#141514',
              fontVariantNumeric: 'tabular-nums',
              fontWeight: 500,
              whiteSpace: 'nowrap',
            }}
            title="Current DB row count"
          >
            {s.row_count.toLocaleString()} <span style={{ color: '#8A8A8A' }}>rows</span>
          </div>
        )}
      </div>

      {s.coverage && (
        <div style={{ fontSize: 13, color: '#141514', lineHeight: 1.5 }}>{s.coverage}</div>
      )}

      {s.used_by.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <div
            style={{
              fontSize: 10,
              color: '#8A8A8A',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              fontWeight: 500,
            }}
          >
            Feeds
          </div>
          <ul style={{ margin: 0, padding: '0 0 0 16px', fontSize: 13, color: '#525252' }}>
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
            color: '#6B6B66',
            lineHeight: 1.5,
            fontStyle: 'italic',
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
            style={{ fontSize: 12, color: '#1F3D2E', textDecoration: 'none' }}
          >
            {s.url.replace(/^https?:\/\//, '').slice(0, 60)}
            {s.url.length > 60 ? '…' : ''} ↗
          </a>
        ) : (
          <span />
        )}
        <div style={{ fontSize: 11, color: '#8A8A8A' }}>
          {s.last_refreshed && `Refreshed ${s.last_refreshed}`}
          {s.last_reviewed && !s.last_refreshed && `Reviewed ${s.last_reviewed}`}
        </div>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const cfg: Record<string, { bg: string; fg: string; label: string }> = {
    ingested: { bg: '#EAF2E7', fg: '#3C6B3F', label: 'Ingested' },
    planned: { bg: '#F7EFE0', fg: '#8C6726', label: 'Planned' },
    external: { bg: '#F0EDE5', fg: '#6B5840', label: 'External' },
  };
  const c = cfg[status] ?? cfg.ingested;
  return (
    <span
      style={{
        display: 'inline-block',
        background: c.bg,
        color: c.fg,
        borderRadius: 100,
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
        background: '#F0EDE5',
        color: '#525252',
        borderRadius: 100,
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
    <div style={{ padding: 40, color: '#8A8A8A', fontSize: 14 }}>Loading sources…</div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div style={{ padding: 40 }}>
      <div style={{ fontSize: 16, fontWeight: 600, color: '#C0392B' }}>Couldn't load sources</div>
      <div style={{ fontSize: 13, color: '#6B6B66', marginTop: 6 }}>{message}</div>
    </div>
  );
}
