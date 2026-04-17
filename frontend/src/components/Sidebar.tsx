import { NavLink } from 'react-router-dom';
import {
  IconChart,
  IconChevronRight,
  IconHome,
  IconMap,
  IconBuilding,
  IconBook,
  IconSidebar,
} from './Icon';

interface Props {
  collapsed: boolean;
  onToggle: () => void;
}

const DASHBOARD_ITEMS: Array<{ to: string; label: string; Icon: typeof IconHome }> = [
  { to: '/', label: 'Overview', Icon: IconHome },
  { to: '/lookup', label: 'Address Lookup', Icon: IconMap },
  { to: '/suitability', label: 'Site Suitability', Icon: IconChart },
];

const PAGES_ITEMS: Array<{ to: string; label: string; Icon: typeof IconHome }> = [
  { to: '/municipalities', label: 'Municipalities', Icon: IconBuilding },
];

const METHODOLOGY_ITEMS: Array<{ label: string; Icon: typeof IconHome }> = [
  { label: '225 CMR 29.00', Icon: IconBook },
  { label: 'DOER Model Bylaws', Icon: IconBook },
];

export default function Sidebar({ collapsed, onToggle }: Props) {
  const width = collapsed ? 72 : 248;

  return (
    <aside
      className="bg-surface border-r hairline"
      style={{
        width,
        minHeight: '100vh',
        position: 'sticky',
        top: 0,
        transition: 'width 180ms ease',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Brand row */}
      <div
        style={{
          padding: collapsed ? '20px 0' : '18px 22px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
        }}
      >
        <img
          src="/civo-logo.png"
          alt="Civo"
          style={{
            height: collapsed ? 22 : 28,
            width: 'auto',
            display: 'block',
          }}
        />
      </div>

      {!collapsed && (
        <div style={{ padding: '4px 22px 10px', display: 'flex', gap: 16 }}>
          <span className="text-textDim" style={{ fontSize: 12 }}>
            Favorites
          </span>
          <span className="text-textDim" style={{ fontSize: 12 }}>
            Recently
          </span>
        </div>
      )}

      {!collapsed && (
        <div style={{ padding: '2px 22px 8px' }}>
          <FavItem label="Overview" />
          <FavItem label="Projects" />
        </div>
      )}

      <NavGroup title="Dashboards" items={DASHBOARD_ITEMS} collapsed={collapsed} />
      <NavGroup title="Pages" items={PAGES_ITEMS} collapsed={collapsed} />

      {!collapsed && (
        <div style={{ padding: '6px 12px 8px' }}>
          <div
            style={{
              padding: '0 10px 6px',
              fontSize: 11,
              color: '#8a8a8a',
              fontWeight: 500,
              textTransform: 'uppercase',
              letterSpacing: 0.4,
            }}
          >
            Methodology
          </div>
          {METHODOLOGY_ITEMS.map((m) => (
            <div
              key={m.label}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '7px 10px',
                fontSize: 13,
                color: '#8a8a8a',
                borderRadius: 6,
                cursor: 'default',
              }}
            >
              <m.Icon size={16} />
              <span>{m.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Collapse toggle — pinned bottom */}
      <div
        style={{
          marginTop: 'auto',
          padding: '10px',
          borderTop: '1px solid #e8eaed',
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
            color: '#525252',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background 120ms ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = '#f4f5f7')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <IconSidebar size={18} />
        </button>
      </div>
    </aside>
  );
}

function FavItem({ label }: { label: string }) {
  return (
    <div
      style={{
        padding: '6px 10px',
        fontSize: 13,
        color: '#525252',
        borderRadius: 6,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 4,
          height: 4,
          borderRadius: 100,
          background: '#c8cace',
        }}
      />
      {label}
    </div>
  );
}

function NavGroup({
  title,
  items,
  collapsed,
}: {
  title: string;
  items: Array<{ to: string; label: string; Icon: typeof IconHome }>;
  collapsed: boolean;
}) {
  return (
    <div style={{ padding: collapsed ? '6px 12px' : '6px 12px 8px' }}>
      {!collapsed && (
        <div
          style={{
            padding: '0 10px 6px',
            fontSize: 11,
            color: '#8a8a8a',
            fontWeight: 500,
            textTransform: 'uppercase',
            letterSpacing: 0.4,
          }}
        >
          {title}
        </div>
      )}
      {items.map((i) => (
        <NavLink
          key={i.to}
          to={i.to}
          end={i.to === '/'}
          title={collapsed ? i.label : undefined}
          style={({ isActive }) => ({
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: collapsed ? '8px 0' : '8px 10px',
            borderRadius: 8,
            textDecoration: 'none',
            color: isActive ? '#1a1a1a' : '#525252',
            background: isActive ? '#f1f2f4' : 'transparent',
            fontSize: 13,
            fontWeight: isActive ? 500 : 400,
            justifyContent: collapsed ? 'center' : 'flex-start',
            transition: 'background 120ms ease, color 120ms ease',
          })}
        >
          <i.Icon size={16} />
          {!collapsed && (
            <>
              <span style={{ flex: 1 }}>{i.label}</span>
              <IconChevronRight size={12} className="text-textFaint" />
            </>
          )}
        </NavLink>
      ))}
    </div>
  );
}
