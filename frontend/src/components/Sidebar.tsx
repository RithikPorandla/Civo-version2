import { NavLink } from 'react-router-dom';

const items: Array<{ to: string; label: string; eyebrow: string }> = [
  { to: '/', label: 'Overview', eyebrow: '01' },
  { to: '/lookup', label: 'Address Lookup', eyebrow: '02' },
  { to: '/municipalities', label: 'Municipalities', eyebrow: '03' },
  { to: '/suitability', label: 'Site Suitability', eyebrow: '04' },
];

export default function Sidebar() {
  return (
    <aside
      className="border-r hairline bg-surface"
      style={{ width: 260, minHeight: '100vh', position: 'sticky', top: 0 }}
    >
      <div className="px-6 pt-8 pb-10">
        <div className="display text-[24px] tracking-tight">
          Civo<span className="text-accent italic">.</span>
        </div>
        <div className="eyebrow mt-2" style={{ fontSize: 11 }}>
          MA Permitting Intelligence
        </div>
      </div>

      <nav className="px-3 flex flex-col gap-1">
        {items.map((i) => (
          <NavLink
            key={i.to}
            to={i.to}
            end={i.to === '/'}
            className={({ isActive }) =>
              [
                'block px-3 py-3 rounded-sm transition-colors',
                isActive
                  ? 'bg-accentSoft text-text'
                  : 'text-textMid hover:text-text hover:bg-accentSoft/60',
              ].join(' ')
            }
          >
            <div className="flex items-baseline gap-3">
              <span
                className="display italic text-textDim"
                style={{ fontSize: 13, width: 22 }}
              >
                {i.eyebrow}
              </span>
              <span className="display" style={{ fontSize: 17, letterSpacing: '-0.01em' }}>
                {i.label}
              </span>
            </div>
          </NavLink>
        ))}
      </nav>

      <div
        className="px-6 absolute bottom-6 text-[11px] text-textDim"
        style={{ width: 260 }}
      >
        <div className="eyebrow mb-2" style={{ fontSize: 10 }}>
          Methodology
        </div>
        <div>225 CMR 29.00 · v1</div>
        <div>MassGIS · Eversource ESMP</div>
      </div>
    </aside>
  );
}
