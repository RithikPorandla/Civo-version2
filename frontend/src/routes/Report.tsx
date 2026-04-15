import { useMemo, useState } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  api,
  type Bucket,
  type CriterionScore,
  type ProjectTypeCode,
  type SuitabilityReport,
} from '../lib/api';
import { MapView } from '../components/MapView';
import PermittingPanel from '../components/PermittingPanel';

const C = {
  bg: '#fafaf7',
  surface: '#ffffff',
  surfaceAlt: '#f5f2ea',
  border: '#ececec',
  borderHover: '#d4d1c7',
  text: '#1a1a1a',
  textMid: '#6b6b6b',
  textDim: '#9b9b9b',
  textFaint: '#b8b8b8',
  accent: '#8b7355',
  accentSoft: '#f0ede5',
  good: '#4a7c4f',
  goodSoft: '#eaf2e7',
  warn: '#c08a3e',
  warnSoft: '#f7efe0',
  bad: '#a85a4a',
  badSoft: '#f5e8e4',
};
const DISPLAY = "'Fraunces', Georgia, serif";
const SANS = "'Inter', -apple-system, system-ui, sans-serif";

const bucketTone = (b: Bucket) =>
  b === 'SUITABLE'
    ? { c: C.good, bg: C.goodSoft, label: 'Suitable' }
    : b === 'CONDITIONALLY SUITABLE'
    ? { c: C.warn, bg: C.warnSoft, label: 'Conditionally Suitable' }
    : { c: C.bad, bg: C.badSoft, label: 'Constrained' };

const statusTone = (s: CriterionScore['status']) => {
  if (s === 'ok') return { c: C.good, bg: C.goodSoft, label: 'OK' };
  if (s === 'flagged') return { c: C.warn, bg: C.warnSoft, label: 'Caution' };
  if (s === 'ineligible') return { c: C.bad, bg: C.badSoft, label: 'Risk' };
  return { c: C.textMid, bg: C.accentSoft, label: 'Pending' };
};

// Maps a flagged/ineligible primary constraint to a short mitigation hierarchy.
const mitigationFor = (primary: string | null | undefined, address: string) => {
  const common = [
    {
      tier: 'Avoid',
      text: 'Relocate or reduce the project footprint to eliminate overlap with the limiting constraint area.',
    },
    {
      tier: 'Minimize',
      text: 'Maintain buffers from sensitive resource areas. Keep disturbance under 50% of the parcel. Preserve existing vegetated corridors.',
    },
    {
      tier: 'Mitigate',
      text: 'Offsite restoration or in-lieu fee per 310 CMR 10.55 and applicable town wetland bylaws; SMART 3.0 benchmarks for solar apply.',
    },
  ];
  if (primary === 'biodiversity')
    return [
      {
        tier: 'Avoid',
        text: `Shift the project footprint away from the BioMap Core / NHESP Priority overlap near ${address}.`,
      },
      {
        tier: 'Minimize',
        text: 'Reduce footprint below 5 acres; retain 100-foot buffer from wetland resource edge and any documented vernal pool.',
      },
      common[2],
    ];
  if (primary === 'climate_resilience')
    return [
      {
        tier: 'Avoid',
        text: 'Site equipment outside the Special Flood Hazard Area (FEMA A/AE/VE). No habitable basements in SFHA.',
      },
      {
        tier: 'Minimize',
        text: 'Elevate critical equipment ≥2 ft above BFE per ResilientMass standards. Flood-proof enclosures.',
      },
      {
        tier: 'Mitigate',
        text: 'Design storm water management to the 100-year + 20% climate adder; coordinate with MassDEP 401.',
      },
    ];
  if (primary === 'agriculture')
    return [
      { tier: 'Avoid', text: 'Relocate from Prime Farmland soils and Chapter 61A parcels where feasible.' },
      {
        tier: 'Minimize',
        text: 'Dual-use (agrivoltaic) configuration per SMART 3.0 ADU incentives; preserve top 18" topsoil.',
      },
      common[2],
    ];
  return common;
};

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontFamily: DISPLAY,
        fontStyle: 'italic',
        fontSize: 13,
        color: C.accent,
        marginBottom: 6,
      }}
    >
      {children}
    </div>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div
        style={{
          fontSize: 11,
          color: C.textDim,
          marginBottom: 4,
          letterSpacing: 0.3,
          textTransform: 'uppercase',
          fontWeight: 500,
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 14, color: C.text }}>{value}</div>
    </div>
  );
}

