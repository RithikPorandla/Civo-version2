import { useLocation } from 'react-router-dom';
import { IconBell, IconClock, IconSearch, IconStar, IconSun } from './Icon';

/**
 * Dashboard top bar: breadcrumb on the left, search + utility icons on
 * the right. Sticky so it stays visible as the main content scrolls.
 *
 * Breadcrumb is derived from the current pathname so every route gets
 * a label for free — "/report/111" → "Report / 111".
 */
export default function TopBar() {
  const { pathname } = useLocation();
  const segments = pathname.split('/').filter(Boolean);
  const crumbs = segments.length === 0 ? ['Dashboards', 'Overview'] : ['Dashboards', ...segments.map(niceSegment)];

  return (
    <header
      style={{
        height: 56,
        padding: '0 24px',
        background: '#f7f8fa',
        borderBottom: '1px solid #e8eaed',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 20,
      }}
    >
      {/* Left: breadcrumb + favorite */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <IconButton aria-label="Favorite">
          <IconStar size={16} />
        </IconButton>
        <nav
          aria-label="Breadcrumb"
          style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}
        >
          {crumbs.map((c, i) => (
            <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <span
                style={{
                  color: i === crumbs.length - 1 ? '#1a1a1a' : '#8a8a8a',
                }}
              >
                {c}
              </span>
              {i < crumbs.length - 1 && (
                <span style={{ color: '#c8cace' }}>/</span>
              )}
            </span>
          ))}
        </nav>
      </div>

      {/* Right: search + utility icons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '7px 12px',
            background: '#ffffff',
            border: '1px solid #e8eaed',
            borderRadius: 8,
            minWidth: 240,
            color: '#8a8a8a',
            fontSize: 13,
          }}
        >
          <IconSearch size={14} />
          <span style={{ flex: 1 }}>Search</span>
          <kbd
            style={{
              fontFamily: 'inherit',
              fontSize: 11,
              padding: '1px 6px',
              borderRadius: 4,
              background: '#f1f2f4',
              color: '#8a8a8a',
            }}
          >
            ⌘/
          </kbd>
        </div>
        <IconButton aria-label="Theme">
          <IconSun size={16} />
        </IconButton>
        <IconButton aria-label="History">
          <IconClock size={16} />
        </IconButton>
        <IconButton aria-label="Notifications">
          <IconBell size={16} />
        </IconButton>
      </div>
    </header>
  );
}

function IconButton({ children, ...rest }: React.ComponentProps<'button'>) {
  return (
    <button
      {...rest}
      style={{
        width: 32,
        height: 32,
        borderRadius: 8,
        border: 'none',
        background: 'transparent',
        color: '#525252',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        transition: 'background 120ms ease',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = '#f1f2f4')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      {children}
    </button>
  );
}

function niceSegment(s: string): string {
  // "solar_ground_mount" → "Solar Ground Mount"
  if (/^\d+$/.test(s)) return s;
  return s
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}
