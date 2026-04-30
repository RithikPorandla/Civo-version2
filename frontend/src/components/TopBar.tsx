import { useLocation } from 'react-router-dom';
import { IconBell } from './Icon';

export default function TopBar() {
  const { pathname } = useLocation();
  const segments = pathname.split('/').filter((s) => s && s !== 'app');
  const crumbs = segments.length === 0 ? ['Overview'] : segments.map(niceSegment);

  return (
    <header
      style={{
        height: 56,
        padding: '0 32px',
        background: 'var(--bg)',
        borderBottom: '1px solid var(--border-soft)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 20,
        flexShrink: 0,
      }}
    >
      {/* Breadcrumb */}
      <nav
        aria-label="Breadcrumb"
        style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5 }}
      >
        {crumbs.map((c, i) => (
          <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                color: i === crumbs.length - 1 ? 'var(--text)' : 'var(--text-soft)',
                fontWeight: i === crumbs.length - 1 ? 500 : 400,
              }}
            >
              {c}
            </span>
            {i < crumbs.length - 1 && (
              <span style={{ color: 'var(--text-faint)', fontSize: 11 }}>/</span>
            )}
          </span>
        ))}
      </nav>

      {/* Right: notifications */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <TopBarIconBtn aria-label="Notifications">
          <IconBell size={13} />
        </TopBarIconBtn>
      </div>
    </header>
  );
}

function TopBarIconBtn({ children, ...rest }: React.ComponentProps<'button'>) {
  return (
    <button
      {...rest}
      style={{
        width: 30,
        height: 30,
        borderRadius: 7,
        border: '1px solid transparent',
        background: 'transparent',
        color: 'var(--text-mid)',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        transition: 'background 120ms ease',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-alt)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      {children}
    </button>
  );
}

function niceSegment(s: string): string {
  if (/^\d+$/.test(s)) return s;
  return s
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}