function btnGhost(): React.CSSProperties {
  return {
    background: 'transparent',
    color: C.textMid,
    border: `1px solid ${C.border}`,
    borderRadius: 100,
    padding: '10px 18px',
    fontSize: 13,
    cursor: 'pointer',
    fontFamily: SANS,
  };
}
function btnPrimary(): React.CSSProperties {
  return {
    background: C.text,
    color: C.bg,
    border: 'none',
    borderRadius: 100,
    padding: '10px 20px',
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
    fontFamily: SANS,
  };
}

export default function Report() {
  const { reportId } = useParams();
  const [qp] = useSearchParams();
  const projectType = (qp.get('pt') as ProjectTypeCode) || 'substation';
  const { data: report, isLoading, error } = useQuery({
    queryKey: ['report', reportId],
    queryFn: () => api.report(reportId!),
    enabled: !!reportId,
  });
  const { data: precedents } = useQuery({
    queryKey: ['precedents', report?.parcel_id],
    queryFn: () => api.parcelPrecedents(report!.parcel_id, 5),
    enabled: !!report?.parcel_id,
  });

  const [expanded, setExpanded] = useState<string | null>(null);

  if (isLoading) return <Loading />;
  if (error || !report) return <ErrorState err={String(error)} />;

  return (
    <ReportView
      report={report}
      precedents={precedents || []}
      expanded={expanded}
      setExpanded={setExpanded}
      projectType={projectType}
    />
  );
}

function Loading() {
  return (
    <div style={{ padding: '80px 40px', fontFamily: SANS, color: C.textDim, textAlign: 'center' }}>
      <div style={{ fontFamily: DISPLAY, fontStyle: 'italic' }}>Loading report…</div>
    </div>
  );
}
function ErrorState({ err }: { err: string }) {
  return (
    <div style={{ padding: '80px 40px', fontFamily: SANS, color: C.bad, maxWidth: 720, margin: '0 auto' }}>
      <Eyebrow>Something went wrong</Eyebrow>
      <p>{err}</p>
      <Link to="/" style={{ color: C.accent }}>
        ← Back to search
      </Link>
    </div>
  );
}

