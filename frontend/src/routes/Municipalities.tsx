import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api, doerApi, ProjectTypeCode } from '../lib/api';
import DoerAlignmentStrip from '../components/DoerAlignmentStrip';
import { IconArrowUpRight } from '../components/Icon';

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
  if (isLoading)
    return <div style={{ padding: '28px', color: '#8a8a8a', fontSize: 13 }}>Loading…</div>;

  const stats = [
    { label: 'Towns indexed', value: String(data?.length || 0), bg: '#e3ebf5' },
    {
      label: 'Project types',
      value: String(
        new Set((data || []).flatMap((m) => m.project_types)).size
      ),
      bg: '#eeedf2',
    },
    { label: 'Recently refreshed', value: String(data?.length || 0), bg: '#e3ebf5' },
    { label: 'DOER deadline', value: '228 days', bg: '#dbe8cc' },
  ];

  return (
    <div style={{ padding: '24px 28px 40px' }}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, letterSpacing: -0.3, margin: 0 }}>
          Municipalities
        </h1>
        <p className="text-textMid" style={{ fontSize: 13, margin: '4px 0 0' }}>
          Zoning and permitting posture for every MA town in the corpus.
        </p>
      </div>

      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 16,
          marginBottom: 20,
        }}
      >
        {stats.map((s) => (
          <div key={s.label} className="stat-tile" style={{ background: s.bg }}>
            <div style={{ fontSize: 13, fontWeight: 500 }}>{s.label}</div>
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ fontSize: 30, fontWeight: 600, letterSpacing: -0.5 }}>
                {s.value}
              </div>
              <IconArrowUpRight size={12} />
            </div>
          </div>
        ))}
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
        {(data || []).map((m) => (
          <Link
            key={m.town_id}
            to={`/municipalities/${m.town_id}`}
            className="card"
            style={{
              padding: '20px 22px',
              textDecoration: 'none',
              color: 'inherit',
              transition: 'border-color 120ms ease',
            }}
          >
            <div style={{ fontSize: 17, fontWeight: 600 }}>{m.town_name}</div>
            <div className="text-textDim" style={{ fontSize: 12, marginTop: 6 }}>
              Refreshed{' '}
              {m.last_refreshed_at
                ? new Date(m.last_refreshed_at).toLocaleDateString()
                : '—'}
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
  const { data: doer } = useQuery({
    queryKey: ['doer-status', townId],
    queryFn: () => doerApi.townStatus(townId),
  });
  const [active, setActive] = useState<ProjectTypeCode>('solar_rooftop');
  if (isLoading || !data)
    return <div style={{ padding: '28px', color: '#8a8a8a', fontSize: 13 }}>Loading…</div>;
  const bylaws = data.project_type_bylaws[active] || null;

  return (
    <div style={{ padding: '24px 28px 40px' }}>
      <div style={{ marginBottom: 20 }}>
        <Link
          to="/municipalities"
          className="text-textDim"
          style={{ fontSize: 12, textDecoration: 'none' }}
        >
          ← Municipalities
        </Link>
        <h1 style={{ fontSize: 26, fontWeight: 600, letterSpacing: -0.4, margin: '8px 0 0' }}>
          {data.town_name}
        </h1>
        <p className="text-textDim" style={{ fontSize: 13, margin: '4px 0 0' }}>
          town_id {data.town_id} · refreshed{' '}
          {data.last_refreshed_at
            ? new Date(data.last_refreshed_at).toLocaleDateString()
            : '—'}
        </p>
      </div>

      {doer && (
        <section style={{ marginBottom: 28 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
            DOER model bylaw status
          </div>
          <DoerAlignmentStrip status={doer} />
        </section>
      )}

      <section className="card" style={{ overflow: 'hidden' }}>
        <div
          style={{
            padding: '14px 20px',
            borderBottom: '1px solid #e8eaed',
            fontSize: 14,
            fontWeight: 600,
          }}
        >
          Zoning matrix
        </div>

        <div
          style={{
            display: 'flex',
            gap: 4,
            padding: '10px 16px 0',
            borderBottom: '1px solid #e8eaed',
            overflowX: 'auto',
          }}
        >
          {PROJECT_TYPES.map((pt) => (
            <button
              key={pt.code}
              onClick={() => setActive(pt.code)}
              style={{
                padding: '10px 14px',
                fontSize: 13,
                fontFamily: 'inherit',
                color: active === pt.code ? '#1a1a1a' : '#8a8a8a',
                fontWeight: active === pt.code ? 500 : 400,
                borderBottom:
                  active === pt.code ? '2px solid #1a1a1a' : '2px solid transparent',
                marginBottom: -1,
                background: 'transparent',
                border: 'none',
                borderTop: 'none',
                borderLeft: 'none',
                borderRight: 'none',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'color 120ms ease, border-color 120ms ease',
              }}
            >
              {pt.label}
            </button>
          ))}
        </div>

        <div style={{ padding: '20px 24px' }}>
          {bylaws ? (
            <BylawPanel bylaws={bylaws} />
          ) : (
            <div className="text-textDim" style={{ fontSize: 13 }}>
              No data for this project type.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function BylawPanel({ bylaws }: { bylaws: any }) {
  const range = bylaws.estimated_timeline_months;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 32 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <Block label="Approval authority" value={bylaws.approval_authority} />
        <Block label="Process" value={String(bylaws.process || '—').replace(/_/g, ' ')} />
        <Block
          label="Estimated timeline"
          value={range ? `${range[0]}–${range[1]} months` : '—'}
        />
        {bylaws.notes && <Block label="Notes" value={bylaws.notes} />}
        {bylaws.key_triggers?.length > 0 && (
          <div>
            <div className="label" style={{ marginBottom: 12 }}>
              Key triggers
            </div>
            <ul
              style={{
                listStyle: 'none',
                padding: 0,
                margin: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
              }}
            >
              {bylaws.key_triggers.map((t: any, i: number) => (
                <li
                  key={i}
                  style={{
                    borderLeft: '2px solid #e8eaed',
                    paddingLeft: 14,
                  }}
                >
                  <div style={{ fontSize: 14, lineHeight: 1.55 }}>{t.description}</div>
                  {t.bylaw_ref && (
                    <div
                      className="text-textDim"
                      style={{ fontSize: 11, marginTop: 4 }}
                    >
                      {t.bylaw_ref}
                    </div>
                  )}
                  {t.source_url && (
                    <a
                      href={t.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-accent"
                      style={{ fontSize: 12, marginTop: 2, display: 'inline-block' }}
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
      <aside style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {bylaws.setbacks_ft && (
          <div
            style={{
              background: '#fafbfc',
              border: '1px solid #e8eaed',
              borderRadius: 12,
              padding: '16px 18px',
            }}
          >
            <div className="label" style={{ marginBottom: 10 }}>
              Setbacks (ft)
            </div>
            <div style={{ fontSize: 13, display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div>Front: {bylaws.setbacks_ft.front ?? '—'}</div>
              <div>Side: {bylaws.setbacks_ft.side ?? '—'}</div>
              <div>Rear: {bylaws.setbacks_ft.rear ?? '—'}</div>
            </div>
            {bylaws.setbacks_ft.note && (
              <div
                className="text-textDim"
                style={{ fontSize: 11, marginTop: 10, lineHeight: 1.5 }}
              >
                {bylaws.setbacks_ft.note}
              </div>
            )}
          </div>
        )}
        {bylaws.citations?.length > 0 && (
          <div
            style={{
              background: '#fafbfc',
              border: '1px solid #e8eaed',
              borderRadius: 12,
              padding: '16px 18px',
            }}
          >
            <div className="label" style={{ marginBottom: 10 }}>
              Citations
            </div>
            <ul
              style={{
                listStyle: 'none',
                padding: 0,
                margin: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              {bylaws.citations.map((c: any, i: number) => (
                <li key={i}>
                  <a
                    href={c.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-accent"
                    style={{ fontSize: 12, lineHeight: 1.45, textDecoration: 'none' }}
                  >
                    {c.document_title} ↗
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
        {bylaws.verification_note && (
          <div
            className="text-textDim"
            style={{ fontSize: 11, lineHeight: 1.5, fontStyle: 'italic', padding: '0 2px' }}
          >
            {bylaws.verification_note}
          </div>
        )}
      </aside>
    </div>
  );
}

function Block({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="label" style={{ marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 15, lineHeight: 1.5 }}>{value}</div>
    </div>
  );
}
