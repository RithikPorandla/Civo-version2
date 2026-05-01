import { useMemo, useState } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  api,
  reportApi,
  type Bucket,
  type CriterionScore,
  type HcaInfo,
  type MitigationCostEstimate,
  type MitigationItem,
  type MoratoriumDetail,
  type ProjectTypeCode,
  type ResolutionInfo,
  type SourceCitation,
  type SuitabilityReport,
} from '../lib/api';
import { MapView } from '../components/MapView';
import PermittingPanel from '../components/PermittingPanel';
import ExemptionChip from '../components/ExemptionChip';
import SiteAnalysisPanel from '../components/SiteAnalysisPanel';
import { IconArrowUpRight } from '../components/Icon';

const CRITERION_NAME: Record<string, string> = {
  biodiversity: 'Biodiversity',
  climate_resilience: 'Climate resilience',
  carbon_storage: 'Carbon storage',
  grid_alignment: 'Grid alignment',
  burdens: 'Environmental burdens',
  benefits: 'Environmental benefits',
  agriculture: 'Agricultural production',
};

const CRITERION_DESC: Record<string, string> = {
  biodiversity: 'BioMap Core, NHESP, wetlands',
  climate_resilience: 'FEMA flood zones, sea-level rise',
  carbon_storage: 'Forest cover & carbon sequestration',
  grid_alignment: 'Proximity to ESMP substation projects',
  burdens: 'EJ / MassEnviroScreen burden score',
  benefits: 'Impervious + previously-developed cover',
  agriculture: 'Prime Farmland & Chapter 61A',
};

const INELIGIBLE_LAYER_NAMES: Record<string, string> = {
  biomap_core: 'BioMap Core',
  nhesp_priority: 'NHESP Priority Habitat',
  nhesp_estimated: 'NHESP Estimated Habitat',
  biomap_cnl: 'BioMap CNL',
  article97: 'Article 97 Protected Land',
  dcr_parks: 'DCR State Park / Reservation',
  conservation_restriction: 'Conservation Restriction',
  prime_farmland: 'Prime Farmland (Chapter 61A)',
};

