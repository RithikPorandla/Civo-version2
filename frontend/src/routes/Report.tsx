import { useMemo, useState } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  api,
  type Bucket,
  type CriterionScore,
  type ProjectTypeCode,
  type SourceCitation,
  type SuitabilityReport,
} from '../lib/api';
import { MapView } from '../components/MapView';
import PermittingPanel from '../components/PermittingPanel';
import ExemptionChip from '../components/ExemptionChip';
import { IconArrowUpRight, IconChevronDown } from '../components/Icon';

const CRITERION_NAME: Record<string, string> = {
  biodiversity: 'Biodiversity',
  climate_resilience: 'Climate resilience',
  carbon_storage: 'Carbon storage',
  grid_alignment: 'Grid alignment',
  burdens: 'Environmental burdens',
  benefits: 'Environmental benefits',
  agriculture: 'Agricultural production',
};

const STAT_BG = {
  blue: '#e3ebf5',
  lavender: '#eeedf2',
  mint: '#dbe8cc',
  peach: '#f8e8d6',
};

const STATUS = {
  good: { c: '#1f8a3d', bg: '#e4f3e7', label: 'OK' },
  warn: { c: '#b6781c', bg: '#fbecd6', label: 'Caution' },
  bad: { c: '#c0392b', bg: '#f9e3df', label: 'Risk' },
  pending: { c: '#8a8a8a', bg: '#f1f2f4', label: 'Pending' },
};

const bucketTone = (b: Bucket) =>
  b === 'SUITABLE'
    ? { c: STATUS.good.c, bg: STATUS.good.bg, label: 'Suitable' }
    : b === 'CONDITIONALLY SUITABLE'
    ? { c: STATUS.warn.c, bg: STATUS.warn.bg, label: 'Conditional' }
    : { c: STATUS.bad.c, bg: STATUS.bad.bg, label: 'Constrained' };

const statusTone = (s: CriterionScore['status']) => {
  if (s === 'ok') return STATUS.good;
  if (s === 'flagged') return STATUS.warn;
  if (s === 'ineligible') return STATUS.bad;
  return STATUS.pending;
};

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

// -----------------------------------------------------------------------------
// Route
// -----------------------------------------------------------------------------
export default function Report() {
  const { reportId } = useParams();
  const [qp] = useSearchParams();
  const projectType = (qp.get('pt') as ProjectTypeCode) || 'solar_ground_mount';
  const kw = qp.get('kw');
  const acres = qp.get('acres');
  const nameplateKw = kw ? Number(kw) : null;
  const footprintAcres = acres ? Number(acres) : null;

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
      nameplateKw={nameplateKw}
      footprintAcres={footprintAcres}
    />
  );
}

function Loading() {
  return (
    <div style={{ padding: '120px 28px', color: '#8a8a8a', textAlign: 'center' }}>
      Loading report…
    </div>
  );
}

