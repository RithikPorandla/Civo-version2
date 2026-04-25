import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { discoverApi, discoverNlApi, type DiscoverResponse, type DiscoverResultItem } from '../lib/api';
import { DiscoverMap } from '../components/DiscoverMap';
import { DiscoverNarrative } from '../components/DiscoverNarrative';
import { LayersPanel } from '../components/LayersPanel';
import { IconSearch } from '../components/Icon';

const LOADING_PHASES = [
  'Understanding your query…',
  'Searching Massachusetts parcels…',
  'Checking constraint layers…',
  'Generating analysis…',
];

const EXAMPLE_CHIPS = [
  '5MW BESS near EMA-North substations',
  'Solar sites in towns with DOER adoption',
  'Parcels >10 acres, no habitat constraints',
  'Compare Acton vs Burlington for BESS',
  'Towns with high ConCom approval rates',
];

interface AdvancedFilters {
  utility: string;
  siting: string;
  projectType: string;
  anchorId: number | null;
  radiusMi: number;
  excludeBiomapCore: boolean;
  excludeNhespPriority: boolean;
  minScore: number;
  minAcreage: string;
  doerStatus: string;
}

const DEFAULT_ADVANCED: AdvancedFilters = {
  utility: 'Eversource',
  siting: 'planned',
  projectType: 'bess_standalone',
  anchorId: null,
  radiusMi: 2,
  excludeBiomapCore: true,
  excludeNhespPriority: false,
  minScore: 0,
  minAcreage: '',
  doerStatus: '',
};

type QueryBreadcrumb = { query: string; response: DiscoverResponse };

