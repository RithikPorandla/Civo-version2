import { Link, useLocation } from 'react-router-dom';
import BrandMark from './BrandMark';

/**
 * Deep espresso nav — dark brown (near black) band used across all
 * three pages. Cream type, pill CTA.
 */
export default function SiteHeader() {
  const { pathname } = useLocation();

  const links: Array<{ to: string; label: string }> = [
    { to: '/', label: 'Home' },
    { to: '/score', label: 'Score a site' },
    { to: '/report/1', label: 'Sample report' },
  ];

  return (
    <header
      style={{
        background: 'var(--accent-dark)',
        color: '#faf8f3',
        position: 'sticky',
        top: 0,
        zIndex: 20,
        borderBottom: '1px solid rgba(250,248,243,0.06)',
      }}
    >
      <div
        style={{
          maxWidth: 1280,
          margin: '0 auto',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 32px',
        }}
      >
        <Link
          to="/"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            textDecoration: 'none',
            color: 'inherit',
          }}
        >
          <BrandMark size={24} color="#faf8f3" />
          <span
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 21,
              fontWeight: 500,
              letterSpacing: '-0.025em',
            }}
          >
            Civo
          </span>
        </Link>

        <nav
          aria-label="Primary"
          style={{
            display: 'flex',
            gap: 28,
            fontSize: 13,
            letterSpacing: '0.01em',
            fontWeight: 500,
          }}
        >
          {links.map((l) => {
            const active =
              pathname === l.to || (l.to === '/report/1' && pathname.startsWith('/report'));
            return (
              <Link
                key={l.to}
                to={l.to}
                style={{
                  color: active ? '#faf8f3' : 'rgba(250,248,243,0.62)',
                  textDecoration: 'none',
                  transition: 'color 150ms ease',
                  paddingBottom: 2,
                  borderBottom: active ? '1px solid rgba(250,248,243,0.9)' : '1px solid transparent',
                }}
                onMouseEnter={(e) => {
                  if (!active) e.currentTarget.style.color = '#faf8f3';
                }}
                onMouseLeave={(e) => {
                  if (!active) e.currentTarget.style.color = 'rgba(250,248,243,0.62)';
                }}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        <Link
          to="/score"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '9px 18px',
            background: '#faf8f3',
            color: 'var(--accent-dark)',
            borderRadius: 999,
            fontSize: 13,
            fontWeight: 600,
            letterSpacing: '0.005em',
            textDecoration: 'none',
            transition: 'transform 150ms ease, filter 150ms ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-1px)';
            e.currentTarget.style.filter = 'brightness(1.02)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'none';
            e.currentTarget.style.filter = 'none';
          }}
        >
          Try Civo →
        </Link>
      </div>
    </header>
  );
}