function ErrorState({ err }: { err: string }) {
  return (
    <div style={{ padding: '80px 28px', color: '#c0392b', maxWidth: 720 }}>
      <div className="label" style={{ marginBottom: 10 }}>
        Something went wrong
      </div>
      <p style={{ fontSize: 14, lineHeight: 1.55 }}>{err}</p>
      <Link to="/" style={{ fontSize: 13, color: '#2563eb' }}>
        ← Back
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
  nameplateKw,
  footprintAcres,
}: {
  report: SuitabilityReport;
  precedents: NonNullable<Awaited<ReturnType<typeof api.parcelPrecedents>>>;
  expanded: string | null;
  setExpanded: (k: string | null) => void;
  projectType: ProjectTypeCode;
  nameplateKw: number | null;
  footprintAcres: number | null;
}) {
  const tone = bucketTone(report.bucket);
  const address = report.address || report.parcel_id;
  const mitigation = useMemo(
    () => mitigationFor(report.primary_constraint, address),
    [report.primary_constraint, address]
  );
  const summary = useMemo(() => buildSummary(report), [report]);

  const primaryName = report.primary_constraint
    ? CRITERION_NAME[report.primary_constraint] ?? report.primary_constraint
    : '—';

  const stats = [
    {
      label: 'Total score',
      value: Math.round(report.total_score),
      suffix: '/ 100',
      bg: STAT_BG.blue,
    },
    {
      label: 'Assessment',
      value: tone.label,
      suffix: '',
      bg: STAT_BG.lavender,
    },
    {
      label: 'Primary constraint',
      value: primaryName,
      suffix: '',
      bg: STAT_BG.blue,
    },
    {
      label: 'Project type',
      value: report.project_type.replace(/_/g, ' '),
      suffix: '',
      bg: STAT_BG.mint,
    },
  ];

  return (
    <div style={{ padding: '24px 28px 40px' }}>
      {/* Header row: title + action buttons */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          marginBottom: 20,
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>Today</span>
            <IconChevronDown size={14} className="text-textDim" />
          </div>
          <h1
            style={{
              fontSize: 22,
              fontWeight: 600,
              letterSpacing: -0.3,
              margin: '4px 0 0',
            }}
          >
            {address}
          </h1>
          <div
            className="text-textDim"
            style={{ fontSize: 12, marginTop: 6, display: 'flex', gap: 10 }}
          >
            <span>{report.parcel_id}</span>
            <span>·</span>
            <span>{report.config_version}</span>
            <span>·</span>
            <span>{new Date(report.computed_at).toISOString().slice(0, 10)}</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost">Export PDF</button>
          <Link to="/lookup" style={{ textDecoration: 'none' }}>
            <button className="btn btn-primary">New analysis</button>
          </Link>
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
          <div key={s.label} className="stat-tile" style={{ background: s.bg }}>
            <div style={{ fontSize: 13, fontWeight: 500 }}>{s.label}</div>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
              <div
                style={{
                  fontSize: 30,
                  fontWeight: 600,
                  letterSpacing: -0.5,
                  lineHeight: 1.05,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  textTransform: 'capitalize',
                }}
              >
                {s.value}
              </div>
              {s.suffix && (
                <div className="text-textMid" style={{ fontSize: 13 }}>
                  {s.suffix}
                </div>
              )}
            </div>
          </div>
        ))}
      </section>

      {/* Exemption chip row */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 24 }}>
        <ExemptionChip
          req={{
            project_type: projectType,
            nameplate_capacity_kw: nameplateKw,
            site_footprint_acres: footprintAcres,
          }}
        />
      </div>

      {/* Findings + narrative */}
      <section
        style={{
          display: 'grid',
          gridTemplateColumns: '1.6fr 1fr',
          gap: 16,
          marginBottom: 20,
        }}
      >
        <Panel title="Findings" right={<span className="chip">{report.bucket}</span>}>
          <h2 style={{ fontSize: 18, fontWeight: 600, letterSpacing: -0.3, margin: 0 }}>
            {summary.verdict}
          </h2>
          <p
            className="text-textMid"
            style={{ fontSize: 14, lineHeight: 1.6, margin: '10px 0 18px', maxWidth: 680 }}
          >
            {summary.narrative}
          </p>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns:
                summary.strengths.length && summary.constraints.length
                  ? 'repeat(2, 1fr)'
                  : '1fr',
              gap: 14,
            }}
          >
            {summary.strengths.length > 0 && (
              <FindingsBlock title="Strengths" tone="good" items={summary.strengths} />
            )}
            {summary.constraints.length > 0 && (
              <FindingsBlock
                title="Constraints"
                tone={summary.constraintsTone}
                items={summary.constraints}
              />
            )}
          </div>
        </Panel>

        <Panel title="Recommended">
          <p style={{ fontSize: 14, lineHeight: 1.6, margin: 0 }}>
            {summary.recommendation ?? 'Continue through the sections below.'}
          </p>
        </Panel>
      </section>

      {/* Site map */}
      <Panel title="Site — the parcel and its surroundings" className="mb-5">
        <p
          className="text-textDim"
          style={{ fontSize: 12, margin: '-4px 0 10px' }}
        >
          Drag to pan, scroll to zoom, right-click + drag to tilt, shift + drag to rotate.
        </p>
        <div
          style={{
            borderRadius: 12,
            overflow: 'hidden',
            height: 500,
            border: '1px solid #e8eaed',
          }}
        >
          <MapView parcelId={report.parcel_id} />
        </div>
      </Panel>

      {/* Criteria */}
      <Panel title="Criteria — how the score breaks down" className="mb-5">
        <p
          className="text-textDim"
          style={{ fontSize: 12, margin: '-4px 0 10px' }}
        >
          Seven weighted criteria. Click any row for the finding and sources.
        </p>
        <div style={{ borderTop: '1px solid #e8eaed' }}>
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
      </Panel>

      {/* Permitting panel */}
      <section style={{ marginBottom: 20 }}>
        <PermittingPanel parcelId={report.parcel_id} projectType={projectType} />
      </section>

      {/* Mitigation + precedents */}
      <section style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Panel title="Mitigation hierarchy">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {mitigation.map((m, i) => (
              <article
                key={i}
                style={{
                  background: '#fafbfc',
                  border: '1px solid #e8eaed',
                  borderRadius: 10,
                  padding: '12px 14px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: 11,
                    fontWeight: 500,
                    color: '#1a1a1a',
                    letterSpacing: 0.3,
                    textTransform: 'uppercase',
                    marginBottom: 6,
                  }}
                >
                  <span className="text-textDim">{String(i + 1).padStart(2, '0')}</span>
                  <span>{m.tier}</span>
                </div>
                <p
                  className="text-textMid"
                  style={{ fontSize: 13, lineHeight: 1.55, margin: 0 }}
                >
                  {m.text}
                </p>
              </article>
            ))}
          </div>
        </Panel>

        <Panel title="Relevant precedents">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {precedents.length === 0 ? (
              <div
                className="text-textDim"
                style={{ fontSize: 13, lineHeight: 1.55 }}
              >
                No precedents loaded for this town yet.
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
                    background: '#fafbfc',
                    border: '1px solid #e8eaed',
                    borderRadius: 10,
                    padding: '12px 14px',
                    color: 'inherit',
                    display: 'block',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'flex-start',
                      marginBottom: 4,
                      gap: 12,
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>
                        {p.applicant || p.project_address || p.docket || 'Unnamed project'}
                      </div>
                      <div className="text-textDim" style={{ fontSize: 11, marginTop: 3 }}>
                        {(p.decision_date || p.filing_date || p.created_at).slice(0, 10)} ·{' '}
                        {p.project_type} {p.meeting_body ? `· ${p.meeting_body}` : ''}
                      </div>
                    </div>
                    {p.decision && <PrecedentDecisionPill decision={p.decision} />}
                  </div>
                  {p.project_address && (
                    <p
                      className="text-textMid"
                      style={{ fontSize: 12, lineHeight: 1.5, margin: 0 }}
                    >
                      {p.project_address}
                      {p.docket ? ` · ${p.docket}` : ''}
                    </p>
                  )}
                </a>
              ))
            )}
          </div>
        </Panel>
      </section>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Panel + findings summary
