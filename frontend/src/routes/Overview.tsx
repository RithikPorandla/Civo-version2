import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { IconArrowUpRight, IconChevronDown } from '../components/Icon';

export default function Overview() {
  const { data: munis } = useQuery({
    queryKey: ['municipalities'],
    queryFn: () => api.listMunicipalities(),
  });
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.health(),
  });

  const stats = [
    {
      label: 'Parcels indexed',
      value: health?.parcels_loaded?.toLocaleString() || '—',
      delta: '+11.01%',
      bg: '#e3ebf5',
    },
    {
      label: 'ESMP projects',
      value: String(health?.esmp_projects_loaded || '—'),
      delta: '+0.00%',
      bg: '#eeedf2',
    },
    {
      label: 'Towns covered',
      value: String(munis?.length || '—'),
      delta: '+15.03%',
      bg: '#e3ebf5',
    },
    {
      label: 'Project types',
      value: '8',
      delta: '+6.08%',
      bg: '#dbe8cc',
    },
  ];

  const projectTypes = [
    { code: 'solar_rooftop', label: 'Solar Rooftop' },
    { code: 'solar_ground_mount', label: 'Solar Ground-Mount' },
    { code: 'solar_canopy', label: 'Solar Canopy' },
    { code: 'bess_standalone', label: 'BESS Standalone' },
    { code: 'bess_colocated', label: 'BESS Co-located' },
    { code: 'substation', label: 'Substation' },
    { code: 'transmission', label: 'Transmission' },
    { code: 'ev_charging', label: 'EV Charging' },
  ];

  return (
    <div style={{ padding: '24px 28px 40px' }}>
      {/* Page title row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 20,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 600 }}>Today</span>
          <IconChevronDown size={14} className="text-textDim" />
        </div>
      </div>

      {/* Stat tiles */}
      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 16,
          marginBottom: 20,
        }}
      >
        {stats.map((s) => (
          <StatTile key={s.label} {...s} />
        ))}
      </section>

      {/* Two-column block: munis list + project types */}
      <section
        style={{
          display: 'grid',
          gridTemplateColumns: '1.5fr 1fr',
          gap: 16,
          marginBottom: 20,
        }}
      >
        <Panel title="Covered municipalities" right={<Link to="/municipalities" className="text-[13px] text-accent">View all →</Link>}>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {(munis || []).slice(0, 5).map((m, i) => (
              <Link
                key={m.town_id}
                to={`/municipalities/${m.town_id}`}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr auto auto',
                  gap: 16,
                  alignItems: 'center',
                  padding: '14px 0',
                  borderTop: i === 0 ? 'none' : '1px solid #e8eaed',
                  textDecoration: 'none',
                  color: 'inherit',
                }}
              >
                <div style={{ fontSize: 14, fontWeight: 500 }}>{m.town_name}</div>
                <span className="chip">{m.project_types.length} project types</span>
                <span className="text-textDim" style={{ fontSize: 12 }}>
                  {m.last_refreshed_at
                    ? new Date(m.last_refreshed_at).toLocaleDateString()
                    : '—'}
                </span>
              </Link>
            ))}
            {(!munis || munis.length === 0) && (
              <div className="text-textDim" style={{ fontSize: 13, padding: '12px 0' }}>
                No municipalities loaded yet.
              </div>
            )}
          </div>
        </Panel>

        <Panel title="Supported project types">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
            {projectTypes.map((p) => (
              <div
                key={p.code}
                style={{
                  fontSize: 13,
                  color: '#525252',
                  padding: '8px 10px',
                  background: '#f7f8fa',
                  borderRadius: 8,
                }}
              >
                {p.label}
              </div>
            ))}
          </div>
        </Panel>
      </section>

      {/* CTA */}
      <section>
        <Link to="/lookup" className="btn btn-primary">
          Score an address →
        </Link>
      </section>
    </div>
  );
}

function StatTile({
  label,
  value,
  delta,
  bg,
}: {
  label: string;
  value: string;
  delta: string;
  bg: string;
}) {
  return (
    <div className="stat-tile" style={{ background: bg }}>
      <div style={{ fontSize: 13, fontWeight: 500, color: '#1a1a1a' }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div
          style={{
            fontSize: 30,
            fontWeight: 600,
            letterSpacing: -0.5,
            lineHeight: 1.05,
            color: '#1a1a1a',
          }}
        >
          {value}
        </div>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            fontSize: 12,
            color: '#1a1a1a',
          }}
        >
          {delta}
          <IconArrowUpRight size={12} />
        </div>
      </div>
    </div>
  );
}

function Panel({
  title,
  right,
  children,
}: {
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="card" style={{ padding: '20px 22px' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 14,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 600 }}>{title}</div>
        {right}
      </div>
      {children}
    </section>
  );
}
