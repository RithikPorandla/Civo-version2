import { NavLink } from 'react-router-dom';
import {
  IconHome,
  IconMap,
  IconSearch,
  IconChart,
  IconBuilding,
  IconSidebar,
} from './Icon';
import BrandMark from './BrandMark';

interface Props {
  collapsed: boolean;
  onToggle: () => void;
}

const NAV_ITEMS: Array<{ to: string; label: string; Icon: typeof IconHome; end?: boolean }> = [
  { to: '/app', label: 'Overview', Icon: IconHome, end: true },
  { to: '/app/lookup', label: 'Address Lookup', Icon: IconMap },
  { to: '/app/discover', label: 'Discover Sites', Icon: IconSearch },
  { to: '/app/suitability', label: 'Site Suitability', Icon: IconChart },
  { to: '/municipalities', label: 'Municipalities', Icon: IconBuilding },
];

export default function Sidebar({ collapsed, onToggle }: Props) {
  const width = collapsed ? 72 : 248;

  return (
    <aside
      className="border-r hairline"
      style={{
        width,
        minHeight: '100vh',
        position: 'sticky',
        top: 0,
        transition: 'width 180ms ease',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surface)',
      }}
    >
      {/* Brand row */}
      <NavLink
        to="/app"
        end
        style={{
          padding: collapsed ? '20px 0' : '22px 22px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          justifyContent: collapsed ? 'center' : 'flex-start',
          textDecoration: 'none',
          color: 'var(--text)',
        }}
      >
        <BrandMark size={collapsed ? 22 : 24} />
        {!collapsed && (
          <span
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 22,
              fontWeight: 500,
              letterSpacing: '-0.025em',
              lineHeight: 1,
            }}
          >
            Civo
          </span>
        )}
      </NavLink>

      <nav style={{ padding: collapsed ? '6px 12px' : '4px 12px 8px' }}>
        {NAV_ITEMS.map((i) => (
          <NavLink
            key={i.to}
            to={i.to}
            end={i.end}
            title={collapsed ? i.label : undefined}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: collapsed ? '8px 0' : '8px 10px',
              borderRadius: 8,
              textDecoration: 'none',
              color: 'var(--text)',
              background: isActive ? 'var(--bg)' : 'transparent',
              boxShadow: isActive
                ? '0 1px 0 var(--border) inset, 0 1px 2px rgba(0,0,0,0.03)'
                : 'none',
              fontSize: 13,
              fontWeight: isActive ? 500 : 400,
              justifyContent: collapsed ? 'center' : 'flex-start',
              lineHeight: 1.3,
              marginBottom: 2,
              transition: 'background 120ms ease',
            })}
          >
            {({ isActive }) => (
              <>
                <i.Icon size={14} className={isActive ? 'text-accent' : 'text-textMid'} />
                {!collapsed && (
                  <span style={{ flex: 1 }}>{i.label}</span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Collapse toggle — pinned bottom */}
      <div
        style={{
          marginTop: 'auto',
          padding: '10px',
          borderTop: '1px solid var(--border-soft)',
          display: 'flex',
          justifyContent: collapsed ? 'center' : 'flex-end',
        }}
      >
        <button
          onClick={onToggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand' : 'Collapse'}
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            border: 'none',
            background: 'transparent',
            color: 'var(--text-dim)',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background 120ms ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-alt)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <IconSidebar size={18} />
        </button>
      </div>
    </aside>
  );
}