// -----------------------------------------------------------------------------
function Panel({
  title,
  right,
  children,
  className,
}: {
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`card ${className ?? ''}`}
      style={{ padding: '20px 22px', marginBottom: className?.includes('mb-5') ? 20 : undefined }}
    >
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

interface SummaryItem {
  name: string;
  detail: string;
}
interface FindingsSummary {
  verdict: string;
  narrative: string;
  strengths: SummaryItem[];
  constraints: SummaryItem[];
  constraintsTone: 'good' | 'warn' | 'bad';
  recommendation: string | null;
}

function buildSummary(report: SuitabilityReport): FindingsSummary {
  const score = Math.round(report.total_score);
  const criteria = report.criteria.filter((c) => c.status !== 'data_unavailable');
  const sorted = [...criteria].sort(
    (a, b) => b.weighted_contribution - a.weighted_contribution
  );
  const strengths = sorted
    .filter((c) => c.status === 'ok' && c.raw_score >= 6)
    .slice(0, 3)
    .map((c) => ({ name: CRITERION_NAME[c.key] ?? c.name, detail: c.finding }));
  const constraintCriteria = [...criteria]
    .filter((c) => c.status === 'flagged' || c.status === 'ineligible' || c.raw_score < 5)
    .sort((a, b) => a.raw_score - b.raw_score)
    .slice(0, 3);
  const constraints = constraintCriteria.map((c) => ({
    name: CRITERION_NAME[c.key] ?? c.name,
    detail: c.finding,
  }));

  let verdict: string;
  if (report.bucket === 'SUITABLE') verdict = 'Clears the 225 CMR 29 threshold.';
  else if (report.bucket === 'CONDITIONALLY SUITABLE')
    verdict = 'Developable with targeted mitigation.';
  else verdict = 'Significant constraints — alternate siting advised.';

  const primary = report.primary_constraint
    ? CRITERION_NAME[report.primary_constraint] ?? report.primary_constraint
    : null;

  let narrative: string;
  if (report.bucket === 'SUITABLE') {
    narrative = `Scored ${score}/100. ${
      primary
        ? `${primary} is the lowest-scoring criterion but stays within acceptable range.`
        : 'All criteria are within acceptable range.'
    }`;
  } else if (report.bucket === 'CONDITIONALLY SUITABLE') {
    narrative = `Scored ${score}/100. ${
      primary ? `${primary} is the binding constraint.` : 'Multiple criteria are close to the threshold.'
    } Expect conditions in the permit; see mitigation + precedents below.`;
  } else {
    narrative = `Scored ${score}/100. ${
      primary ? `${primary} is driving the constrained rating.` : 'Multiple criteria are failing.'
    } Consider an alternate parcel or a significantly reduced footprint.`;
  }

  const hasIneligible = report.criteria.some((c) => c.status === 'ineligible');
  const constraintsTone: 'good' | 'warn' | 'bad' = hasIneligible
    ? 'bad'
    : constraints.length > 0
    ? 'warn'
    : 'good';

  let recommendation: string | null = null;
  if (hasIneligible) {
    recommendation = `Begin with ${primary ?? 'the flagged criterion'} — the Avoid tier in the mitigation hierarchy below is the first lever.`;
  } else if (report.bucket === 'CONDITIONALLY SUITABLE' && primary) {
    recommendation = `Open the ${primary} row to see the finding and citations, then review town precedents.`;
  } else if (report.bucket === 'SUITABLE') {
    recommendation =
      'Proceed to the municipal permitting panel to confirm the by-right or special-permit path.';
  }

  return { verdict, narrative, strengths, constraints, constraintsTone, recommendation };
}

function FindingsBlock({
  title,
  tone,
  items,
}: {
  title: string;
  tone: 'good' | 'warn' | 'bad';
  items: SummaryItem[];
}) {
  const dot =
    tone === 'good'
      ? STATUS.good.c
      : tone === 'warn'
      ? STATUS.warn.c
      : STATUS.bad.c;

  return (
    <div
      style={{
        background: '#fafbfc',
        border: '1px solid #e8eaed',
        borderRadius: 12,
        padding: '14px 16px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span
          aria-hidden="true"
          style={{ width: 6, height: 6, borderRadius: 100, background: dot }}
        />
        <span className="label">{title}</span>
      </div>
      <ul
        style={{
          listStyle: 'none',
          padding: 0,
          margin: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        }}
      >
        {items.map((it, i) => (
          <li key={i}>
            <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 2 }}>{it.name}</div>
            <div
              className="text-textMid"
              style={{ fontSize: 12, lineHeight: 1.55 }}
            >
              {it.detail}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PrecedentDecisionPill({ decision }: { decision: string }) {
  const denied = decision === 'denied';
  const withdrawn = decision === 'withdrawn';
  const pending = decision === 'pending' || decision === 'continued';
  const tone = denied || withdrawn ? STATUS.bad : pending ? STATUS.warn : STATUS.good;
  const label = decision.replace(/_/g, ' ');
  return (
    <div
      style={{
        fontSize: 11,
        color: tone.c,
        background: tone.bg,
        padding: '3px 10px',
        borderRadius: 100,
        fontWeight: 500,
        whiteSpace: 'nowrap',
        textTransform: 'capitalize',
        letterSpacing: 0.2,
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
      style={{
        cursor: 'pointer',
        borderBottom: '1px solid #e8eaed',
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '28px 1fr 64px 180px 92px 24px',
          gap: 16,
          alignItems: 'center',
          padding: '14px 4px',
        }}
      >
        <span className="text-textDim" style={{ fontSize: 12 }}>
          {String(idx).padStart(2, '0')}
        </span>
        <div>
          <div style={{ fontSize: 14, fontWeight: 500 }}>{c.name}</div>
        </div>
        <span className="text-textDim" style={{ fontSize: 12, textAlign: 'right' }}>
          {Math.round(c.weight * 100)}%
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="bar-track" style={{ flex: 1 }}>
            <div
              className="bar-fill"
              style={{ width: `${c.raw_score * 10}%`, background: tone.c }}
            />
          </div>
          <span
            className="text-textMid"
            style={{ fontSize: 12, minWidth: 36, textAlign: 'right' }}
          >
            {c.raw_score.toFixed(1)}
          </span>
        </div>
        <span
          style={{
            fontSize: 11,
            color: tone.c,
            background: tone.bg,
            padding: '3px 10px',
            borderRadius: 100,
            fontWeight: 500,
            justifySelf: 'start',
          }}
        >
          {tone.label}
        </span>
        <span
          className="text-textDim"
          style={{
            fontSize: 12,
            textAlign: 'right',
            transform: expanded ? 'rotate(180deg)' : 'none',
            transition: 'transform 180ms ease',
          }}
        >
          ⌄
        </span>
      </div>
      {expanded && (
        <div style={{ padding: '0 4px 16px 48px' }}>
          <div className="label" style={{ marginBottom: 6 }}>
            Finding
          </div>
          <p style={{ fontSize: 13, lineHeight: 1.6, margin: '0 0 14px' }}>{c.finding}</p>
          {c.citations.length > 0 && (
            <>
              <div className="label" style={{ marginBottom: 8 }}>
                Sources
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {c.citations.map((s, i) => (
                  <CitationChip key={i} s={s} />
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function CitationChip({ s }: { s: SourceCitation }) {
  const baseLabel = `${s.dataset}${s.detail ? ` · ${s.detail}` : ''}`;
  const healthy = !s.health || s.health.status === 'healthy';
  const wb = s.health?.wayback_url || null;

  if (!s.url) {
    return (
      <span
        style={{
          fontSize: 12,
          color: '#525252',
          padding: '3px 10px',
          background: '#f1f2f4',
          borderRadius: 100,
        }}
      >
        {baseLabel}
      </span>
    );
  }

  if (!healthy && wb) {
    return (
      <a
        href={wb}
        target="_blank"
        rel="noreferrer"
        title={`Original URL returns ${s.health?.status_code ?? '???'}. Showing Wayback snapshot.`}
        style={{
          fontSize: 12,
          color: '#525252',
          padding: '3px 10px',
          background: '#fafbfc',
          border: '1px dashed #d7dae0',
          borderRadius: 100,
          textDecoration: 'none',
        }}
      >
        {baseLabel} · archived ↗
      </a>
    );
  }

  if (!healthy) {
    return (
      <a
        href={s.url}
        target="_blank"
        rel="noreferrer"
        title={`Original URL returns ${s.health?.status_code ?? '???'}. No archive available.`}
        style={{
          fontSize: 12,
          color: '#8a8a8a',
          padding: '3px 10px',
          background: '#f1f2f4',
          borderRadius: 100,
          textDecoration: 'line-through',
        }}
      >
        {baseLabel}
      </a>
    );
  }

  return (
    <a
      href={s.url}
      target="_blank"
      rel="noreferrer"
      style={{
        fontSize: 12,
        color: '#2563eb',
        padding: '3px 10px',
        background: '#e8efff',
        borderRadius: 100,
        textDecoration: 'none',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
      }}
    >
      {baseLabel}
      <IconArrowUpRight size={11} />
    </a>
  );
}
