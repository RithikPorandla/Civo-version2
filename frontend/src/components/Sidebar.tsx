import { NavLink } from 'react-router-dom';
import {
  IconHome,
  IconMap,
  IconSearch,
  IconChart,
  IconBuilding,
  IconFolder,
  IconSidebar,
  IconSettings,
  IconHelpCircle,
} from './Icon';
import BrandMark from './BrandMark';

interface Props {
  collapsed: boolean;
  onToggle: () => void;
}

const SIDEBAR_BG = '#8b7355';
const INACTIVE_COLOR = 'rgba(255,255,255,0.68)';
const ACTIVE_BG = 'rgba(255,255,255,0.14)';
const DIVIDER = 'rgba(255,255,255,0.12)';

const NAV_ITEMS: Array<{ to: string; label: string; Icon: typeof IconHome; end?: boolean }> = [
  { to: '/app',             label: 'Dashboard',        Icon: IconHome,     end: true },
  { to: '/app/lookup',      label: 'Address Lookup',   Icon: IconMap               },
  { to: '/app/suitability', label: 'Suitability',      Icon: IconChart             },
  { to: '/app/discover',    label: 'Discover Sites',   Icon: IconSearch            },
  { to: '/municipalities',  label: 'Municipalities',   Icon: IconBuilding          },
  { to: '/app/portfolio',   label: 'Portfolio',        Icon: IconFolder            },
];

const BOTTOM_ITEMS: Array<{ label: string; Icon: typeof IconHome }> = [
  { label: 'Settings', Icon: IconSettings  },
  { label: 'Help',     Icon: IconHelpCircle },
];

export default function Sidebar({ collapsed, onToggle }: Props) {
  const width = collapsed ? 64 : 236;

  return (
    <aside
      style={{
        width,
        height: '100vh',
        position: 'sticky',
        top: 0,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        background: SIDEBAR_BG,
        borderRight: '1px solid rgba(0,0,0,0.14)',
        overflowY: 'auto',
        overflowX: 'hidden',
        transition: 'width 180ms ease',
        zIndex: 30,
      }}
    >
      {/* Brand row — same height as TopBar (56px) */}
      <NavLink
        to="/app"
        end
        style={{
          height: 56,
          flexShrink: 0,
          padding: collapsed ? '0' : '0 20px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          justifyContent: collapsed ? 'center' : 'flex-start',
          textDecoration: 'none',
          color: '#ffffff',
          borderBottom: `1px solid ${DIVIDER}`,
        }}
      >
        <BrandMark size={22} color="#ffffff" />
        {!collapsed && (
          <span
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 20,
              fontWeight: 500,
              letterSpacing: '-0.025em',
              lineHeight: 1,
              color: '#ffffff',
            }}
          >
            Civo
          </span>
        )}
      </NavLink>

      {/* Primary nav */}
      <nav style={{ padding: '8px 8px', flex: 1 }}>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            title={collapsed ? item.label : undefined}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 9,
              padding: collapsed ? '8px 0' : '8px 10px',
              borderRadius: 7,
              textDecoration: 'none',
              color: isActive ? '#ffffff' : INACTIVE_COLOR,
              background: isActive ? ACTIVE_BG : 'transparent',
              boxShadow: isActive && !collapsed ? 'inset 2px 0 0 var(--gold)' : 'none',
              fontSize: 12.5,
              fontWeight: isActive ? 500 : 400,
              justifyContent: collapsed ? 'center' : 'flex-start',
              lineHeight: 1.3,
              marginBottom: 1,
              transition: 'background 120ms ease, color 120ms ease, box-shadow 120ms ease',
            })}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLAnchorElement;
              if (el.getAttribute('aria-current') !== 'page') {
                el.style.background = 'rgba(255,255,255,0.08)';
                el.style.color = '#ffffff';
              }
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLAnchorElement;
              if (el.getAttribute('aria-current') !== 'page') {
                el.style.background = 'transparent';
                el.style.color = INACTIVE_COLOR;
              }
            }}
          >
            {({ isActive: _ }) => (
              <>
                <item.Icon size={14} />
                {!collapsed && <span style={{ flex: 1 }}>{item.label}</span>}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Bottom utility */}
      <div style={{ borderTop: `1px solid ${DIVIDER}`, padding: '8px 8px' }}>
        {BOTTOM_ITEMS.map((item) => (
          <button
            key={item.label}
            title={collapsed ? item.label : undefined}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 9,
              width: '100%',
              padding: collapsed ? '8px 0' : '8px 10px',
              borderRadius: 7,
              border: 'none',
              background: 'transparent',
              color: INACTIVE_COLOR,
              fontSize: 12.5,
              fontWeight: 400,
              justifyContent: collapsed ? 'center' : 'flex-start',
              cursor: 'pointer',
              marginBottom: 1,
              fontFamily: "'Inter', ui-sans-serif, system-ui, sans-serif",
              transition: 'background 120ms ease, color 120ms ease',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.08)';
              (e.currentTarget as HTMLButtonElement).style.color = '#ffffff';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
              (e.currentTarget as HTMLButtonElement).style.color = INACTIVE_COLOR;
            }}
          >
            <item.Icon size={14} />
            {!collapsed && <span>{item.label}</span>}
          </button>
        ))}
      </div>

      {/* User avatar */}
      <div
        style={{
          borderTop: `1px solid ${DIVIDER}`,
          padding: collapsed ? '12px 0' : '12px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 9,
          justifyContent: collapsed ? 'center' : 'flex-start',
          flexShrink: 0,
        }}
      >
        <div
          aria-label="User: Rithik P."
          style={{
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: 'var(--gold)',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--accent-deep)',
            fontSize: 10.5,
            fontWeight: 600,
            letterSpacing: '0.02em',
            flexShrink: 0,
            fontFamily: "'Inter', ui-sans-serif, system-ui, sans-serif",
          }}
        >
          RP
        </div>
        {!collapsed && (
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: 12.5,
                fontWeight: 500,
                color: '#ffffff',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                lineHeight: 1.3,
              }}
            >
              Rithik P.
            </div>
            <div style={{ fontSize: 11, color: INACTIVE_COLOR, marginTop: 1 }}>
              Professional
            </div>
          </div>
        )}
      </div>

      {/* Collapse toggle */}
      <div
        style={{
          padding: '6px 8px',
          borderTop: `1px solid ${DIVIDER}`,
          display: 'flex',
          justifyContent: collapsed ? 'center' : 'flex-end',
          flexShrink: 0,
        }}
      >
        <button
          onClick={onToggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand' : 'Collapse'}
          style={{
            width: 30,
            height: 30,
            borderRadius: 7,
            border: 'none',
            background: 'transparent',
            color: INACTIVE_COLOR,
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background 120ms ease, color 120ms ease',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.10)';
            (e.currentTarget as HTMLButtonElement).style.color = '#ffffff';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
            (e.currentTarget as HTMLButtonElement).style.color = INACTIVE_COLOR;
          }}
        >
          <IconSidebar size={16} />
        </button>
      </div>
    </aside>
  );
}
