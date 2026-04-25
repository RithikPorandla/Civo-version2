import { useState } from 'react';
import { IconLayers, IconPlus } from './Icon';

const LAYER_GROUPS = [
  { id: 'parcels', label: 'Parcel Boundaries' },
  { id: 'environmental', label: 'Environmental' },
  { id: 'flood', label: 'Flood Zones' },
  { id: 'article97', label: 'Article 97 Lands' },
  { id: 'esmp', label: 'ESMP Projects' },
] as const;

interface Props {
  basemap: 'street' | 'satellite';
  onBasemapChange: (b: 'street' | 'satellite') => void;
  enabled: Set<string>;
  onToggle: (id: string) => void;
}

export function LayersPanel({ basemap, onBasemapChange, enabled, onToggle }: Props) {
  const [search, setSearch] = useState('');
  const [collapsed, setCollapsed] = useState(false);

  const filtered = search
    ? LAYER_GROUPS.filter((g) => g.label.toLowerCase().includes(search.toLowerCase()))
    : LAYER_GROUPS;

  const activeCount = enabled.size;

  return (
    <div
      style={{
        position: 'absolute',
        top: 12,
        left: 12,
        zIndex: 20,
        width: 236,
        background: 'var(--bg)',
        borderRadius: 12,
        boxShadow: '0 4px 24px rgba(0,0,0,0.14), 0 1px 4px rgba(0,0,0,0.08)',
        border: '1px solid var(--border-soft)',
        overflow: 'hidden',
        fontFamily: 'var(--sans)',
        userSelect: 'none',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '10px 12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: collapsed ? 'none' : '1px solid var(--border-soft)',
          background: 'var(--surface)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <IconLayers size={13} className="text-textMid" />
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>Layers</span>
          {activeCount > 0 && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: 'var(--accent)',
                background: 'var(--surface-alt)',
                border: '1px solid var(--border)',
                borderRadius: 999,
                padding: '1px 7px',
                lineHeight: '16px',
              }}
            >
              {activeCount}
            </span>
          )}
        </div>
        <button
          onClick={() => setCollapsed(!collapsed)}
          style={{
            width: 24,
            height: 24,
            borderRadius: 6,
            border: 'none',
            background: 'transparent',
            color: 'var(--text-dim)',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-alt)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          title={collapsed ? 'Expand' : 'Collapse'}
        >
          {collapsed ? <IconPlus size={13} /> : <span style={{ fontSize: 13, lineHeight: 1 }}>✕</span>}
        </button>
      </div>

      {!collapsed && (
        <>
          {/* Search */}
          <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--border-soft)' }}>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search layers…"
              style={{
                width: '100%',
                border: '1px solid var(--border)',
                borderRadius: 6,
                padding: '5px 10px',
                fontSize: 12,
                fontFamily: 'var(--sans)',
                outline: 'none',
                color: 'var(--text)',
                background: 'var(--surface)',
                boxSizing: 'border-box',
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
              onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
            />
          </div>

          {/* Basemap */}
          <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border-soft)' }}>
            <div className="label" style={{ marginBottom: 6 }}>Basemap</div>
            <div style={{ display: 'flex', gap: 5 }}>
              {(['street', 'satellite'] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => onBasemapChange(mode)}
                  style={{
                    flex: 1,
                    padding: '5px 8px',
                    fontSize: 11,
                    fontWeight: 500,
                    border: '1px solid',
                    borderColor: basemap === mode ? 'var(--accent)' : 'var(--border)',
                    background: basemap === mode ? 'var(--surface-alt)' : 'var(--bg)',
                    color: basemap === mode ? 'var(--accent)' : 'var(--text-mid)',
                    borderRadius: 6,
                    cursor: 'pointer',
                    fontFamily: 'var(--sans)',
                    transition: 'all 120ms ease',
                  }}
                >
                  {mode.charAt(0).toUpperCase() + mode.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Data layers */}
          <div style={{ padding: '6px 0 6px' }}>
            <div className="label" style={{ padding: '2px 12px 6px' }}>Data Layers</div>
            {filtered.map((g) => (
              <LayerRow
                key={g.id}
                label={g.label}
                enabled={enabled.has(g.id)}
                onToggle={() => onToggle(g.id)}
              />
            ))}
            {filtered.length === 0 && (
              <div style={{ padding: '8px 12px', fontSize: 12, color: 'var(--text-dim)' }}>
                No layers match
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function LayerRow({
  label,
  enabled,
  onToggle,
}: {
  label: string;
  enabled: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      onClick={onToggle}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 12px',
        cursor: 'pointer',
        transition: 'background 100ms ease',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      <span
        style={{
          fontSize: 12,
          color: enabled ? 'var(--text)' : 'var(--text-mid)',
          fontWeight: enabled ? 500 : 400,
        }}
      >
        {label}
      </span>
      <ToggleSwitch checked={enabled} />
    </div>
  );
}

function ToggleSwitch({ checked }: { checked: boolean }) {
  return (
    <div
      role="switch"
      aria-checked={checked}
      style={{
        width: 30,
        height: 17,
        borderRadius: 999,
        background: checked ? 'var(--accent)' : 'var(--border)',
        position: 'relative',
        transition: 'background 150ms ease',
        flexShrink: 0,
      }}
    >
      <span
        style={{
          position: 'absolute',
          top: 2,
          left: checked ? 15 : 2,
          width: 13,
          height: 13,
          borderRadius: '50%',
          background: '#fff',
          boxShadow: '0 1px 2px rgba(0,0,0,0.2)',
          transition: 'left 150ms ease',
          display: 'block',
        }}
      />
    </div>
  );
}
