import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api, ProjectTypeCode } from '../lib/api';

const DISPLAY = "'Fraunces', Georgia, serif";
const PROJECT_TYPES: Array<{ code: ProjectTypeCode; label: string }> = [
  { code: 'solar_rooftop', label: 'Solar Rooftop' },
  { code: 'solar_ground_mount', label: 'Solar Ground-Mount' },
  { code: 'solar_canopy', label: 'Solar Canopy' },
  { code: 'bess_standalone', label: 'BESS Standalone' },
  { code: 'bess_colocated', label: 'BESS Co-located' },
  { code: 'substation', label: 'Substation' },
  { code: 'transmission', label: 'Transmission' },
  { code: 'ev_charging', label: 'EV Charging' },
];

export default function MunicipalitiesRoute() {
  const { townId } = useParams();
  if (townId) return <MunicipalityDetail townId={Number(townId)} />;
  return <MunicipalityIndex />;
}

function MunicipalityIndex() {
  const { data, isLoading } = useQuery({
    queryKey: ['municipalities'],
    queryFn: () => api.listMunicipalities(),
  });
  if (isLoading) return <div className="px-12 py-12 text-textDim">Loading…</div>;
  return (
    <div className="px-12 py-12 max-w-6xl">
      <div className="eyebrow mb-3">Municipalities</div>
      <h1
        style={{
          fontFamily: DISPLAY,
          fontSize: 54,
          letterSpacing: -1.5,
          lineHeight: 1.05,
          fontWeight: 400,
        }}
      >
        Permitting by town.
      </h1>
      <p className="text-textMid mt-6 max-w-2xl mb-12">
        Zoning, wetlands, and conservation bylaws for every town where Eversource has
        a planned ESMP project. Each entry cites back to the town's own bylaw document.
      </p>
      <div className="grid grid-cols-2 gap-4">
        {(data || []).map((m) => (
          <Link
            key={m.town_id}
            to={`/municipalities/${m.town_id}`}
            className="border hairline rounded-md bg-surface px-6 py-6 hover:border-borderHover transition"
          >
            <div style={{ fontFamily: DISPLAY, fontSize: 26 }} className="mb-2">
              {m.town_name}
            </div>
            <div className="flex gap-2 flex-wrap">
              {m.project_types.map((pt) => (
                <span
                  key={pt}
                  className="chip"
                  style={{ fontSize: 11, padding: '2px 10px' }}
                >
                  {pt.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function MunicipalityDetail({ townId }: { townId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ['municipality', townId],
    queryFn: () => api.getMunicipality(townId),
  });
  const [active, setActive] = useState<ProjectTypeCode>('solar_rooftop');
  if (isLoading || !data) return <div className="px-12 py-12 text-textDim">Loading…</div>;
  const bylaws = data.project_type_bylaws[active] || null;

  return (
    <div className="px-12 py-12 max-w-6xl">
      <div className="eyebrow mb-3">
        <Link to="/municipalities" className="hover:text-text">
          ← Municipalities
        </Link>
      </div>
      <h1
        style={{
          fontFamily: DISPLAY,
          fontSize: 54,
          letterSpacing: -1.5,
          lineHeight: 1.05,
          fontWeight: 400,
        }}
      >
        {data.town_name}
      </h1>
      <div className="text-sm text-textDim mt-2 mb-10">
        town_id {data.town_id} · refreshed{' '}
        {data.last_refreshed_at
          ? new Date(data.last_refreshed_at).toLocaleDateString()
          : '—'}
      </div>

      <div className="flex gap-1 mb-8 border-b hairline">
        {PROJECT_TYPES.map((pt) => (
          <button
            key={pt.code}
            onClick={() => setActive(pt.code)}
            className="px-4 py-3 text-sm transition-colors"
            style={{
              color: active === pt.code ? '#1a1a1a' : '#9b9b9b',
              borderBottom:
                active === pt.code ? '2px solid #8b7355' : '2px solid transparent',
              marginBottom: -1,
            }}
          >
            {pt.label}
          </button>
        ))}
      </div>

      {bylaws ? <BylawPanel bylaws={bylaws} /> : (
        <div className="text-textDim">No data for this project type.</div>
      )}
    </div>
  );
}

function BylawPanel({ bylaws }: { bylaws: any }) {
  const range = bylaws.estimated_timeline_months;
  return (
    <div className="grid grid-cols-3 gap-8">
      <div className="col-span-2 space-y-6">
        <Block label="Approval authority" value={bylaws.approval_authority} />
        <Block label="Process" value={String(bylaws.process || '—').replace(/_/g, ' ')} />
        <Block
          label="Estimated timeline"
          value={range ? `${range[0]}–${range[1]} months` : '—'}
        />
        {bylaws.notes && <Block label="Notes" value={bylaws.notes} />}
        {bylaws.key_triggers?.length > 0 && (
          <div>
            <div className="eyebrow mb-3">Key triggers</div>
            <ul className="space-y-3">
              {bylaws.key_triggers.map((t: any, i: number) => (
                <li key={i} className="border-l-2 pl-4" style={{ borderColor: '#ececec' }}>
                  <div className="text-[14px]">{t.description}</div>
                  {t.bylaw_ref && (
                    <div className="text-[11px] text-textDim mt-1 eyebrow" style={{ fontSize: 11 }}>
                      {t.bylaw_ref}
                    </div>
                  )}
                  {t.source_url && (
                    <a
                      href={t.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] text-accent hover:underline mt-1 inline-block"
                    >
                      Source ↗
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <div className="space-y-4">
        {bylaws.setbacks_ft && (
          <div className="border hairline rounded-md bg-surface p-5">
            <div className="eyebrow mb-3" style={{ fontSize: 11 }}>
              Setbacks (ft)
            </div>
            <div className="text-[13px] space-y-1">
              <div>Front: {bylaws.setbacks_ft.front ?? '—'}</div>
              <div>Side: {bylaws.setbacks_ft.side ?? '—'}</div>
              <div>Rear: {bylaws.setbacks_ft.rear ?? '—'}</div>
            </div>
            {bylaws.setbacks_ft.note && (
              <div className="text-[11px] text-textDim mt-3">
                {bylaws.setbacks_ft.note}
              </div>
            )}
          </div>
        )}
        {bylaws.citations?.length > 0 && (
          <div className="border hairline rounded-md bg-surface p-5">
            <div className="eyebrow mb-3" style={{ fontSize: 11 }}>
              Citations
            </div>
            <ul className="space-y-3">
              {bylaws.citations.map((c: any, i: number) => (
                <li key={i} className="text-[12px]">
                  <a
                    href={c.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-accent hover:underline"
                  >
                    {c.document_title}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
        {bylaws.verification_note && (
          <div className="text-[11px] text-textDim italic">
            {bylaws.verification_note}
          </div>
        )}
      </div>
    </div>
  );
}

function Block({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="eyebrow mb-2" style={{ fontSize: 11 }}>
        {label}
      </div>
      <div style={{ fontFamily: DISPLAY, fontSize: 20, lineHeight: 1.35 }}>{value}</div>
    </div>
  );
}