function ReportView({
  report,
  precedents,
  expanded,
  setExpanded,
  projectType,
}: {
  report: SuitabilityReport;
  precedents: NonNullable<Awaited<ReturnType<typeof api.parcelPrecedents>>>;
  expanded: string | null;
  setExpanded: (k: string | null) => void;
  projectType: ProjectTypeCode;
}) {
  const tone = bucketTone(report.bucket);
  const address = report.address || report.parcel_id;
  const mitigation = useMemo(
    () => mitigationFor(report.primary_constraint, address),
    [report.primary_constraint, address]
  );

  return (
    <div style={{ fontFamily: SANS, background: C.bg, color: C.text, minHeight: '100vh' }}>
      {/* top app bar */}
      <div
        style={{
          padding: '22px 40px',
          borderBottom: `1px solid ${C.border}`,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: C.bg,
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 40 }}>
          <Link
            to="/"
            style={{ fontFamily: DISPLAY, fontSize: 22, fontWeight: 500, letterSpacing: -0.5, color: C.text, textDecoration: 'none' }}
          >
            Civo
          </Link>
          <div style={{ display: 'flex', gap: 28, fontSize: 13, color: C.textMid }}>
            {['Dashboard', 'Portfolio', 'Towns', 'Methodology'].map((l, i) => (
              <span key={i} style={{ cursor: 'pointer' }}>
                {l}
              </span>
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button style={btnGhost()}>Export PDF</button>
          <button style={btnGhost()}>Save to portfolio</button>
          <Link to="/" style={{ textDecoration: 'none' }}>
            <button style={btnPrimary()}>New analysis</button>
          </Link>
        </div>
      </div>

      <div style={{ maxWidth: 1180, margin: '0 auto', padding: '40px 40px 80px' }}>
        {/* Breadcrumb */}
        <div
          style={{
            fontSize: 13,
            color: C.textDim,
            marginBottom: 20,
            display: 'flex',
            gap: 10,
            alignItems: 'center',
          }}
        >
          <Link to="/" style={{ color: C.textDim, textDecoration: 'none' }}>
            Portfolio
          </Link>
          <span>›</span>
          <span>candidate-sites</span>
          <span>›</span>
          <span style={{ color: C.text }}>{address}</span>
        </div>

        {/* Header — address + metadata + score card */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 360px',
            gap: 48,
            alignItems: 'flex-start',
            marginBottom: 56,
          }}
        >
          <div>
            <Eyebrow>Suitability Report</Eyebrow>
            <h1
              style={{
                fontFamily: DISPLAY,
                fontSize: 54,
                fontWeight: 400,
                lineHeight: 1.05,
                letterSpacing: -1.5,
                margin: '0 0 12px',
              }}
            >
              {address}
            </h1>
            <div style={{ fontSize: 17, color: C.textMid, marginBottom: 28 }}>
              {report.parcel_id}
            </div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, auto)',
                gap: 40,
                paddingTop: 20,
                borderTop: `1px solid ${C.border}`,
              }}
            >
              <MetaItem label="Parcel ID" value={report.parcel_id} />
              <MetaItem label="Project type" value={report.project_type} />
              <MetaItem label="Methodology" value={report.config_version} />
              <MetaItem
                label="Primary constraint"
                value={report.primary_constraint || '—'}
              />
            </div>
          </div>

          {/* Score card */}
          <div
            style={{
              background: C.surface,
              borderRadius: 20,
              padding: '36px 32px',
              border: `1px solid ${C.border}`,
            }}
          >
            <Eyebrow>Total score</Eyebrow>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 16 }}>
              <div
                style={{
                  fontFamily: DISPLAY,
                  fontSize: 96,
                  fontWeight: 400,
                  lineHeight: 0.9,
                  letterSpacing: -4,
                }}
              >
                {Math.round(report.total_score)}
              </div>
              <div style={{ fontSize: 20, color: C.textDim, fontWeight: 300 }}>/ 100</div>
            </div>
            <div
              style={{
                display: 'inline-block',
                padding: '8px 16px',
                background: tone.bg,
                borderRadius: 100,
                fontSize: 13,
                color: tone.c,
                fontWeight: 500,
                marginBottom: 20,
              }}
            >
              {tone.label}
            </div>
            <p
              style={{
                fontSize: 14,
                color: C.textMid,
                lineHeight: 1.6,
                margin: 0,
                paddingTop: 20,
                borderTop: `1px solid ${C.border}`,
              }}
            >
              {interpretationText(report)}
            </p>
          </div>
        </div>

        {/* Map */}
        <section style={{ marginBottom: 80 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-end',
              marginBottom: 20,
            }}
          >
            <div>
              <Eyebrow>Site context</Eyebrow>
              <h2
                style={{
                  fontFamily: DISPLAY,
                  fontSize: 32,
                  fontWeight: 400,
                  letterSpacing: -0.8,
                  margin: 0,
                }}
              >
                The parcel and its surroundings
              </h2>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {['Parcel', 'Habitat', 'Wetlands', 'ESMP'].map((l, i) => (
                <span
                  key={i}
                  style={{
                    fontSize: 12,
                    color: C.textMid,
                    padding: '6px 12px',
                    background: C.surface,
                    border: `1px solid ${C.border}`,
                    borderRadius: 100,
                    cursor: 'default',
                  }}
                >
                  {l}
                </span>
              ))}
            </div>
          </div>
          <MapView parcelId={report.parcel_id} />
        </section>

        {/* Criteria */}
        <section style={{ marginBottom: 80 }}>
          <div style={{ marginBottom: 32 }}>
            <Eyebrow>How the score breaks down</Eyebrow>
            <h2
              style={{
                fontFamily: DISPLAY,
                fontSize: 32,
                fontWeight: 400,
                letterSpacing: -0.8,
                margin: '0 0 12px',
              }}
            >
              Seven criteria, weighted.
            </h2>
            <p
              style={{
                fontSize: 15,
                color: C.textMid,
                lineHeight: 1.6,
                margin: 0,
                maxWidth: 680,
              }}
            >
              Each criterion is evaluated against the 2024 Climate Act methodology codified in 225 CMR 29.00. Click any row to see the full finding and cited sources.
            </p>
          </div>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 1,
              background: C.border,
              borderRadius: 16,
              overflow: 'hidden',
              border: `1px solid ${C.border}`,
            }}
          >
            {report.criteria.map((c, i) => (
              <CriterionRow
                key={c.key}
                idx={i + 1}
                c={c}
                expanded={expanded === c.key}
                onToggle={() => setExpanded(expanded === c.key ? null : c.key)}
              />
            ))}
          </div>
        </section>

        {/* Municipal permitting panel — project-type-aware */}
        <section style={{ marginBottom: 64 }}>
          <PermittingPanel parcelId={report.parcel_id} projectType={projectType} />
        </section>

        {/* Two columns */}
        <section
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 40,
            marginBottom: 80,
          }}
        >
          <div>
            <div style={{ marginBottom: 24 }}>
              <Eyebrow>What you can do about it</Eyebrow>
              <h2
                style={{
                  fontFamily: DISPLAY,
                  fontSize: 28,
                  fontWeight: 400,
                  letterSpacing: -0.6,
                  margin: 0,
                }}
              >
                Mitigation hierarchy
              </h2>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {mitigation.map((m, i) => (
                <div
                  key={i}
                  style={{
                    background: C.surface,
                    border: `1px solid ${C.border}`,
                    borderRadius: 14,
                    padding: '20px 24px',
                  }}
                >
                  <div
                    style={{
                      fontSize: 12,
                      color: C.accent,
                      fontFamily: DISPLAY,
                      fontStyle: 'italic',
                      marginBottom: 8,
                    }}
                  >
                    {String(i + 1).padStart(2, '0')} · {m.tier}
                  </div>
                  <p style={{ fontSize: 14, color: C.textMid, lineHeight: 1.6, margin: 0 }}>
                    {m.text}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div style={{ marginBottom: 24 }}>
              <Eyebrow>What this town has decided before</Eyebrow>
              <h2
                style={{
                  fontFamily: DISPLAY,
                  fontSize: 28,
                  fontWeight: 400,
                  letterSpacing: -0.6,
                  margin: 0,
                }}
              >
                Relevant precedents
              </h2>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {precedents.length === 0 ? (
                <div
                  style={{
                    background: C.surface,
                    border: `1px solid ${C.border}`,
                    borderRadius: 14,
                    padding: '20px 24px',
                    color: C.textDim,
                    fontSize: 14,
                    lineHeight: 1.6,
                  }}
                >
                  No precedents loaded for this town yet. The research agent has only populated Acton in this build. Other towns will populate in the next run.
                </div>
              ) : (
                precedents.map((p) => (
                  <a
                    key={p.id}
                    href={p.source_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      textDecoration: 'none',
                      background: C.surface,
                      border: `1px solid ${C.border}`,
                      borderRadius: 14,
                      padding: '20px 24px',
                      display: 'block',
                      color: 'inherit',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        marginBottom: 8,
                        gap: 12,
                      }}
                    >
                      <div>
                        <div
                          style={{
                            fontSize: 15,
                            color: C.text,
                            fontWeight: 500,
                            fontFamily: DISPLAY,
                          }}
                        >
                          {p.applicant || p.project_address || p.docket || 'Unnamed project'}
                        </div>
                        <div style={{ fontSize: 12, color: C.textDim, marginTop: 3 }}>
                          {(p.decision_date || p.filing_date || p.created_at).slice(0, 10)} ·{' '}
                          {p.project_type} {p.meeting_body ? `· ${p.meeting_body}` : ''}
                        </div>
                      </div>
                      {p.decision && <PrecedentDecisionPill decision={p.decision} />}
                    </div>
                    {p.project_address && (
                      <p
                        style={{
                          fontSize: 13,
                          color: C.textMid,
                          lineHeight: 1.55,
                          margin: 0,
                        }}
                      >
                        {p.project_address}
                        {p.docket ? ` · ${p.docket}` : ''}
                      </p>
                    )}
                  </a>
                ))
              )}
            </div>
          </div>
        </section>

        {/* Footer provenance */}
        <div
          style={{
            paddingTop: 32,
            borderTop: `1px solid ${C.border}`,
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 12,
            color: C.textDim,
            flexWrap: 'wrap',
            gap: 16,
          }}
        >
          <div>
            Scored on {new Date(report.computed_at).toLocaleDateString()} · Configuration{' '}
            {report.config_version}
          </div>
          <div>Data sources: MassGIS · NHESP · FEMA NFHL · Eversource ESMP DPU 24-10</div>
          <div>All scoring traceable to {report.methodology}</div>
        </div>
      </div>
    </div>
  );
}