const STATUS = {
  good: { c: 'var(--good)', bg: 'var(--sage-soft, #eaf2e7)', label: 'OK' },
  warn: { c: 'var(--gold, #c08a3e)', bg: 'var(--gold-soft, #f7efe0)', label: 'Caution' },
  bad: { c: 'var(--bad)', bg: 'var(--bad-soft, #f5e8e4)', label: 'Risk' },
  pending: { c: 'var(--text-dim)', bg: 'var(--surface-alt)', label: 'N/A' },
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

type ParcelGeoProps = {
  loc_id: string;
  site_addr: string | null;
  town_name: string | null;
  city: string | null;
  zip: string | null;
  owner1: string | null;
  use_code: string | null;
  fy: number | null;
  total_val: number | null;
  lot_size: number | null;
  zoning: string | null;
  style: string | null;
  bldg_val: number | null;
  land_val: number | null;
  bld_area: number | null;
  year_built: number | null;
  ls_price: number | null;
  ls_date: string | null;
  stories: number | null;
};

const USE_CODE: Record<string, string> = {
  '1010': 'Single-family', '1020': 'Condo', '1040': 'Two-family', '1050': 'Three-family',
  '1110': 'Apartment (4–8 units)', '1120': 'Apartment (9+ units)',
  '3110': 'Retail', '3200': 'Office', '3250': 'Medical office',
  '3310': 'Hotel / motel', '3400': 'Warehouse', '3410': 'Distribution center',
  '3420': 'Mini-warehouse', '3430': 'Flex / R&D',
  '4110': 'Light industrial', '4120': 'Heavy industrial', '4150': 'Quarry / mining',
  '7100': 'Ch. 61 — Forestry', '7110': 'Ch. 61A — Farm', '7120': 'Ch. 61B — Recreation',
  '9100': 'Town-owned (exempt)', '9300': 'State-owned (exempt)', '9400': 'Federal (exempt)',
  '1300': 'Vacant residential', '3900': 'Vacant commercial', '9900': 'Exempt — other',
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
  const { data: parcelGeo } = useQuery({
    queryKey: ['parcel-geo', report?.parcel_id],
    queryFn: () => api.parcelGeoJSON(report!.parcel_id),
    enabled: !!report?.parcel_id,
  });
  const { data: precedents } = useQuery({
    queryKey: ['precedents', report?.parcel_id],
    queryFn: () => api.parcelPrecedents(report!.parcel_id, 5),
    enabled: !!report?.parcel_id,
  });
  const { data: moratoriums } = useQuery({
    queryKey: ['moratoriums', report?.parcel_id],
    queryFn: () => reportApi.moratoriums(report!.parcel_id),
    enabled: !!report?.parcel_id,
  });
  const { data: mitigationCosts } = useQuery({
    queryKey: ['mitigation-costs', report?.parcel_id, projectType, nameplateKw, footprintAcres],
    queryFn: () =>
      reportApi.mitigationCosts(report!.parcel_id, {
        project_type: projectType,
        nameplate_kw: nameplateKw,
        site_footprint_acres: footprintAcres,
      }),
    enabled: !!report?.parcel_id,
  });

  const [expanded, setExpanded] = useState<string | null>(null);

  if (isLoading) return <Loading />;
  if (error || !report) return <ErrorState err={String(error)} />;

  return (
    <ReportView
      report={report}
      parcelGeo={parcelGeo?.properties as ParcelGeoProps | null | undefined}
      precedents={precedents || []}
      moratoriums={moratoriums?.moratoriums || {}}
      mitigationCosts={mitigationCosts || null}
      expanded={expanded}
      setExpanded={setExpanded}
      projectType={projectType}
      nameplateKw={nameplateKw}
      footprintAcres={footprintAcres}
    />
  );
}

// -----------------------------------------------------------------------------
// Loading / Error
// -----------------------------------------------------------------------------
function Loading() {
  return (
    <div style={{ padding: '120px 28px', color: 'var(--text-dim)', textAlign: 'center', fontFamily: "'Fraunces', Georgia, serif", fontStyle: 'italic' }}>
      Loading report…
    </div>
  );
}
function ErrorState({ err }: { err: string }) {
  return (
    <div style={{ padding: '80px 28px', color: 'var(--bad)', maxWidth: 720 }}>
      <div className="label" style={{ marginBottom: 10 }}>Something went wrong</div>
      <p style={{ fontSize: 14, lineHeight: 1.55 }}>{err}</p>
      <Link to="/app" className="link-accent" style={{ fontSize: 13 }}>← Back</Link>
    </div>
  );
}

// -----------------------------------------------------------------------------
// ReportView
// -----------------------------------------------------------------------------
function ReportView({
  report, parcelGeo, precedents, moratoriums, mitigationCosts,
  expanded, setExpanded, projectType, nameplateKw, footprintAcres,
}: {
  report: SuitabilityReport;
  parcelGeo: ParcelGeoProps | null | undefined;
  precedents: NonNullable<Awaited<ReturnType<typeof api.parcelPrecedents>>>;
  moratoriums: Record<string, MoratoriumDetail>;
  mitigationCosts: MitigationCostEstimate | null;
  expanded: string | null;
  setExpanded: (k: string | null) => void;
  projectType: ProjectTypeCode;
  nameplateKw: number | null;
  footprintAcres: number | null;
}) {
  const tone = bucketTone(report.bucket);
  const address = report.address || report.parcel_id;
  const fullAddress = report.resolution?.formatted_address || address;
  const summary = useMemo(() => buildSummary(report), [report]);
  const mitigation = useMemo(() => mitigationFor(report.primary_constraint, address), [report.primary_constraint, address]);

  return (
    <div style={{ padding: '32px 40px 80px', maxWidth: 1280 }}>

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24, marginBottom: 14 }}>
        <div style={{ minWidth: 0 }}>
          <div className="eyebrow" style={{ marginBottom: 8 }}>Suitability Report</div>
          <h1 className="display" style={{ fontSize: 26, margin: 0, letterSpacing: '-0.016em', lineHeight: 1.2, wordBreak: 'break-word' }}>
            {fullAddress}
          </h1>
          <div className="tnum" style={{ fontSize: 11.5, marginTop: 7, display: 'flex', gap: 8, color: 'var(--text-dim)', flexWrap: 'wrap' }}>
            <span title="MassGIS assessor parcel ID">Parcel {report.parcel_id}</span>
            <span>·</span>
            <span>225 CMR 29</span>
            <span>·</span>
            <span>{new Date(report.computed_at).toISOString().slice(0, 10)}</span>
          </div>
        </div>
        <div className="no-print" style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          <button className="btn btn-ghost" onClick={() => window.print()}>Export PDF</button>
          <Link to="/app/lookup" style={{ textDecoration: 'none' }}>
            <button className="btn btn-primary">New analysis <span className="arr">→</span></button>
          </Link>
        </div>
      </div>
      <hr className="rule" style={{ margin: '18px 0 22px' }} />

      {/* ── Alert banners ───────────────────────────────────────────────── */}
      <ResolutionBanner resolution={report.resolution ?? null} />
      <MoratoriumBanner moratoriums={moratoriums} projectType={projectType} />
      <IneligibilityAlert flags={report.ineligible_flags} />

      {/* ── Hero: score + findings | map ────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 20, marginBottom: 20, alignItems: 'start' }}>

        {/* Left column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <ScoreGauge score={report.total_score} bucket={report.bucket} />
          <ParcelMetaStrip parcelGeo={parcelGeo} projectType={projectType} />

          {/* Findings card */}
          <div className="card" style={{ padding: '20px 22px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <span className="label">Findings</span>
              <span style={{ fontSize: 11, fontWeight: 500, color: tone.c, background: tone.bg, padding: '3px 10px', borderRadius: 100 }}>
                {report.bucket}
              </span>
            </div>
            <h2 style={{ fontFamily: "'Fraunces', Georgia, serif", fontSize: 22, fontWeight: 500, letterSpacing: '-0.014em', margin: '0 0 8px', color: 'var(--text)', lineHeight: 1.2 }}>
              {summary.verdict}
            </h2>
            <p style={{ fontSize: 13.5, lineHeight: 1.65, margin: '0 0 14px', color: 'var(--text-mid)', maxWidth: 560 }}>
              {summary.narrative}
            </p>

            {/* Property record */}
            <PropertyRecord parcelGeo={parcelGeo} />

            {/* Next step */}
            {summary.recommendation && (
              <div style={{ background: 'var(--surface)', border: '1px solid var(--border-soft)', borderRadius: 10, padding: '12px 14px' }}>
                <div style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
                  Next step
                </div>
                <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-mid)' }}>
                  {summary.recommendation}
                </div>
              </div>
            )}
          </div>

          {/* Exemption chip */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            <ExemptionChip req={{ project_type: projectType, nameplate_capacity_kw: nameplateKw, site_footprint_acres: footprintAcres }} />
          </div>
        </div>

        {/* Right column — map */}
        <div>
          <div style={{ borderRadius: 12, overflow: 'hidden', height: 480, border: '1px solid var(--border-soft)' }}>
            <MapView parcelId={report.parcel_id} address={fullAddress} />
          </div>
          <div className="tnum" style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 7, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <span>{parcelGeo?.town_name ?? '—'}</span>
            {parcelGeo?.lot_size != null && (<><span>·</span><span>{parcelGeo.lot_size.toFixed(2)} ac</span></>)}
            {parcelGeo?.total_val != null && (<><span>·</span><span>{formatVal(parcelGeo.total_val)}</span></>)}
          </div>
        </div>
      </div>

      {/* ── Criteria cards ──────────────────────────────────────────────── */}
      <section className="card" style={{ padding: '22px', marginBottom: 20 }}>
        <div style={{ marginBottom: 16 }}>
          <h3 style={{ fontFamily: "'Fraunces', Georgia, serif", fontSize: 18, fontWeight: 500, letterSpacing: '-0.012em', margin: '0 0 5px', color: 'var(--text)' }}>
            Criteria breakdown
          </h3>
          <p style={{ fontSize: 12, color: 'var(--text-dim)', margin: 0 }}>
            Seven weighted criteria under 225 CMR 29.00. Click any card to expand full finding and all citations.
          </p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
          {report.criteria.map((c) => (
            <CriterionCard
              key={c.key}
              c={c}
              expanded={expanded === c.key}
              onToggle={() => setExpanded(expanded === c.key ? null : c.key)}
            />
          ))}
        </div>
      </section>

      {/* ── AI site characterization ────────────────────────────────────── */}
      <SiteAnalysisPanel parcelId={report.parcel_id} />

      {/* ── Permitting ──────────────────────────────────────────────────── */}
      <section style={{ marginBottom: 20 }}>
        <PermittingPanel parcelId={report.parcel_id} projectType={projectType} />
      </section>

      {/* ── Mitigation + Precedents ─────────────────────────────────────── */}
      <section style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Panel title="Mitigation hierarchy">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {mitigation.map((m, i) => (
              <article key={i} style={{ background: 'var(--surface)', border: '1px solid var(--border-soft)', borderRadius: 10, padding: '12px 14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, fontWeight: 500, color: 'var(--text)', letterSpacing: 0.3, textTransform: 'uppercase', marginBottom: 6 }}>
                  <span className="text-textDim">{String(i + 1).padStart(2, '0')}</span>
                  <span>{m.tier}</span>
                </div>
                <p className="text-textMid" style={{ fontSize: 13, lineHeight: 1.55, margin: 0 }}>{m.text}</p>
              </article>
            ))}
          </div>
        </Panel>

        <Panel title="Relevant precedents">
          {mitigationCosts && <MitigationCostBlock mitigation={mitigationCosts} />}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {precedents.length === 0 ? (
              <div className="text-textDim" style={{ fontSize: 13, lineHeight: 1.55 }}>
                No precedents loaded for this town yet.
              </div>
            ) : (
              precedents.map((p) => (
                <a key={p.id} href={p.source_url} target="_blank" rel="noreferrer"
                  style={{ textDecoration: 'none', background: 'var(--surface)', border: '1px solid var(--border-soft)', borderRadius: 10, padding: '12px 14px', color: 'inherit', display: 'block' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4, gap: 12 }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>
                        {p.applicant || p.project_address || p.docket || 'Unnamed project'}
                      </div>
                      <div className="text-textDim" style={{ fontSize: 11, marginTop: 3 }}>
                        {(p.decision_date || p.filing_date || p.created_at).slice(0, 10)} · {p.project_type}
                        {p.meeting_body ? ` · ${p.meeting_body}` : ''}
                      </div>
                    </div>
                    {p.decision && <PrecedentDecisionPill decision={p.decision} />}
                  </div>
                  {p.project_address && (
                    <p className="text-textMid" style={{ fontSize: 12, lineHeight: 1.5, margin: 0 }}>
                      {p.project_address}{p.docket ? ` · ${p.docket}` : ''}
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
// ScoreGauge
// -----------------------------------------------------------------------------
function ScoreGauge({ score, bucket }: { score: number; bucket: Bucket }) {
  const tone = bucketTone(bucket);
  const pct = Math.min(100, Math.max(0, score));

  return (
    <div className="card" style={{ padding: '20px 22px' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 14 }}>
        <span style={{ fontFamily: "'Fraunces', Georgia, serif", fontSize: 58, fontWeight: 400, letterSpacing: '-0.04em', lineHeight: 1, color: 'var(--text)' }}>
          {Math.round(score)}
        </span>
        <span style={{ fontSize: 14, color: 'var(--text-dim)', marginBottom: 4 }}>/ 100</span>
        <span style={{ fontSize: 13, fontWeight: 600, color: tone.c, background: tone.bg, padding: '4px 14px', borderRadius: 100, marginLeft: 4 }}>
          {tone.label}
        </span>
      </div>

      {/* Track */}
      <div style={{ position: 'relative', marginBottom: 4 }}>
        <div style={{ height: 8, borderRadius: 8, overflow: 'hidden', background: 'var(--border-soft)', position: 'relative' }}>
          {/* Zone fills */}
          <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: '50%', background: '#a85a4a', opacity: 0.1 }} />
          <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: '25%', background: '#c9a464', opacity: 0.1 }} />
          <div style={{ position: 'absolute', left: '75%', top: 0, bottom: 0, right: 0, background: '#6b7e5a', opacity: 0.1 }} />
          {/* Score fill */}
          <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${pct}%`, background: tone.c, borderRadius: '8px 0 0 8px', transition: 'width 0.6s ease' }} />
        </div>
        {/* Threshold ticks */}
        <div style={{ position: 'absolute', top: 0, bottom: 0, left: '50%', width: 2, background: 'var(--bg)', marginLeft: -1 }} />
        <div style={{ position: 'absolute', top: 0, bottom: 0, left: '75%', width: 2, background: 'var(--bg)', marginLeft: -1 }} />
      </div>

      {/* Labels */}
      <div style={{ position: 'relative', height: 18, marginBottom: 2 }}>
        <span style={{ position: 'absolute', left: 0, fontSize: 10, color: 'var(--text-dim)' }}>0 — Constrained</span>
        <span style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)', fontSize: 10, color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>50 — Conditional</span>
        <span style={{ position: 'absolute', right: 0, fontSize: 10, color: 'var(--text-dim)' }}>75+ — Suitable</span>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// PropertyRecord — replaces Strengths/Constraints in the findings card
// -----------------------------------------------------------------------------
function PropertyRecord({ parcelGeo }: { parcelGeo: ParcelGeoProps | null | undefined }) {
  if (!parcelGeo) return null;

  const useDesc = parcelGeo.use_code
    ? (USE_CODE[parcelGeo.use_code] ?? `Use code ${parcelGeo.use_code}`)
    : null;

  const lastSale = (() => {
    if (!parcelGeo.ls_date) return null;
    const s = String(parcelGeo.ls_date);
    if (s.length === 8) {
      const d = new Date(`${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`);
      return isNaN(d.getTime()) ? null : d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
    }
    return null;
  })();

  const zoningUrl = zoningVerifyUrl(parcelGeo.town_name);

  const rows: Array<{ label: string; value: string | null; verify?: string; note?: string }> = [
    {
      label: 'Owner',
      value: parcelGeo.owner1,
      note: parcelGeo.fy ? `assessor FY${parcelGeo.fy}` : 'assessor record',
    },
    {
      label: 'Zoning',
      value: parcelGeo.zoning,
      verify: zoningUrl,
      note: 'assessor est. — may not reflect recent rezoning',
    },
    { label: 'Use', value: useDesc },
    {
      label: 'Building',
      value: [
        parcelGeo.style,
        parcelGeo.bld_area != null ? `${parcelGeo.bld_area.toLocaleString()} sf` : null,
        parcelGeo.stories != null && parcelGeo.stories > 0
          ? `${parcelGeo.stories} ${parcelGeo.stories === 1 ? 'story' : 'stories'}`
          : null,
        parcelGeo.year_built ? `built ${parcelGeo.year_built}` : null,
      ].filter(Boolean).join(' · ') || null,
    },
    {
      label: 'Last sold',
      value: lastSale && parcelGeo.ls_price
        ? `${lastSale} · ${formatVal(parcelGeo.ls_price)}`
        : lastSale,
    },
    {
      label: 'Value split',
      value:
        parcelGeo.land_val != null && parcelGeo.bldg_val != null
          ? `Land ${formatVal(parcelGeo.land_val)} · Bldg ${formatVal(parcelGeo.bldg_val)}`
          : null,
    },
    {
      label: 'Assessor ref.',
      value: parcelGeo.city && parcelGeo.zip ? `${parcelGeo.city}, MA ${parcelGeo.zip}` : null,
    },
  ].filter((r) => r.value);

  if (rows.length === 0) return null;

  return (
    <div style={{ borderTop: '1px solid var(--border-soft)', paddingTop: 14, marginTop: 4 }}>
      <div className="label" style={{ marginBottom: 10 }}>Property record</div>
      <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '7px 16px', margin: 0 }}>
        {rows.map((r) => (
          <>
            <dt
              key={`dt-${r.label}`}
              style={{ fontSize: 11.5, color: 'var(--text-dim)', fontWeight: 500, whiteSpace: 'nowrap', alignSelf: 'baseline' }}
            >
              {r.label}
            </dt>
            <dd key={`dd-${r.label}`} style={{ fontSize: 12.5, color: 'var(--text-mid)', margin: 0, lineHeight: 1.45 }}>
              <span>{r.value}</span>
              {r.verify && (
                <a
                  href={r.verify}
                  target="_blank"
                  rel="noreferrer"
                  title={r.note}
                  style={{ marginLeft: 8, fontSize: 11, color: 'var(--accent)', textDecoration: 'none', whiteSpace: 'nowrap' }}
                >
                  verify ↗
                </a>
              )}
              {!r.verify && r.note && (
                <span style={{ marginLeft: 6, fontSize: 10.5, color: 'var(--text-dim)' }}>
                  · {r.note}
                </span>
              )}
            </dd>
          </>
        ))}
      </dl>
    </div>
  );
}

function zoningVerifyUrl(town: string | null | undefined): string {
  const TOWN_ZONING_URLS: Record<string, string> = {
    'BOSTON':      'https://maps.bostonplans.org/zoningviewer/',
    'CAMBRIDGE':   'https://www.cambridgema.gov/GIS/interactivemaps',
    'SOMERVILLE':  'https://online.encodeplus.com/regs/somerville-ma/',
    'FALMOUTH':    'https://www.falmouthma.gov/307/Zoning',
    'NEW BEDFORD': 'https://www.newbedford-ma.gov/planning/zoning/',
    'NATICK':      'https://www.natickma.gov/268/GIS',
    'BURLINGTON':  'https://www.burlington.org/departments/planning___development/zoning.php',
    'ACTON':       'https://www.acton-ma.gov/268/Zoning',
    'FREETOWN':    'https://www.freetownma.gov/planning-board',
    'WHATELY':     'https://www.whately.org/planning-board',
    'WORTHINGTON': 'https://www.worthington-ma.us/planning-board',
  };
  const key = (town ?? '').toUpperCase().trim();
  return TOWN_ZONING_URLS[key] ?? 'https://maps.massgis.digital.mass.gov/MassMapper/MassMapper.html';
}

// -----------------------------------------------------------------------------
// ParcelMetaStrip
// -----------------------------------------------------------------------------
function ParcelMetaStrip({ parcelGeo, projectType }: { parcelGeo: ParcelGeoProps | null | undefined; projectType: string }) {
  const items = [
    { label: 'Town', value: parcelGeo?.town_name || '—' },
    { label: 'Lot size', value: parcelGeo?.lot_size != null ? `${parcelGeo.lot_size.toFixed(2)} ac` : '—' },
    { label: 'Assessed value', value: parcelGeo?.total_val != null ? formatVal(parcelGeo.total_val) : '—' },
    { label: 'Project type', value: projectType.replace(/_/g, ' ') },
  ];
  return (
    <div className="card" style={{ padding: '14px 20px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 0 }}>
        {items.map((it) => (
          <div key={it.label}>
            <div style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 3 }}>
              {it.label}
            </div>
            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)', textTransform: 'capitalize' }}>
              {it.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatVal(v: number): string {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  return `$${(v / 1000).toFixed(0)}k`;
}

// -----------------------------------------------------------------------------
// IneligibilityAlert
// -----------------------------------------------------------------------------
function IneligibilityAlert({ flags }: { flags: string[] }) {
  if (!flags || flags.length === 0) return null;
  const names = flags.map((f) => INELIGIBLE_LAYER_NAMES[f] ?? f.replace(/_/g, ' ')).join(', ');
  return (
    <div style={{ background: 'var(--bad-soft, #f5e8e4)', border: '1px solid var(--bad, #a85a4a)', borderRadius: 12, padding: '16px 18px', marginBottom: 18 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: 100, background: 'var(--bad)', marginTop: 5, flexShrink: 0 }} />
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--bad)', marginBottom: 5 }}>
            225 CMR 29.06 — Ineligibility overlay detected
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-mid)', lineHeight: 1.6 }}>
            This parcel overlaps <strong style={{ color: 'var(--text)' }}>{names}</strong>.
            {' '}Under 225 CMR 29.06, projects on these mapped layers are not eligible for the simplified siting pathway.
            An alternatives analysis or significant footprint reduction is required before advancing.
          </div>
        </div>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// CriterionCard
// -----------------------------------------------------------------------------
function CriterionCard({ c, expanded, onToggle }: { c: CriterionScore; expanded: boolean; onToggle: () => void }) {
  const tone = statusTone(c.status);
  const PREVIEW = 220;
  const needsExpand = c.finding.length > PREVIEW || c.citations.length > 3;
  const displayFinding = expanded || !needsExpand
    ? c.finding
    : c.finding.slice(0, PREVIEW).replace(/\s\S*$/, '') + '…';
  const displayCitations = expanded ? c.citations : c.citations.slice(0, 3);

  const borderColor =
    c.status === 'ineligible' ? 'var(--bad, #a85a4a)' :
    c.status === 'flagged'    ? 'var(--gold, #c9a464)' :
    'var(--border-soft)';

  return (
    <div style={{ background: 'var(--surface)', border: `1px solid ${borderColor}`, borderRadius: 12, padding: '16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', marginBottom: 2 }}>
            {CRITERION_NAME[c.key] ?? c.name}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
            {CRITERION_DESC[c.key] ?? ''} · {Math.round(c.weight * 100)}% weight
          </div>
        </div>
        <span style={{ fontSize: 11, fontWeight: 500, color: tone.c, background: tone.bg, padding: '3px 10px', borderRadius: 100, whiteSpace: 'nowrap', flexShrink: 0 }}>
          {tone.label}
        </span>
      </div>

      {/* Score bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ flex: 1, height: 6, background: 'var(--border-soft)', borderRadius: 6, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${c.raw_score * 10}%`, background: tone.c, borderRadius: 6, transition: 'width 0.5s ease' }} />
        </div>
        <span className="tnum" style={{ fontSize: 14, fontWeight: 700, color: tone.c, minWidth: 46, textAlign: 'right' }}>
          {c.raw_score.toFixed(1)}<span style={{ fontSize: 10, fontWeight: 400, color: 'var(--text-dim)' }}> / 10</span>
        </span>
      </div>

      {/* Finding */}
      <p style={{ fontSize: 12.5, lineHeight: 1.65, margin: 0, color: 'var(--text-mid)' }}>
        {displayFinding}
      </p>

      {/* Citations */}
      {displayCitations.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
          {displayCitations.map((s, i) => <CitationChip key={i} s={s} />)}
        </div>
      )}

      {/* Expand toggle */}
      {needsExpand && (
        <button
          onClick={(e) => { e.stopPropagation(); onToggle(); }}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontSize: 11, color: 'var(--accent)', textAlign: 'left', alignSelf: 'flex-start' }}
        >
          {expanded ? '↑ Show less' : '↓ Full finding + all sources'}
        </button>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Panel
// -----------------------------------------------------------------------------
function Panel({ title, right, children, className }: {
  title: string; right?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={`card ${className ?? ''}`} style={{ padding: '22px 22px', marginBottom: className?.includes('mb-5') ? 20 : undefined }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 14, gap: 12 }}>
        <h3 style={{ fontFamily: "'Fraunces', Georgia, serif", fontSize: 18, fontWeight: 500, letterSpacing: '-0.012em', margin: 0, color: 'var(--text)' }}>
          {title}
        </h3>
        {right}
      </div>
      {children}
    </section>
  );
}

// -----------------------------------------------------------------------------
// buildSummary
// -----------------------------------------------------------------------------
interface FindingsSummary {
  verdict: string;
  narrative: string;
  recommendation: string | null;
}


function buildSummary(report: SuitabilityReport): FindingsSummary {
  const score = Math.round(report.total_score);
  const criteria = report.criteria.filter((c) => c.status !== 'data_unavailable');
  const primaryCriterion = report.primary_constraint ? criteria.find((c) => c.key === report.primary_constraint) : null;
  const primaryScore = primaryCriterion?.raw_score;
  const primary = report.primary_constraint ? CRITERION_NAME[report.primary_constraint] ?? report.primary_constraint : null;

  let verdict: string;
  if (report.bucket === 'SUITABLE') verdict = 'Clears the 225 CMR 29 threshold.';
  else if (report.bucket === 'CONDITIONALLY SUITABLE') verdict = 'Developable with targeted mitigation.';
  else verdict = 'Significant constraints — alternate siting advised.';

  let narrative: string;
  if (report.bucket === 'SUITABLE') {
    narrative = `At ${score}/100, this site meets the 225 CMR 29 suitability threshold.${
      primary && primaryScore != null
        ? ` ${primary} is the lowest-scoring factor at ${primaryScore.toFixed(1)}/10, but remains within the acceptable range.`
        : ' All seven criteria are within the acceptable range.'
    }`;
  } else if (report.bucket === 'CONDITIONALLY SUITABLE') {
    narrative = `At ${score}/100, this site is permittable subject to conditions.${
      primary && primaryScore != null
        ? ` ${primary} (${primaryScore.toFixed(1)}/10) is the binding factor — expect permit conditions and likely mitigation obligations.`
        : ' Multiple criteria approach the threshold; permit conditions are probable.'
    }`;
  } else {
    narrative = `At ${score}/100, this site has constraints that preclude straightforward permitting.${
      primary && primaryScore != null
        ? ` ${primary} scores ${primaryScore.toFixed(1)}/10 and is the primary driver.`
        : ' Multiple criteria fall below the acceptable range.'
    } An alternate parcel or a substantially reduced footprint is advisable before advancing.`;
  }

  const hasIneligible = report.criteria.some((c) => c.status === 'ineligible');
  let recommendation: string | null = null;
  if (hasIneligible) {
    recommendation = `Begin with ${primary ?? 'the flagged criterion'} — the Avoid tier in the mitigation hierarchy is the first lever. Consider an alternatives analysis under 225 CMR 29.06 if the footprint cannot be relocated.`;
  } else if (report.bucket === 'CONDITIONALLY SUITABLE' && primary) {
    recommendation = `Expand the ${primary} card below for the full finding and data sources, then review town precedents and the permitting panel.`;
  } else if (report.bucket === 'SUITABLE') {
    recommendation = 'Proceed to the municipal permitting panel to confirm the by-right or special-permit pathway and estimated timeline.';
  }

  return { verdict, narrative, recommendation };
}


// -----------------------------------------------------------------------------
// CitationChip
// -----------------------------------------------------------------------------
function CitationChip({ s }: { s: SourceCitation }) {
  const baseLabel = `${s.dataset}${s.detail ? ` · ${s.detail}` : ''}`;
  const healthy = !s.health || s.health.status === 'healthy';
  const wb = s.health?.wayback_url || null;

  if (!s.url) {
    return (
      <span style={{ fontSize: 12, color: 'var(--text-mid)', padding: '3px 10px', background: 'var(--surface-alt)', borderRadius: 100 }}>
        {baseLabel}
      </span>
    );
  }
  if (!healthy && wb) {
    return (
      <a href={wb} target="_blank" rel="noreferrer"
        title={`Original URL returns ${s.health?.status_code ?? '???'}. Showing Wayback snapshot.`}
        style={{ fontSize: 12, color: 'var(--text-mid)', padding: '3px 10px', background: 'var(--surface)', border: '1px dashed var(--border)', borderRadius: 100, textDecoration: 'none' }}>
        {baseLabel} · archived ↗
      </a>
    );
  }
  if (!healthy) {
    return (
      <a href={s.url} target="_blank" rel="noreferrer"
        title={`Original URL returns ${s.health?.status_code ?? '???'}. No archive available.`}
        style={{ fontSize: 12, color: 'var(--text-dim)', padding: '3px 10px', background: 'var(--surface-alt)', borderRadius: 100, textDecoration: 'line-through' }}>
        {baseLabel}
      </a>
    );
  }
  return (
    <a href={s.url} target="_blank" rel="noreferrer"
      style={{ fontSize: 12, color: 'var(--accent)', padding: '3px 10px', background: 'var(--accent-soft)', borderRadius: 100, textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      {baseLabel}
      <IconArrowUpRight size={11} />
    </a>
  );
}

// -----------------------------------------------------------------------------
// PrecedentDecisionPill
// -----------------------------------------------------------------------------
function PrecedentDecisionPill({ decision }: { decision: string }) {
  const denied = decision === 'denied';
  const withdrawn = decision === 'withdrawn';
  const pending = decision === 'pending' || decision === 'continued';
  const tone = denied || withdrawn ? STATUS.bad : pending ? STATUS.warn : STATUS.good;
  return (
    <div style={{ fontSize: 11, color: tone.c, background: tone.bg, padding: '3px 10px', borderRadius: 100, fontWeight: 500, whiteSpace: 'nowrap', textTransform: 'capitalize', letterSpacing: 0.2 }}>
      {decision.replace(/_/g, ' ')}
    </div>
  );
}

// -----------------------------------------------------------------------------
// MoratoriumBanner
// -----------------------------------------------------------------------------
function MoratoriumBanner({ moratoriums, projectType }: { moratoriums: Record<string, MoratoriumDetail>; projectType: ProjectTypeCode }) {
  const hit = findMoratoriumFor(moratoriums, projectType);
  if (!hit) return null;
  const [key, detail] = hit;
  const end = detail.end_date ? new Date(detail.end_date).toLocaleDateString() : null;
  const start = detail.start_date ? new Date(detail.start_date).toLocaleDateString() : null;
  return (
    <div style={{ background: 'var(--bad-soft, #f5e8e4)', border: '1px solid var(--bad, #a85a4a)', borderRadius: 12, padding: '14px 18px', marginBottom: 18, display: 'flex', alignItems: 'flex-start', gap: 12 }}>
      <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: 100, background: 'var(--bad)', marginTop: 5, flexShrink: 0 }} />
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--bad)' }}>Active moratorium on {key.replace(/_/g, ' ')} in this town</div>
        <div style={{ fontSize: 12, color: 'var(--text-mid)', marginTop: 4, lineHeight: 1.55 }}>
          {start && `Effective ${start}`}{start && end && ' · '}{end && `through ${end}`}
          {detail.source_url && (<>{(start || end) && ' · '}<a href={detail.source_url as string} target="_blank" rel="noreferrer" style={{ color: 'var(--bad)' }}>source ↗</a></>)}
          <div style={{ marginTop: 4, color: 'var(--text-dim)' }}>MA AG has historically rejected overly-broad moratoria; verify current enforceability with town counsel before advancing this site.</div>
        </div>
      </div>
    </div>
  );
}

function findMoratoriumFor(moratoriums: Record<string, MoratoriumDetail>, projectType: ProjectTypeCode): [string, MoratoriumDetail] | null {
  if (!moratoriums || Object.keys(moratoriums).length === 0) return null;
  const candidates: string[] = [projectType];
  if (projectType.startsWith('bess')) candidates.push('battery_storage', 'bess');
  if (projectType.startsWith('solar')) candidates.push('solar');
  if (projectType === 'substation' || projectType === 'transmission') candidates.push('grid_infrastructure');
  for (const k of candidates) {
    const hit = moratoriums[k];
    if (hit && typeof hit === 'object') {
      const end = hit.end_date ? new Date(hit.end_date) : null;
      if (end && end < new Date()) continue;
      return [k, hit];
    }
  }
  return null;
}

// -----------------------------------------------------------------------------
// ResolutionBanner
// -----------------------------------------------------------------------------
function ResolutionBanner({ resolution }: { resolution: ResolutionInfo | null }) {
  if (!resolution || resolution.mode === 'contains' || resolution.mode === 'addr_match') return null;
  const distDisplay = resolution.distance_m < 1000 ? `${Math.round(resolution.distance_m)} m` : `${(resolution.distance_m / 1609).toFixed(2)} mi`;
  const resolved = [resolution.resolved_site_addr, resolution.resolved_town].filter(Boolean).join(', ') || 'unnamed parcel';
  const modeCopy = {
    nearest: { title: 'Approximate match — scored the nearest parcel', body: `Your query didn't fall inside a parcel polygon we have indexed. We snapped to the closest parcel (${distDisplay} away). Try a more specific street address if this isn't the site you meant.` },
    esmp_anchored: { title: 'Anchored to a planned ESMP project', body: `Because the project type is substation or transmission and your query was near a planned ESMP project, we scored the parcel at the ESMP site (${distDisplay} from your query).` },
  }[resolution.mode];
  if (!modeCopy) return null;
  return (
    <div style={{ background: 'var(--gold-soft, #f7efe0)', border: '1px solid var(--gold, #c08a3e)', borderRadius: 12, padding: '14px 18px', marginBottom: 16, display: 'flex', gap: 12, alignItems: 'flex-start' }}>
      <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: 100, background: 'var(--gold, #c08a3e)', marginTop: 5, flexShrink: 0 }} />
      <div style={{ flex: 1, fontSize: 13, lineHeight: 1.55 }}>
        <div style={{ fontWeight: 600, color: 'var(--gold, #c08a3e)', marginBottom: 4 }}>{modeCopy.title}</div>
        <div style={{ color: 'var(--text-mid)' }}>{modeCopy.body}</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 14px', marginTop: 10, fontSize: 12 }}>
          <span className="text-textDim">You typed</span><span>{resolution.original_query}</span>
          {resolution.formatted_address && (<><span className="text-textDim">Google geocoded to</span><span>{resolution.formatted_address}</span></>)}
          <span className="text-textDim">Scored parcel</span><span>{resolved}</span>
        </div>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// MitigationCostBlock
// -----------------------------------------------------------------------------
function MitigationCostBlock({ mitigation }: { mitigation: MitigationCostEstimate }) {
  if (mitigation.items.length === 0 && !mitigation.hca.triggers) return null;
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border-soft)', borderRadius: 10, padding: '14px 16px', marginBottom: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div>
          <div className="label">Typical mitigation cost</div>
          <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: -0.3, marginTop: 2 }}>{mitigation.total_range_display}</div>
        </div>
        <span className="text-textDim" style={{ fontSize: 11 }}>
          {mitigation.precedent_count > 0 ? `${mitigation.precedent_count} precedent${mitigation.precedent_count === 1 ? '' : 's'} · industry benchmarks` : 'industry benchmarks'}
        </span>
      </div>
      <ul style={{ listStyle: 'none', padding: 0, margin: '10px 0 0', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {mitigation.items.map((it) => <MitigationRow key={it.category + it.label} item={it} />)}
        {mitigation.hca.triggers && <HcaRow hca={mitigation.hca} />}
      </ul>
      {mitigation.caveats.length > 0 && (
        <ul className="text-textDim" style={{ fontSize: 11, margin: '12px 0 0', padding: '0 0 0 16px', lineHeight: 1.55 }}>
          {mitigation.caveats.map((c, i) => <li key={i}>{c}</li>)}
        </ul>
      )}
    </div>
  );
}

function MitigationRow({ item }: { item: MitigationItem }) {
  return (
    <li style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12, alignItems: 'baseline' }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{item.label}</div>
        {item.note && <div className="text-textDim" style={{ fontSize: 11, marginTop: 2 }}>{item.note}</div>}
        {item.observed_in_precedents.length > 0 && (
          <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {item.observed_in_precedents.slice(0, 3).map((p, i) =>
              p.source_url ? (
                <a key={i} href={p.source_url} target="_blank" rel="noreferrer"
                  style={{ fontSize: 10, color: 'var(--accent)', background: 'var(--accent-soft)', padding: '2px 8px', borderRadius: 100, textDecoration: 'none' }}>
                  {p.applicant} ↗
                </a>
              ) : (
                <span key={i} style={{ fontSize: 10, color: 'var(--text-mid)', background: 'var(--surface-alt)', padding: '2px 8px', borderRadius: 100 }}>
                  {p.applicant}
                </span>
              )
            )}
          </div>
        )}
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', textAlign: 'right', whiteSpace: 'nowrap' }}>
        {item.range_display}
      </div>
    </li>
  );
}

function HcaRow({ hca }: { hca: HcaInfo }) {
  return (
    <li style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12, alignItems: 'baseline', paddingTop: 8, borderTop: '1px solid var(--border-soft)' }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500 }}>
          Host Community Agreement{' '}
          <span style={{ fontSize: 10, fontWeight: 500, color: 'var(--gold, #c08a3e)', background: 'var(--gold-soft, #f7efe0)', padding: '2px 8px', borderRadius: 100, marginLeft: 4 }}>
            likely triggered
          </span>
        </div>
        <div className="text-textDim" style={{ fontSize: 11, marginTop: 2 }}>
          {hca.reason}{hca.pct_of_capital_display && ` · ${hca.pct_of_capital_display}`}
        </div>
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, textAlign: 'right', whiteSpace: 'nowrap' }}>{hca.range_display || '—'}</div>
    </li>
  );
}

