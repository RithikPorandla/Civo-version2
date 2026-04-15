/**
 * Project-type-aware permitting panel.
 *
 * Given a parcel loc_id + project type, resolves the parcel's town, pulls
 * that town's seeded bylaws, and renders the permitting pathway: approval
 * authority, timeline window, key triggers with source citations, setbacks,
 * and a verification note for fields the seed could not directly verify.
 */
import { useQuery } from '@tanstack/react-query';
import { api, type ProjectTypeCode } from '../lib/api';

const DISPLAY = "'Fraunces', Georgia, serif";
const C = {
  border: '#ececec',
  accent: '#8b7355',
  text: '#1a1a1a',
  textMid: '#6b6b6b',
  textDim: '#9b9b9b',
  surface: '#ffffff',
};

const PROJECT_TYPE_LABEL: Record<ProjectTypeCode, string> = {
  solar_rooftop: 'Solar Rooftop',
  solar_ground_mount: 'Solar Ground-Mount',
  solar_canopy: 'Solar Canopy',
  bess_standalone: 'BESS Standalone',
  bess_colocated: 'BESS Co-located',
  substation: 'Substation',
  transmission: 'Transmission Line',
  ev_charging: 'EV Charging',
};

export default function PermittingPanel({
  parcelId,
  projectType,
}: {
  parcelId: string;
  projectType: ProjectTypeCode;
}) {
  // 1. Resolve parcel → town via existing geojson endpoint
  const { data: geo } = useQuery({
    queryKey: ['parcel-geo', parcelId],
    queryFn: () => api.parcelGeoJSON(parcelId),
    enabled: !!parcelId,
  });
  const townName = (geo?.properties as any)?.town_name as string | undefined;

  // 2. Resolve townName → town_id via municipalities list
  const { data: munis } = useQuery({
    queryKey: ['municipalities'],
    queryFn: () => api.listMunicipalities(),
  });
  const muni = munis?.find(
    (m) => m.town_name.toUpperCase() === (townName || '').toUpperCase()
  );

  // 3. Fetch the project-type bylaws
  const { data: payload, isLoading } = useQuery({
    queryKey: ['bylaws', muni?.town_id, projectType],
    queryFn: () => api.getProjectTypeBylaws(muni!.town_id, projectType),
    enabled: !!muni?.town_id,
  });

  if (!townName) return null;

  if (!muni) {
    return (
      <div style={{ border: `1px solid ${C.border}`, borderRadius: 14, padding: 24 }}>
        <Eyebrow>Municipal permitting</Eyebrow>
        <div style={{ color: C.textMid, fontSize: 14 }}>
          Parcel is in <strong>{townName}</strong>. Bylaws for this municipality
          have not been seeded yet. See Municipalities → bylaws coverage.
        </div>
      </div>
    );
  }

  if (isLoading || !payload) {
    return (
      <div style={{ border: `1px solid ${C.border}`, borderRadius: 14, padding: 24 }}>
        <Eyebrow>Municipal permitting</Eyebrow>
        <div style={{ color: C.textDim, fontSize: 14 }}>Loading bylaws…</div>
      </div>
    );
  }

  const b = payload.bylaws;
  const range = b.estimated_timeline_months;

  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 14,
        padding: '28px 32px',
      }}
    >
      <div style={{ marginBottom: 18 }}>
        <Eyebrow>Municipal permitting</Eyebrow>
        <h2
          style={{
            fontFamily: DISPLAY,
            fontSize: 28,
            fontWeight: 400,
            letterSpacing: -0.6,
            margin: '6px 0 4px',
          }}
        >
          {PROJECT_TYPE_LABEL[projectType]} in {payload.town_name}
        </h2>
        <div style={{ fontSize: 13, color: C.textDim }}>
          Scored under project type <code>{projectType}</code> · bylaws refreshed{' '}
          {muni.last_refreshed_at
            ? new Date(muni.last_refreshed_at).toLocaleDateString()
            : '—'}
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr',
          gap: 28,
          padding: '18px 0',
          borderTop: `1px solid ${C.border}`,
          borderBottom: `1px solid ${C.border}`,
          marginBottom: 24,
        }}
      >
        <FactBlock label="Approval authority" value={b.approval_authority} />
        <FactBlock
          label="Process"
          value={String(b.process || '—').replace(/_/g, ' ')}
        />
        <FactBlock
          label="Estimated timeline"
          value={range ? `${range[0]}–${range[1]} months` : '—'}
        />
      </div>

      {b.key_triggers?.length > 0 && (
        <div style={{ marginBottom: 18 }}>
          <Eyebrow>Key triggers</Eyebrow>
          <ul style={{ listStyle: 'none', padding: 0, margin: '12px 0 0', display: 'flex', flexDirection: 'column', gap: 14 }}>
            {b.key_triggers.map((t: any, i: number) => (
              <li
                key={i}
                style={{ borderLeft: `2px solid ${C.border}`, padding: '2px 0 2px 16px' }}
              >
                <div style={{ fontSize: 14, color: C.text, lineHeight: 1.5 }}>
                  {t.description}
                </div>
                <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 11 }}>
                  {t.bylaw_ref && (
                    <span style={{ color: C.textDim, fontStyle: 'italic', fontFamily: DISPLAY }}>
                      {t.bylaw_ref}
                    </span>
                  )}
                  {t.source_url && (
                    <a
                      href={t.source_url}
                      target="_blank"
                      rel="noreferrer"
                      style={{ color: C.accent }}
                    >
                      Source ↗
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {b.notes && (
        <div style={{ fontSize: 13, color: C.textMid, marginBottom: 18 }}>
          {b.notes}
        </div>
      )}

      {b.verification_note && (
        <div style={{ fontSize: 11, color: C.textDim, fontStyle: 'italic', marginTop: 8 }}>
          {b.verification_note}
        </div>
      )}
    </div>
  );
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontFamily: DISPLAY,
        fontStyle: 'italic',
        color: C.accent,
        fontSize: 13,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
      }}
    >
      {children}
    </div>
  );
}

function FactBlock({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div
        style={{
          fontFamily: DISPLAY,
          fontStyle: 'italic',
          color: C.accent,
          fontSize: 11,
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div
        style={{ fontFamily: DISPLAY, fontSize: 18, lineHeight: 1.3, color: C.text }}
      >
        {value || '—'}
      </div>
    </div>
  );
}