function interpretationText(report: SuitabilityReport) {
  const pc = report.primary_constraint;
  const niceName: Record<string, string> = {
    biodiversity: 'Biodiversity',
    climate_resilience: 'Climate resilience',
    carbon_storage: 'Carbon storage',
    grid_alignment: 'Grid alignment',
    burdens: 'Environmental burdens',
    benefits: 'Environmental benefits',
    agriculture: 'Agricultural production',
  };
  if (report.bucket === 'SUITABLE')
    return `Site meets the MA EEA site-suitability threshold. ${
      pc ? niceName[pc] ?? pc : 'No individual'
    } is the lowest-scoring criterion; review the row below for detail.`;
  if (report.bucket === 'CONDITIONALLY SUITABLE')
    return `${niceName[pc || ''] || 'A scoring criterion'} is the limiting factor. Site is developable with mitigation. See precedents for how similar outcomes have been conditioned.`;
  return `${niceName[pc || ''] || 'Multiple criteria'} are driving a constrained rating. Consider an alternate site or a significantly reduced footprint.`;
}

function PrecedentDecisionPill({ decision }: { decision: string }) {
  const denied = decision === 'denied';
  const withdrawn = decision === 'withdrawn';
  const pending = decision === 'pending' || decision === 'continued';
  const tone =
    denied || withdrawn
      ? { c: C.bad, bg: C.badSoft }
      : pending
      ? { c: C.warn, bg: C.warnSoft }
      : { c: C.good, bg: C.goodSoft };
  const label = decision.replace(/_/g, ' ');
  return (
    <div
      style={{
        fontSize: 11,
        color: tone.c,
        background: tone.bg,
        padding: '4px 12px',
        borderRadius: 100,
        fontWeight: 500,
        whiteSpace: 'nowrap',
        textTransform: 'capitalize',
      }}
    >
      {label}
    </div>
  );
}

