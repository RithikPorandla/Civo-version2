import { useNavigate } from 'react-router-dom';
import type { DiscoverResultItem } from '../lib/api';

const BUCKET_COLOR: Record<string, string> = {
  SUITABLE: 'var(--sage)',
  'CONDITIONALLY SUITABLE': 'var(--gold)',
  CONSTRAINED: 'var(--rust)',
};

const DOER_LABEL: Record<string, string> = {
  adopted: 'DOER ✓',
  in_progress: 'DOER ~',
  not_started: 'DOER ✗',
  unknown: 'DOER ?',
};
const DOER_COLOR: Record<string, { bg: string; fg: string }> = {
  adopted:     { bg: '#eaf3eb', fg: 'var(--sage)' },
  in_progress: { bg: '#fdf5e0', fg: 'var(--gold)' },
  not_started: { bg: '#f5e8e4', fg: 'var(--rust)' },
  unknown:     { bg: 'var(--surface-alt)', fg: 'var(--text-faint)' },
};

interface Props {
  result: DiscoverResultItem;
  rank: number;
  selected: boolean;
  hovered: boolean;
  onSelect: () => void;
  onHover: (on: boolean) => void;
}

export function DiscoverResultCard({ result, rank, selected, hovered, onSelect, onHover }: Props) {
  const nav = useNavigate();

  const bucketColor = BUCKET_COLOR[result.bucket || ''] || 'var(--text-dim)';

  const constraintFlags = [
    result.in_biomap_core && 'BioMap Core',
    result.in_nhesp_priority && 'NHESP Priority',
    result.in_flood_zone && 'Flood Zone',
    result.in_wetlands && 'Wetlands',
    result.in_article97 && 'Article 97',
  ].filter(Boolean) as string[];

  const doerColors = DOER_COLOR[result.doer_status || ''] ?? DOER_COLOR['unknown'];

  return (
    <div
      onClick={onSelect}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      style={{
        padding: '14px 16px',
        borderBottom: '1px solid var(--border-soft)',
        cursor: 'pointer',
        background: selected ? '#faf7f2' : hovered ? 'var(--surface)' : 'var(--bg)',
        borderLeft: result.moratorium_active
          ? '3px solid var(--rust)'
          : selected
          ? '3px solid var(--accent)'
          : '3px solid transparent',
        transition: 'background 100ms ease, border-left-color 100ms ease',
        display: 'flex',
        gap: 14,
        alignItems: 'flex-start',
        opacity: result.moratorium_active ? 0.7 : 1,
      }}
    >
      {/* Rank + score */}
      <div style={{ flexShrink: 0, textAlign: 'center', width: 44 }}>
        <div
          className="tnum"
          style={{ fontSize: 11, color: 'var(--text-faint)', fontWeight: 500, marginBottom: 4 }}
        >
          #{rank}
        </div>
        {result.total_score != null ? (
          <div
            style={{
              fontFamily: 'var(--display)',
              fontSize: 22,
              fontWeight: 400,
              letterSpacing: '-0.02em',
              lineHeight: 1,
              color: bucketColor,
            }}
          >
            {Math.round(result.total_score)}
          </div>
        ) : (
          <div style={{ fontSize: 12, color: 'var(--text-faint)', fontStyle: 'italic' }}>—</div>
        )}
        {result.bucket && (
          <div
            style={{
              fontSize: 9,
              fontWeight: 600,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              color: bucketColor,
              marginTop: 3,
              lineHeight: 1.2,
            }}
          >
            {result.bucket === 'CONDITIONALLY SUITABLE' ? 'Conditional' : result.bucket}
          </div>
        )}
      </div>

      {/* Main content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: 'var(--text)',
            lineHeight: 1.3,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {result.site_addr || '(no address)'}
        </div>
        <div
          className="tnum"
          style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}
        >
          {result.town_name}
          {result.lot_size_acres != null && ` · ${result.lot_size_acres.toFixed(1)} ac`}
        </div>

        {/* Moratorium banner */}
        {result.moratorium_active && (
          <div
            style={{
              marginTop: 6,
              fontSize: 10,
              fontWeight: 600,
              color: 'var(--rust)',
              letterSpacing: '0.02em',
            }}
          >
            ⚠ Active moratorium — permitting blocked
          </div>
        )}

        {/* Primary constraint */}
        {result.primary_constraint && !result.moratorium_active && (
          <div style={{ fontSize: 11, color: 'var(--text-mid)', marginTop: 6, lineHeight: 1.4 }}>
            {result.primary_constraint}
          </div>
        )}

        {/* Jurisdiction + constraint pill row */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
          {/* DOER status pill */}
          {result.doer_status && result.doer_status !== 'unknown' && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                padding: '2px 7px',
                borderRadius: 999,
                background: doerColors.bg,
                color: doerColors.fg,
                letterSpacing: '0.01em',
              }}
            >
              {DOER_LABEL[result.doer_status] ?? 'DOER ?'}
            </span>
          )}

          {/* Constraint flags */}
          {constraintFlags.map((f) => (
            <span
              key={f}
              style={{
                fontSize: 10,
                fontWeight: 500,
                padding: '2px 7px',
                borderRadius: 999,
                background: '#f5e8e4',
                color: 'var(--rust)',
                letterSpacing: '0.01em',
              }}
            >
              {f}
            </span>
          ))}
        </div>

        {/* Actions */}
        <div style={{ marginTop: 8, display: 'flex', gap: 6 }}>
          <button
            className="btn btn-ghost"
            style={{ fontSize: 11, padding: '4px 10px', height: 'auto' }}
            onClick={(e) => {
              e.stopPropagation();
              const addr = result.site_addr
                ? `${result.site_addr}, ${result.town_name}, MA`
                : null;
              if (addr) nav(`/app/lookup?q=${encodeURIComponent(addr)}`);
            }}
          >
            Open report →
          </button>
        </div>
      </div>
    </div>
  );
}