export default function Discover() {
  const [input, setInput] = useState('');
  const [activeQuery, setActiveQuery] = useState('');
  const [response, setResponse] = useState<DiscoverResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [adv, setAdv] = useState<AdvancedFilters>(DEFAULT_ADVANCED);
  const [loadingPhase, setLoadingPhase] = useState(0);
  const [breadcrumbs, setBreadcrumbs] = useState<QueryBreadcrumb[]>([]);
  const [followUpInput, setFollowUpInput] = useState('');
  const [basemap, setBasemap] = useState<'street' | 'satellite'>('street');
  const [enabledLayers, setEnabledLayers] = useState<Set<string>>(new Set());
  const [tableFilter, setTableFilter] = useState('');
  const [showNarrative, setShowNarrative] = useState(false);
  const tableScrollRef = useRef<HTMLDivElement | null>(null);

  const { data: anchors = [] } = useQuery({
    queryKey: ['esmp-anchors', adv.utility, adv.siting],
    queryFn: () => discoverApi.listAnchors(adv.utility || undefined, adv.siting || undefined),
    enabled: showAdvanced,
  });

  const [apiError, setApiError] = useState<string | null>(null);

  const searchMut = useMutation({
    mutationFn: (query: string) => discoverNlApi.search(query),
    onSuccess: (data, query) => {
      setApiError(null);
      setResponse(data);
      setBreadcrumbs((prev) => [...prev, { query, response: data }]);
      setSelectedId(null);
      setShowNarrative(false);
    },
    onError: (err: Error) => setApiError(err.message),
  });

  const followupMut = useMutation({
    mutationFn: (fu: string) => discoverNlApi.followup(response!.query_id, fu),
    onSuccess: (data, fu) => {
      setApiError(null);
      setResponse(data);
      setBreadcrumbs((prev) => [...prev, { query: fu, response: data }]);
      setFollowUpInput('');
      setShowNarrative(false);
    },
    onError: (err: Error) => setApiError(err.message),
  });

  const isLoading = searchMut.isPending || followupMut.isPending;

  useEffect(() => {
    if (!isLoading) { setLoadingPhase(0); return; }
    const t = setInterval(() => setLoadingPhase((p) => (p + 1) % LOADING_PHASES.length), 1400);
    return () => clearInterval(t);
  }, [isLoading]);

  const handleSearch = useCallback(() => {
    const q = input.trim();
    if (!q || isLoading) return;
    setActiveQuery(q);
    searchMut.mutate(q);
  }, [input, isLoading, searchMut]);

  const handleChip = (chip: string) => {
    setInput(chip);
    setActiveQuery(chip);
    searchMut.mutate(chip);
  };

  const handleFollowUp = () => {
    const fu = followUpInput.trim();
    if (!fu || !response || isLoading) return;
    followupMut.mutate(fu);
  };

  const handleBreadcrumbRevert = (idx: number) => {
    const crumb = breadcrumbs[idx];
    setBreadcrumbs(breadcrumbs.slice(0, idx + 1));
    setResponse(crumb.response);
    setInput(crumb.query);
    setActiveQuery(crumb.query);
  };

  const toggleLayer = (id: string) => {
    setEnabledLayers((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  // Scroll table to selected row
  useEffect(() => {
    if (!selectedId || !tableScrollRef.current) return;
    const el = tableScrollRef.current.querySelector(`[data-id="${selectedId}"]`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [selectedId]);

  const results = response?.results ?? [];
  const narrative = response?.narrative ?? null;
  const citations = response?.citations ?? [];
  const hasResults = results.length > 0;

  const filteredResults = tableFilter
    ? results.filter(
        (r) =>
          (r.site_addr ?? '').toLowerCase().includes(tableFilter.toLowerCase()) ||
          r.town_name.toLowerCase().includes(tableFilter.toLowerCase())
      )
    : results;

  return (
    <div
      style={{
        height: 'calc(100vh - 56px)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        background: 'var(--bg)',
      }}
    >
      {/* ── Compact query bar ── */}
      <div
        style={{
          padding: '10px 20px',
          borderBottom: '1px solid var(--border-soft)',
          flexShrink: 0,
          background: 'var(--bg)',
        }}
      >
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <div
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              background: 'var(--surface)',
              border: `1px solid ${isLoading ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: 100,
              padding: '0 16px',
              gap: 10,
              transition: 'border-color 200ms ease',
              boxShadow: isLoading ? '0 0 0 3px rgba(90,58,31,0.08)' : 'none',
            }}
          >
            <span style={{ color: 'var(--text-faint)', flexShrink: 0, lineHeight: 0 }}>
              <IconSearch size={14} />
            </span>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Describe what you're looking for…"
              style={{
                flex: 1,
                border: 'none',
                background: 'transparent',
                outline: 'none',
                fontSize: 14,
                color: 'var(--text)',
                fontFamily: 'var(--sans)',
                padding: '9px 0',
              }}
            />
            {isLoading && (
              <span style={{ fontSize: 11, color: 'var(--text-dim)', flexShrink: 0 }}>
                {LOADING_PHASES[loadingPhase]}
              </span>
            )}
          </div>
          <button
            className="btn btn-primary"
            onClick={handleSearch}
            disabled={!input.trim() || isLoading}
            style={{ borderRadius: 100, padding: '9px 20px', flexShrink: 0, fontSize: 13 }}
          >
            Search
          </button>
          <button
            className="btn btn-ghost"
            onClick={() => setShowAdvanced((v) => !v)}
            style={{ borderRadius: 100, padding: '9px 16px', flexShrink: 0, fontSize: 13 }}
          >
            Filters {showAdvanced ? '▴' : '▾'}
          </button>
        </div>

        {!activeQuery && !isLoading && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
            {EXAMPLE_CHIPS.map((chip) => (
              <button
                key={chip}
                onClick={() => handleChip(chip)}
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  fontFamily: 'var(--sans)',
                  padding: '3px 11px',
                  borderRadius: 999,
                  border: '1px solid var(--border)',
                  background: 'var(--surface-alt)',
                  color: 'var(--accent)',
                  cursor: 'pointer',
                  transition: 'background 120ms ease',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-warm)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface-alt)')}
              >
                {chip}
              </button>
            ))}
          </div>
        )}

        {showAdvanced && (
          <AdvancedFiltersPanel adv={adv} setAdv={setAdv} anchors={anchors} />
        )}
      </div>

      {/* ── Map + Table body ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* Map section — full width, top ~52% */}
        <div style={{ flex: '0 0 52%', position: 'relative', overflow: 'hidden' }}>
          <DiscoverMap
            results={results}
            selectedId={selectedId}
            hoveredId={hoveredId}
            onSelect={(id) => setSelectedId(id || null)}
            onHover={(id) => setHoveredId(id)}
            basemap={basemap}
          />
          <LayersPanel
            basemap={basemap}
            onBasemapChange={setBasemap}
            enabled={enabledLayers}
            onToggle={toggleLayer}
          />
        </div>

        {/* Table section */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            borderTop: '2px solid var(--border-soft)',
          }}
        >
          {/* Table toolbar */}
          <div
            style={{
              padding: '7px 16px',
              borderBottom: '1px solid var(--border-soft)',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              flexShrink: 0,
              background: 'var(--surface)',
            }}
          >
            {/* Table search filter */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                padding: '0 10px',
                gap: 6,
              }}
            >
              <IconSearch size={12} className="text-textDim" />
              <input
                value={tableFilter}
                onChange={(e) => setTableFilter(e.target.value)}
                placeholder="Search address or town…"
                style={{
                  border: 'none',
                  background: 'transparent',
                  outline: 'none',
                  fontSize: 12,
                  color: 'var(--text)',
                  fontFamily: 'var(--sans)',
                  padding: '5px 0',
                  width: 180,
                }}
              />
            </div>

            {/* Breadcrumb trail */}
            {breadcrumbs.length > 1 && (
              <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                {breadcrumbs.map((b, i) => (
                  <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <button
                      onClick={() => handleBreadcrumbRevert(i)}
                      style={{
                        fontSize: 11,
                        color: i === breadcrumbs.length - 1 ? 'var(--text)' : 'var(--text-dim)',
                        fontWeight: i === breadcrumbs.length - 1 ? 500 : 400,
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        padding: 0,
                        fontFamily: 'var(--sans)',
                        textDecoration: i < breadcrumbs.length - 1 ? 'underline' : 'none',
                      }}
                    >
                      {b.query.length > 24 ? b.query.slice(0, 24) + '…' : b.query}
                    </button>
                    {i < breadcrumbs.length - 1 && (
                      <span style={{ color: 'var(--text-faint)', fontSize: 11 }}>→</span>
                    )}
                  </span>
                ))}
              </div>
            )}

            {/* Narrative toggle */}
            {narrative && !isLoading && (
              <button
                onClick={() => setShowNarrative((v) => !v)}
                style={{
                  fontSize: 11,
                  fontWeight: 500,
                  color: 'var(--accent)',
                  background: 'none',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  padding: '3px 9px',
                  cursor: 'pointer',
                  fontFamily: 'var(--sans)',
                }}
              >
                Analysis {showNarrative ? '▴' : '▾'}
              </button>
            )}

            {/* Follow-up — after results */}
            {hasResults && !isLoading && (
              <div style={{ display: 'flex', gap: 6, marginLeft: 'auto' }}>
                <input
                  value={followUpInput}
                  onChange={(e) => setFollowUpInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleFollowUp()}
                  placeholder="Refine results…"
                  style={{
                    padding: '5px 10px',
                    fontSize: 12,
                    fontFamily: 'var(--sans)',
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    outline: 'none',
                    color: 'var(--text)',
                    width: 160,
                  }}
                />
                <button
                  className="btn btn-ghost"
                  onClick={handleFollowUp}
                  disabled={!followUpInput.trim() || followupMut.isPending}
                  style={{ fontSize: 11, padding: '4px 10px' }}
                >
                  →
                </button>
              </div>
            )}

            {/* Result count */}
            <span
              className="tnum"
              style={{
                fontSize: 11,
                color: 'var(--text-dim)',
                fontWeight: 500,
                marginLeft: hasResults ? 8 : 'auto',
                flexShrink: 0,
              }}
            >
              {isLoading
                ? LOADING_PHASES[loadingPhase]
                : hasResults
                ? `${filteredResults.length}${filteredResults.length !== results.length ? ` of ${results.length}` : ''} sites`
                : activeQuery
                ? 'No results'
                : 'Ready'}
            </span>
          </div>

          {/* Narrative panel */}
          {showNarrative && narrative && !isLoading && (
            <div
              style={{
                flexShrink: 0,
                borderBottom: '1px solid var(--border-soft)',
                maxHeight: 160,
                overflowY: 'auto',
              }}
            >
              <DiscoverNarrative narrative={narrative} citations={citations} />
            </div>
          )}

          {/* API error */}
          {!isLoading && apiError && (
            <div
              style={{
                margin: '12px 16px',
                padding: '10px 14px',
                background: '#fdf2f0',
                border: '1px solid #e8c8c2',
                borderRadius: 8,
                fontSize: 12,
                color: 'var(--rust)',
                flexShrink: 0,
              }}
            >
              <strong>Search error:</strong> {apiError}
            </div>
          )}

          {/* Table scroll area */}
          <div ref={tableScrollRef} style={{ flex: 1, overflowY: 'auto' }}>
            {isLoading ? (
              <TableSkeleton />
            ) : hasResults ? (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr
                    style={{
                      background: 'var(--surface)',
                      borderBottom: '1px solid var(--border-soft)',
                      position: 'sticky',
                      top: 0,
                      zIndex: 1,
                    }}
                  >
                    <Th style={{ width: 40 }}>#</Th>
                    <Th>Parcel</Th>
                    <Th>Town</Th>
                    <Th>Status</Th>
                    <Th>Area</Th>
                    <Th>Score</Th>
                    <Th>Constraints</Th>
                    <Th>DOER</Th>
                    <Th style={{ width: 60 }} />
                  </tr>
                </thead>
                <tbody>
                  {filteredResults.map((r, i) => (
                    <SiteRow
                      key={r.parcel_id}
                      result={r}
                      rank={i + 1}
                      selected={selectedId === r.parcel_id}
                      hovered={hoveredId === r.parcel_id}
                      onSelect={() => setSelectedId(r.parcel_id)}
                      onHover={(on) => setHoveredId(on ? r.parcel_id : null)}
                    />
                  ))}
                  {filteredResults.length === 0 && tableFilter && (
                    <tr>
                      <td
                        colSpan={9}
                        style={{
                          padding: '24px 16px',
                          textAlign: 'center',
                          fontSize: 13,
                          color: 'var(--text-dim)',
                        }}
                      >
                        No sites match "{tableFilter}"
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            ) : activeQuery && !isLoading ? (
              <EmptyResults query={activeQuery} onChip={handleChip} />
            ) : (
              <ReadyState onChip={handleChip} />
            )}
          </div>

          {/* Footer */}
          {hasResults && (
            <div
              style={{
                padding: '5px 16px',
                borderTop: '1px solid var(--border-soft)',
                background: 'var(--surface)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexShrink: 0,
              }}
            >
              <span className="tnum" style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                Showing {filteredResults.length} of {results.length} sites
              </span>
              {response?.interpreted_filters && (
                <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>
                  {response.interpreted_filters.sub_region ||
                    (response.interpreted_filters.municipalities.length > 0
                      ? `${response.interpreted_filters.municipalities.length} municipalities`
                      : 'MA statewide')}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Table helpers
// ---------------------------------------------------------------------------

function Th({
  children,
  style,
}: {
  children?: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <th
      style={{
        padding: '7px 12px',
        textAlign: 'left',
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color: 'var(--text-dim)',
        whiteSpace: 'nowrap',
        fontFamily: 'var(--sans)',
        ...style,
      }}
    >
      {children}
    </th>
  );
}

const BUCKET_STYLE: Record<string, { bg: string; fg: string; label: string }> = {
  SUITABLE: { bg: '#eaf3eb', fg: '#4a7c4f', label: 'Suitable' },
  'CONDITIONALLY SUITABLE': { bg: '#fdf5e0', fg: '#c08a3e', label: 'Conditional' },
  CONSTRAINED: { bg: '#f5e8e4', fg: '#a85a4a', label: 'Constrained' },
};

const DOER_STYLE: Record<string, { label: string; color: string; bg: string }> = {
  adopted: { label: 'Adopted', color: '#4a7c4f', bg: '#eaf3eb' },
  in_progress: { label: 'In progress', color: '#c08a3e', bg: '#fdf5e0' },
  not_started: { label: 'Not started', color: '#a85a4a', bg: '#f5e8e4' },
};

function SiteRow({
  result,
  rank,
  selected,
  hovered,
  onSelect,
  onHover,
}: {
  result: DiscoverResultItem;
  rank: number;
  selected: boolean;
  hovered: boolean;
  onSelect: () => void;
  onHover: (on: boolean) => void;
}) {
  const nav = useNavigate();
  const bucket = BUCKET_STYLE[result.bucket ?? ''] ?? { bg: 'var(--surface-alt)', fg: 'var(--text-dim)', label: 'Unscored' };
  const doer = DOER_STYLE[result.doer_status ?? ''];

  const constraintFlags = [
    result.in_biomap_core && 'BioMap',
    result.in_nhesp_priority && 'NHESP',
    result.in_flood_zone && 'Flood',
    result.in_wetlands && 'Wetlands',
    result.in_article97 && 'A97',
  ].filter(Boolean) as string[];

  return (
    <tr
      data-id={result.parcel_id}
      onClick={onSelect}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      style={{
        borderBottom: '1px solid var(--border-soft)',
        borderLeft: `3px solid ${result.moratorium_active ? 'var(--rust)' : selected ? 'var(--accent)' : 'transparent'}`,
        background: selected ? 'var(--surface-alt)' : hovered ? 'var(--surface)' : 'transparent',
        cursor: 'pointer',
        transition: 'background 100ms ease',
        opacity: result.moratorium_active ? 0.75 : 1,
      }}
    >
      <td
        className="tnum"
        style={{ padding: '9px 12px 9px 14px', fontSize: 11, color: 'var(--text-faint)', fontWeight: 500 }}
      >
        {rank}
      </td>
      <td
        style={{
          padding: '9px 12px',
          fontSize: 12,
          color: 'var(--text)',
          fontWeight: 500,
          maxWidth: 220,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {result.site_addr || (
          <span style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>Unnamed parcel</span>
        )}
      </td>
      <td style={{ padding: '9px 12px', fontSize: 12, color: 'var(--text-mid)', whiteSpace: 'nowrap' }}>
        {result.town_name}
      </td>
      <td style={{ padding: '9px 12px' }}>
        <span
          style={{
            fontSize: 10,
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: 999,
            background: bucket.bg,
            color: bucket.fg,
            whiteSpace: 'nowrap',
          }}
        >
          {bucket.label}
        </span>
      </td>
      <td
        className="tnum"
        style={{ padding: '9px 12px', fontSize: 12, color: 'var(--text-mid)', whiteSpace: 'nowrap' }}
      >
        {result.lot_size_acres != null ? `${result.lot_size_acres.toFixed(1)} ac` : '—'}
      </td>
      <td
        className="tnum"
        style={{
          padding: '9px 12px',
          fontSize: 12,
          fontWeight: result.total_score != null ? 600 : 400,
          color: result.total_score != null ? 'var(--text)' : 'var(--text-faint)',
          whiteSpace: 'nowrap',
        }}
      >
        {result.total_score != null ? `${Math.round(result.total_score)}/100` : '—'}
      </td>
      <td style={{ padding: '9px 12px' }}>
        {constraintFlags.length > 0 ? (
          <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            {constraintFlags.map((f) => (
              <span
                key={f}
                style={{
                  fontSize: 10,
                  fontWeight: 500,
                  padding: '1px 5px',
                  borderRadius: 999,
                  background: 'var(--surface-alt)',
                  color: 'var(--text-dim)',
                  border: '1px solid var(--border-soft)',
                  whiteSpace: 'nowrap',
                }}
              >
                {f}
              </span>
            ))}
          </div>
        ) : (
          <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>—</span>
        )}
      </td>
      <td style={{ padding: '9px 12px' }}>
        {doer ? (
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              padding: '2px 7px',
              borderRadius: 999,
              background: doer.bg,
              color: doer.color,
              whiteSpace: 'nowrap',
            }}
          >
            {doer.label}
          </span>
        ) : (
          <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>—</span>
        )}
      </td>
      <td style={{ padding: '9px 12px' }}>
        <button
          onClick={(e) => {
            e.stopPropagation();
            nav(`/report/${result.parcel_id}`);
          }}
          style={{
            fontSize: 11,
            fontWeight: 500,
            color: 'var(--accent)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontFamily: 'var(--sans)',
            padding: 0,
            whiteSpace: 'nowrap',
          }}
        >
          View →
        </button>
      </td>
    </tr>
  );
}

function TableSkeleton() {
  return (
    <div style={{ padding: '8px 16px' }}>
      {[1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          style={{
            display: 'flex',
            gap: 12,
            padding: '10px 0',
            borderBottom: '1px solid var(--border-soft)',
            alignItems: 'center',
          }}
        >
          <div style={{ width: 24, height: 11, borderRadius: 3, background: 'var(--surface-alt)', animation: 'pulse 1.5s ease-in-out infinite' }} />
          <div style={{ flex: 1, height: 11, borderRadius: 3, background: 'var(--surface-alt)', animation: 'pulse 1.5s ease-in-out infinite' }} />
          <div style={{ width: 60, height: 11, borderRadius: 3, background: 'var(--surface-alt)', animation: `pulse 1.5s ease-in-out ${i * 0.1}s infinite` }} />
          <div style={{ width: 40, height: 11, borderRadius: 3, background: 'var(--surface-alt)', animation: `pulse 1.5s ease-in-out ${i * 0.1 + 0.1}s infinite` }} />
        </div>
      ))}
      <style>{`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.45; } }`}</style>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Advanced filters (preserved exactly)
// ---------------------------------------------------------------------------

const UTILITIES = ['Eversource', 'National Grid', 'Unitil'];
const SITING_STATUSES = ['planned', 'in_permitting', 'under_construction', 'approved', 'in_service'];
const PROJECT_TYPES = [
  { code: 'bess_standalone', label: 'BESS Standalone' },
  { code: 'bess_colocated', label: 'BESS Co-located' },
  { code: 'solar_ground_mount', label: 'Solar Ground-Mount' },
  { code: 'solar_canopy', label: 'Solar Canopy' },
  { code: 'substation', label: 'Substation' },
];
const DOER_STATUSES = ['adopted', 'in_progress', 'not_started'];

function AdvancedFiltersPanel({
  adv,
  setAdv,
  anchors,
}: {
  adv: AdvancedFilters;
  setAdv: (v: AdvancedFilters) => void;
  anchors: Array<{ id: number; project_name: string; municipality: string | null; mw: number | null }>;
}) {
  return (
    <div
      style={{
        marginTop: 10,
        padding: '14px 16px',
        background: 'var(--surface)',
        border: '1px solid var(--border-soft)',
        borderRadius: 10,
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 12,
      }}
    >
      <Field label="Utility">
        <FSelect value={adv.utility} onChange={(v) => setAdv({ ...adv, utility: v })}>
          <option value="">All utilities</option>
          {UTILITIES.map((u) => <option key={u} value={u}>{u}</option>)}
        </FSelect>
      </Field>

      <Field label="Siting status">
        <FSelect value={adv.siting} onChange={(v) => setAdv({ ...adv, siting: v })}>
          <option value="">Any status</option>
          {SITING_STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
        </FSelect>
      </Field>

      <Field label="Project type">
        <FSelect value={adv.projectType} onChange={(v) => setAdv({ ...adv, projectType: v })}>
          {PROJECT_TYPES.map((pt) => <option key={pt.code} value={pt.code}>{pt.label}</option>)}
        </FSelect>
      </Field>

      <Field label={`ESMP anchor (${anchors.length})`} style={{ gridColumn: '1 / 3' }}>
        <FSelect
          value={adv.anchorId != null ? String(adv.anchorId) : ''}
          onChange={(v) => setAdv({ ...adv, anchorId: v ? Number(v) : null })}
        >
          <option value="">— pick one —</option>
          {anchors.map((a) => (
            <option key={a.id} value={a.id}>
              {a.project_name} · {a.municipality}{a.mw ? ` · ${a.mw} MW` : ''}
            </option>
          ))}
        </FSelect>
      </Field>

      <Field label={`Radius: ${adv.radiusMi} mi`}>
        <input
          type="range" min={0.5} max={10} step={0.5}
          value={adv.radiusMi}
          onChange={(e) => setAdv({ ...adv, radiusMi: Number(e.target.value) })}
          style={{ width: '100%', accentColor: 'var(--accent)' }}
        />
      </Field>

      <Field label="Min acreage">
        <input
          type="number" min={0} step={0.5}
          value={adv.minAcreage}
          onChange={(e) => setAdv({ ...adv, minAcreage: e.target.value })}
          placeholder="e.g. 5"
          style={{
            width: '100%', padding: '8px 10px', fontSize: 13, fontFamily: 'var(--sans)',
            border: '1px solid var(--border)', borderRadius: 8, background: 'var(--bg)',
            color: 'var(--text)', outline: 'none',
          }}
        />
      </Field>

      <Field label="Min score">
        <input
          type="range" min={0} max={100} step={5}
          value={adv.minScore}
          onChange={(e) => setAdv({ ...adv, minScore: Number(e.target.value) })}
          style={{ width: '100%', accentColor: 'var(--accent)' }}
        />
        <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{adv.minScore}/100</span>
      </Field>

      <Field label="DOER status">
        <FSelect value={adv.doerStatus} onChange={(v) => setAdv({ ...adv, doerStatus: v })}>
          <option value="">Any</option>
          {DOER_STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
        </FSelect>
      </Field>

      <div style={{ gridColumn: '1 / -1', display: 'flex', gap: 16, alignItems: 'center' }}>
        <Toggle
          label="Exclude BioMap Core"
          checked={adv.excludeBiomapCore}
          onChange={(v) => setAdv({ ...adv, excludeBiomapCore: v })}
        />
        <Toggle
          label="Exclude NHESP Priority"
          checked={adv.excludeNhespPriority}
          onChange={(v) => setAdv({ ...adv, excludeNhespPriority: v })}
        />
      </div>
    </div>
  );
}

function Field({
  label,
  children,
  style,
}: {
  label: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 5, ...style }}>
      <span className="label">{label}</span>
      {children}
    </label>
  );
}

function FSelect({
  value,
  onChange,
  disabled,
  children,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div style={{ position: 'relative' }}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        style={{
          width: '100%', padding: '8px 28px 8px 10px', fontSize: 13,
          fontFamily: 'inherit', background: 'var(--bg)', border: '1px solid var(--border)',
          borderRadius: 8, outline: 'none', color: 'var(--text)',
          appearance: 'none', cursor: 'pointer',
        }}
      >
        {children}
      </select>
      <span
        aria-hidden
        style={{
          position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
          color: 'var(--text-dim)', fontSize: 11, pointerEvents: 'none',
        }}
      >
        ▾
      </span>
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 12, color: 'var(--text-mid)' }}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        style={{ accentColor: 'var(--accent)', width: 14, height: 14 }}
      />
      {label}
    </label>
  );
}

// ---------------------------------------------------------------------------
// Empty / ready states
// ---------------------------------------------------------------------------

function ReadyState({ onChip }: { onChip: (c: string) => void }) {
  return (
    <div style={{ padding: '32px 20px', textAlign: 'center' }}>
      <div className="display" style={{ fontSize: 17, marginBottom: 8, color: 'var(--text)' }}>
        Discover sites with potential
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.6, margin: '0 0 16px' }}>
        Type a natural language query above, or pick an example to get started.
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center' }}>
        {EXAMPLE_CHIPS.map((chip) => (
          <button
            key={chip}
            onClick={() => onChip(chip)}
            style={{
              fontSize: 12, fontWeight: 500, fontFamily: 'var(--sans)',
              padding: '4px 12px', borderRadius: 999,
              border: '1px solid var(--border)', background: 'var(--surface-alt)',
              color: 'var(--accent)', cursor: 'pointer',
            }}
          >
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}

function EmptyResults({ query, onChip }: { query: string; onChip: (c: string) => void }) {
  const suggestions = [
    'Expand to all EMA regions',
    'Try solar instead of BESS',
    'Remove habitat exclusions',
    'Lower the minimum acreage',
  ];
  return (
    <div style={{ padding: '28px 20px' }}>
      <div className="display" style={{ fontSize: 16, marginBottom: 6, color: 'var(--text)' }}>
        No parcels matched
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.6, margin: '0 0 14px' }}>
        The filters applied to "{query}" returned no results. Try relaxing one constraint.
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => onChip(s)}
            style={{
              fontSize: 11, fontWeight: 500, fontFamily: 'var(--sans)',
              padding: '4px 10px', borderRadius: 999,
              border: '1px solid var(--border)', background: 'var(--surface-alt)',
              color: 'var(--accent)', cursor: 'pointer',
            }}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