function CriterionRow({
  idx,
  c,
  expanded,
  onToggle,
}: {
  idx: number;
  c: CriterionScore;
  expanded: boolean;
  onToggle: () => void;
}) {
  const tone = statusTone(c.status);
  return (
    <div
      onClick={onToggle}
      style={{ background: C.surface, padding: '24px 32px', cursor: 'pointer' }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '40px 1fr 200px 80px 40px',
          gap: 24,
          alignItems: 'center',
        }}
      >
        <div
          style={{
            fontSize: 13,
            color: C.textDim,
            fontFamily: DISPLAY,
            fontStyle: 'italic',
          }}
        >
          {String(idx).padStart(2, '0')}
        </div>
        <div>
          <div style={{ fontSize: 17, color: C.text, fontWeight: 500, fontFamily: DISPLAY }}>
            {c.name}
          </div>
          <div style={{ fontSize: 12, color: C.textDim, marginTop: 4 }}>
            Weight {Math.round(c.weight * 100)}%
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div
            style={{
              flex: 1,
              height: 4,
              background: C.border,
              borderRadius: 2,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: `${c.raw_score * 10}%`,
                height: '100%',
                background: tone.c,
                borderRadius: 2,
                transition: 'width 240ms ease',
              }}
            />
          </div>
          <div style={{ fontSize: 13, color: C.textMid, minWidth: 36, textAlign: 'right' }}>
            {c.raw_score.toFixed(1)}/10
          </div>
        </div>
        <div
          style={{
            fontSize: 11,
            color: tone.c,
            fontWeight: 500,
            padding: '4px 10px',
            background: tone.bg,
            borderRadius: 100,
            textAlign: 'center',
          }}
        >
          {tone.label}
        </div>
        <div
          style={{
            fontSize: 14,
            color: C.textDim,
            textAlign: 'right',
            transform: expanded ? 'rotate(180deg)' : 'none',
            transition: 'transform 0.2s',
          }}
        >
          ⌄
        </div>
      </div>
      {expanded && (
        <div
          style={{
            marginTop: 20,
            paddingTop: 20,
            borderTop: `1px solid ${C.border}`,
            display: 'grid',
            gridTemplateColumns: '40px 1fr',
            gap: 24,
          }}
        >
          <div />
          <div>
            <div
              style={{
                fontSize: 11,
                color: C.textDim,
                textTransform: 'uppercase',
                letterSpacing: 0.5,
                marginBottom: 10,
                fontWeight: 500,
              }}
            >
              Finding
            </div>
            <p
              style={{
                fontSize: 15,
                color: C.text,
                lineHeight: 1.65,
                margin: '0 0 20px',
              }}
            >
              {c.finding}
            </p>
            {c.citations.length > 0 && (
              <>
                <div
                  style={{
                    fontSize: 11,
                    color: C.textDim,
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                    marginBottom: 10,
                    fontWeight: 500,
                  }}
                >
                  Sources
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {c.citations.map((s, i) =>
                    s.url ? (
                      <a
                        key={i}
                        href={s.url}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          fontSize: 12,
                          color: C.accent,
                          padding: '4px 12px',
                          background: C.accentSoft,
                          borderRadius: 100,
                          textDecoration: 'none',
                        }}
                      >
                        {s.dataset}
                        {s.detail ? ` · ${s.detail}` : ''} ↗
                      </a>
                    ) : (
                      <span
                        key={i}
                        style={{
                          fontSize: 12,
                          color: C.textMid,
                          padding: '4px 12px',
                          background: C.accentSoft,
                          borderRadius: 100,
                        }}
                      >
                        {s.dataset}
                        {s.detail ? ` · ${s.detail}` : ''}
                      </span>
                    )
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