// -----------------------------------------------------------------------------
// mitigationFor
// -----------------------------------------------------------------------------
const mitigationFor = (primary: string | null | undefined, address: string) => {
  const common = [
    { tier: 'Avoid', text: 'Relocate or reduce the project footprint to eliminate overlap with the limiting constraint area.' },
    { tier: 'Minimize', text: 'Maintain buffers from sensitive resource areas. Keep disturbance under 50% of the parcel. Preserve existing vegetated corridors.' },
    { tier: 'Mitigate', text: 'Offsite restoration or in-lieu fee per 310 CMR 10.55 and applicable town wetland bylaws; SMART 3.0 benchmarks for solar apply.' },
  ];
  if (primary === 'biodiversity')
    return [
      { tier: 'Avoid', text: `Shift the project footprint away from the BioMap Core / NHESP Priority overlap near ${address}.` },
      { tier: 'Minimize', text: 'Reduce footprint below 5 acres; retain 100-foot buffer from wetland resource edge and any documented vernal pool.' },
      common[2],
    ];
  if (primary === 'climate_resilience')
    return [
      { tier: 'Avoid', text: 'Site equipment outside the Special Flood Hazard Area (FEMA A/AE/VE). No habitable basements in SFHA.' },
      { tier: 'Minimize', text: 'Elevate critical equipment ≥2 ft above BFE per ResilientMass standards. Flood-proof enclosures.' },
      { tier: 'Mitigate', text: 'Design storm water management to the 100-year + 20% climate adder; coordinate with MassDEP 401.' },
    ];
  if (primary === 'agriculture')
    return [
      { tier: 'Avoid', text: 'Relocate from Prime Farmland soils and Chapter 61A parcels where feasible.' },
      { tier: 'Minimize', text: 'Dual-use (agrivoltaic) configuration per SMART 3.0 ADU incentives; preserve top 18" topsoil.' },
      common[2],
    ];
  return common;
};
