import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';

const C = {
  border: '#ececec',
  accent: '#8b7355',
  textMid: '#6b6b6b',
  textDim: '#9b9b9b',
};
const DISPLAY = "'Fraunces', Georgia, serif";

export default function Overview() {
  const { data: munis } = useQuery({
    queryKey: ['municipalities'],
    queryFn: () => api.listMunicipalities(),
  });
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.health(),
  });

  const projectTypes = [
    { code: 'solar_ground_mount', label: 'Solar PV (Ground-Mount)' },
    { code: 'bess', label: 'Battery Energy Storage' },
    { code: 'substation', label: 'Substation' },
    { code: 'wind', label: 'Wind Turbine' },
    { code: 'transmission', label: 'Transmission' },
  ];

  return (
    <div className="px-12 py-12 max-w-6xl">
      <div className="eyebrow mb-3">Overview</div>
      <h1
        style={{
          fontFamily: DISPLAY,
          fontSize: 54,
          letterSpacing: -1.5,
          lineHeight: 1.05,
          fontWeight: 400,
        }}
      >
        Massachusetts permitting,
        <br />
        triaged in seconds.
      </h1>
      <p className="text-textMid mt-6 max-w-2xl">
        Civo scores energy-infrastructure sites against 225 CMR 29.00 and cross-references
        every Massachusetts municipality's zoning, wetland, and conservation bylaws. Every
        number traces back to a cited source row.
      </p>

      <div className="mt-12 grid grid-cols-4 gap-6">
        <Stat label="Parcels indexed" value={health?.parcels_loaded?.toLocaleString() || '—'} />
        <Stat label="ESMP projects" value={String(health?.esmp_projects_loaded || '—')} />
        <Stat label="Towns covered" value={String(munis?.length || '—')} />
        <Stat label="Project types" value="5" />
      </div>

      <section className="mt-16">
        <div className="eyebrow mb-4">Covered municipalities</div>
        <div className="grid grid-cols-2 gap-4">
          {(munis || []).map((m) => (
            <Link
              key={m.town_id}
              to={`/municipalities/${m.town_id}`}
              className="border hairline rounded-md bg-surface px-6 py-5 hover:border-borderHover transition"
            >
              <div
                style={{ fontFamily: DISPLAY, fontSize: 22 }}
                className="mb-1"
              >
                {m.town_name}
              </div>
              <div className="text-[12px] text-textDim">
                {m.project_types.length} project types · refreshed{' '}
                {m.last_refreshed_at ? new Date(m.last_refreshed_at).toLocaleDateString() : '—'}
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="mt-16">
        <div className="eyebrow mb-4">Supported project types</div>
        <div className="grid grid-cols-5 gap-3">
          {projectTypes.map((p) => (
            <div
              key={p.code}
              className="border hairline rounded-md bg-surface px-4 py-4 text-[13px]"
              style={{ color: C.textMid }}
            >
              {p.label}
            </div>
          ))}
        </div>
      </section>

      <section className="mt-16 pb-16">
        <div className="eyebrow mb-4">Start here</div>
        <Link to="/lookup" className="btn-pill btn-pill-primary inline-flex">
          Score an address →
        </Link>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border hairline rounded-md bg-surface px-6 py-6">
      <div className="eyebrow mb-2" style={{ fontSize: 11 }}>
        {label}
      </div>
      <div style={{ fontFamily: DISPLAY, fontSize: 34, letterSpacing: '-0.02em' }}>
        {value}
      </div>
    </div>
  );
}
