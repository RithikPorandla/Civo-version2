/**
 * Project-type-aware permitting panel — aligned to the Earth & Paper
 * design tokens (`.card`, `.eyebrow`, `.label`, `.display`, `.chip`,
 * CSS variables). Previously had its own hardcoded color + font
 * constants that drifted from the rest of the dashboard.
 */
import { useQuery } from '@tanstack/react-query';
import { api, type ProjectTypeCode } from '../lib/api';

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
  const { data: geo } = useQuery({
    queryKey: ['parcel-geo', parcelId],
    queryFn: () => api.parcelGeoJSON(parcelId),
    enabled: !!parcelId,
  });
  const townName = (geo?.properties as any)?.town_name as string | undefined;

  const { data: munis } = useQuery({
    queryKey: ['municipalities'],
    queryFn: () => api.listMunicipalities(),
  });
  const muni = munis?.find(
    (m) => m.town_name.toUpperCase() === (townName || '').toUpperCase()
  );

  const { data: payload, isLoading } = useQuery({
    queryKey: ['bylaws', muni?.town_id, projectType],
    queryFn: () => api.getProjectTypeBylaws(muni!.town_id, projectType),
    enabled: !!muni?.town_id,
  });

  if (!townName) return null;

  if (!muni) {
    return (
      <section className="card" style={{ padding: '22px 24px' }}>
        <div className="eyebrow" style={{ marginBottom: 10 }}>
          Municipal permitting
        </div>
        <div style={{ fontSize: 14, color: 'var(--text-mid)', lineHeight: 1.55 }}>
          Parcel is in <strong style={{ color: 'var(--text)' }}>{townName}</strong>.
          Bylaws for this municipality have not been seeded yet — see Municipalities →
          coverage.
        </div>
      </section>
    );
  }

  if (isLoading || !payload) {
    return (
      <section className="card" style={{ padding: '22px 24px' }}>
        <div className="eyebrow" style={{ marginBottom: 10 }}>
          Municipal permitting
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>Loading bylaws…</div>
      </section>
    );
  }

  const b = payload.bylaws as {
    approval_authority?: string;
    process?: string;
    estimated_timeline_months?: [number, number];
    key_triggers?: Array<{
      description: string;
      bylaw_ref?: string;
      source_url?: string;
    }>;
    notes?: string;
    verification_note?: string;
  };
  const range = b.estimated_timeline_months;

  return (
    <section className="card" style={{ padding: '24px 28px' }}>
      <div style={{ marginBottom: 16 }}>
        <div className="eyebrow" style={{ marginBottom: 10 }}>
          Municipal permitting
        </div>
        <h2
          className="display"
          style={{ fontSize: 24, margin: 0, letterSpacing: '-0.015em', lineHeight: 1.15 }}
        >
          {PROJECT_TYPE_LABEL[projectType]} in {payload.town_name}
        </h2>
        <p
          className="tnum"
          style={{
            fontSize: 12,
            color: 'var(--text-dim)',
            margin: '8px 0 0',
          }}
        >
          Scored under <code style={{ fontFamily: 'inherit' }}>{projectType}</code> ·
          bylaws refreshed{' '}
          {muni.last_refreshed_at
            ? new Date(muni.last_refreshed_at).toLocaleDateString()
            : '—'}
        </p>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr',
          gap: 28,
          padding: '16px 0',
          borderTop: '1px solid var(--border-soft)',
          borderBottom: '1px solid var(--border-soft)',
          marginBottom: 20,
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

      {b.key_triggers && b.key_triggers.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div className="label" style={{ marginBottom: 10 }}>
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
            {b.key_triggers.map((t, i) => (
              <li
                key={i}
                style={{
                  borderLeft: '2px solid var(--border)',
                  padding: '2px 0 2px 14px',
                }}
              >
                <div
                  style={{ fontSize: 14, color: 'var(--text)', lineHeight: 1.55 }}
                >
                  {t.description}
                </div>
                <div
                  style={{
                    display: 'flex',
                    gap: 12,
                    marginTop: 6,
                    fontSize: 11,
                    alignItems: 'center',
                  }}
                >
                  {t.bylaw_ref && (
                    <span className="tnum" style={{ color: 'var(--text-dim)' }}>
                      {t.bylaw_ref}
                    </span>
                  )}
                  {t.source_url && (
                    <a
                      href={t.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="link-accent"
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
        <p
          style={{
            fontSize: 13,
            color: 'var(--text-mid)',
            margin: '0 0 12px',
            lineHeight: 1.6,
          }}
        >
          {b.notes}
        </p>
      )}

      {b.verification_note && (
        <p
          style={{
            fontSize: 11,
            color: 'var(--text-dim)',
            fontFamily: "'Fraunces', Georgia, serif",
            fontStyle: 'italic',
            margin: '8px 0 0',
            lineHeight: 1.55,
          }}
        >
          {b.verification_note}
        </p>
      )}
    </section>
  );
}

function FactBlock({ label, value }: { label: string; value: string | undefined }) {
  return (
    <div>
      <div className="label" style={{ marginBottom: 6 }}>
        {label}
      </div>
      <div
        style={{
          fontFamily: "'Fraunces', Georgia, serif",
          fontSize: 18,
          fontWeight: 500,
          letterSpacing: '-0.012em',
          lineHeight: 1.3,
          color: 'var(--text)',
        }}
      >
        {value || '—'}
      </div>
    </div>
  );
}
