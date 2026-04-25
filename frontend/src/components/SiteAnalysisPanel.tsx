import { useMutation, useQuery } from '@tanstack/react-query';
import { reportApi, type SiteAnalysisResponse } from '../lib/api';

/**
 * AI site characterization panel on the Report page. Claude vision
 * reads the aerial tile of the parcel (with boundary drawn onto the
 * image), returns structured features + a short narrative, and we
 * reconcile against MassGIS 2016 LU/LC so the UI can flag conflicts.
 *
 * Lazy + cached: the panel shows a CTA button until the user clicks
 * "Run analysis" — first run pays the ~10s / ~$0.30 vision call, then
 * it's cached forever. Cache key lives on (parcel, vision_version);
 * bumping the prompt invalidates.
 */

const C = {
  bg: 'var(--bg)',
  surface: 'var(--surface)',
  border: 'var(--border-soft)',
  text: 'var(--text)',
  textMid: 'var(--text-mid)',
  textDim: 'var(--text-dim)',
  good: 'var(--good)',
  warn: 'var(--gold, #c08a3e)',
};

export default function SiteAnalysisPanel({ parcelId }: { parcelId: string }) {
  // Only auto-load from cache — don't trigger a fresh vision call on mount.
  // We'll use a mutation instead, which the Run button fires explicitly.
  const cached = useQuery<SiteAnalysisResponse | null>({
    queryKey: ['site-analysis', parcelId],
    queryFn: async () => {
      // Peek at the endpoint non-destructively. The backend returns cached
      // rows without billing; only a fresh run costs. That means we can
      // always ask on mount and only the first view pays.
      return reportApi.siteAnalysis(parcelId);
    },
    staleTime: 60 * 60 * 1000,
    retry: false,
    // Disabled by default — the user opts in by clicking "Run analysis".
    // First-time users don't want a silent 10s background call.
    enabled: false,
  });

  const run = useMutation({
    mutationFn: (force: boolean) => reportApi.siteAnalysis(parcelId, force),
    onSuccess: (data) => {
      // Seed the query cache with the result so refetch / re-renders are free.
      cached.refetch();
      return data;
    },
  });

  const data = run.data ?? cached.data ?? null;
  const running = run.isPending;

  if (!data && !running) {
    return (
      <section
        style={{
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 16,
          padding: '20px 24px',
          marginBottom: 20,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>AI site characterization</div>
            <p
              style={{
                margin: '6px 0 0',
                fontSize: 13,
                color: C.textMid,
                lineHeight: 1.55,
                maxWidth: 560,
              }}
            >
              Run Claude vision on the parcel's 2025 aerial — returns impervious %,
              canopy %, detected buildings, and a written site narrative. Cross-checked
              against MassGIS 2016 land-use so conflicts surface. Takes ~10 seconds,
              cached after first run.
            </p>
          </div>
          <button className="btn btn-primary" onClick={() => run.mutate(false)}>
            Run analysis
          </button>
        </div>
      </section>
    );
  }

  if (running) {
    return (
      <section
        style={{
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 16,
          padding: '20px 24px',
          marginBottom: 20,
          textAlign: 'center',
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
          Analyzing the aerial…
        </div>
        <div style={{ fontSize: 12, color: C.textMid }}>
          Drawing the parcel boundary, sending to Claude, reconciling against MassGIS.
          ~10 seconds.
        </div>
      </section>
    );
  }

  if (!data) return null;

  return <Populated data={data} onForce={() => run.mutate(true)} />;
}

function Populated({ data, onForce }: { data: SiteAnalysisResponse; onForce: () => void }) {
  const c = data.characterization;
  const r = data.reconciliation;
  const confidencePct = Math.round(c.confidence * 100);

  const stats = [
    { label: 'Impervious', value: `${Math.round(c.impervious_pct)}%`, tile: 'tile-stone' },
    { label: 'Tree canopy', value: `${Math.round(c.tree_canopy_pct)}%`, tile: 'tile-sage' },
    { label: 'Open ground', value: `${Math.round(c.open_ground_pct)}%`, tile: 'tile-rust' },
    { label: 'Buildings', value: String(c.detected_building_count), tile: 'tile-paper' },
  ];

  return (
    <section
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 16,
        padding: '20px 24px',
        marginBottom: 20,
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          marginBottom: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>AI site characterization</div>
          <ConfidencePill pct={confidencePct} />
          {data.cached && (
            <span
              className="text-textDim"
              style={{ fontSize: 11, padding: '2px 8px', background: 'var(--surface-alt)', borderRadius: 100 }}
            >
              cached
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            className="btn btn-ghost no-print"
            onClick={onForce}
            style={{ fontSize: 12, padding: '6px 10px' }}
            title="Bill a fresh vision call (bypass cache)"
          >
            Re-run
          </button>
        </div>
      </header>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 12,
          marginBottom: 16,
        }}
      >
        {stats.map((s) => (
          <div
            key={s.label}
            className={`stat-tile ${s.tile}`}
            style={{ padding: '14px 16px', gap: 8, minHeight: 0 }}
          >
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-mid)' }}>
              {s.label}
            </div>
            <div className="tile-num tnum" style={{ fontSize: 26 }}>
              {s.value}
            </div>
          </div>
        ))}
      </div>

      <p
        style={{
          fontSize: 14,
          lineHeight: 1.65,
          margin: '0 0 12px',
          color: C.text,
          maxWidth: 780,
        }}
      >
        {c.narrative}
      </p>

      {r && <Reconciliation reconciliation={r} />}
    </section>
  );
}

function ConfidencePill({ pct }: { pct: number }) {
  const tone =
    pct >= 75
      ? { c: C.good, bg: 'var(--sage-soft, #eaf2e7)' }
      : pct >= 55
      ? { c: C.warn, bg: 'var(--gold-soft, #f7efe0)' }
      : { c: 'var(--bad)', bg: 'var(--bad-soft, #f5e8e4)' };
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 500,
        color: tone.c,
        background: tone.bg,
        padding: '3px 10px',
        borderRadius: 100,
      }}
    >
      {pct}% confidence
    </span>
  );
}

function Reconciliation({
  reconciliation,
}: {
  reconciliation: NonNullable<SiteAnalysisResponse['reconciliation']>;
}) {
  const isDivergent = reconciliation.flag === 'diverges';
  const tone = isDivergent
    ? { c: 'var(--gold, #c08a3e)', dot: 'var(--gold, #c08a3e)' }
    : { c: 'var(--good)', dot: 'var(--good)' };
  const vision = reconciliation.vision_impervious_pct;
  const mass = reconciliation.massgis_developed_pct;
  const delta = reconciliation.delta;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        fontSize: 12,
        color: C.textMid,
        paddingTop: 4,
      }}
      title={reconciliation.note || undefined}
    >
      <span
        aria-hidden="true"
        style={{
          width: 6,
          height: 6,
          borderRadius: 100,
          background: tone.dot,
          flexShrink: 0,
        }}
      />
      <span style={{ color: tone.c, fontWeight: 500 }}>
        {isDivergent ? 'MassGIS divergence' : 'Aligned with MassGIS'}
      </span>
      <span className="text-textDim">·</span>
      <span>
        Vision {vision}% · MassGIS {mass != null ? `${mass}%` : '—'}
        {delta != null && (
          <span style={{ color: tone.c, marginLeft: 6 }}>
            ({delta > 0 ? '+' : ''}{delta} pts)
          </span>
        )}
      </span>
    </div>
  );
}
