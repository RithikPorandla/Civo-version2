export type CriterionStatus = 'ok' | 'flagged' | 'ineligible' | 'data_unavailable';
export type Bucket = 'SUITABLE' | 'CONDITIONALLY SUITABLE' | 'CONSTRAINED';

export interface LinkHealthInfo {
  status: 'healthy' | 'broken';
  status_code: number | null;
  wayback_url: string | null;
  final_url: string | null;
  checked_at: string | null;
}

export interface SourceCitation {
  dataset: string;
  row_id?: string | null;
  url?: string | null;
  detail?: string | null;
  health?: LinkHealthInfo | null;
}

export interface CriterionScore {
  key: string;
  name: string;
  weight: number;
  raw_score: number;
  weighted_contribution: number;
  status: CriterionStatus;
  finding: string;
  citations: SourceCitation[];
}

export interface ResolutionInfo {
  mode: 'contains' | 'esmp_anchored' | 'nearest';
  original_query: string;
  formatted_address?: string | null;
  resolved_site_addr?: string | null;
  resolved_town?: string | null;
  distance_m: number;
}

export interface SuitabilityReport {
  parcel_id: string;
  address?: string | null;
  project_type: string;
  config_version: string;
  methodology: string;
  computed_at: string;
  total_score: number;
  bucket: Bucket;
  primary_constraint?: string | null;
  ineligible_flags: string[];
  criteria: CriterionScore[];
  citations: SourceCitation[];
  resolution?: ResolutionInfo | null;
}

export interface ScoreEnvelope {
  report_id: number;
  address: string;
  resolution_mode: 'contains' | 'nearest' | 'esmp_anchored';
  report: SuitabilityReport;
}

export interface PortfolioItem {
  rank: number;
  address: string;
  parcel_id?: string | null;
  score_report_id?: number | null;
  total_score?: number | null;
  bucket?: Bucket | null;
  resolution_mode?: string | null;
  ok: boolean;
  error?: string | null;
}

export interface PortfolioEnvelope {
  id: string;
  state: string;
  name?: string | null;
  project_type?: string | null;
  config_version: string;
  created_at: string;
  scored_at: string;
  items: PortfolioItem[];
}

async function jf<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let detail = '';
    try {
      detail = JSON.stringify(await res.json());
    } catch {
      detail = await res.text();
    }
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return res.json();
}

export type ProjectTypeCode =
  | 'solar_ground_mount'
  | 'solar_rooftop'
  | 'solar_canopy'
  | 'bess_standalone'
  | 'bess_colocated'
  | 'substation'
  | 'transmission'
  | 'ev_charging';

export interface MunicipalitySummary {
  town_id: number;
  town_name: string;
  project_types: string[];
  last_refreshed_at: string | null;
}

export interface MunicipalityDetail {
  town_id: number;
  town_name: string;
  county: string | null;
  project_type_bylaws: Record<string, any>;
  last_refreshed_at: string | null;
}

export const api = {
  health: () => jf<{
    database: boolean;
    postgis: string;
    pgvector: string;
    parcels_loaded: number;
    esmp_projects_loaded: number;
    municipalities_loaded: number;
    status: string;
  }>('/health'),
  score: (address: string, project_type = 'generic') =>
    jf<ScoreEnvelope>('/score', {
      method: 'POST',
      body: JSON.stringify({ address, project_type }),
    }),
  listMunicipalities: () => jf<MunicipalitySummary[]>('/municipalities'),
  getMunicipality: (townId: number) =>
    jf<MunicipalityDetail>(`/municipality/${townId}`),
  getProjectTypeBylaws: (townId: number, projectType: ProjectTypeCode) =>
    jf<{ town_id: number; town_name: string; project_type: ProjectTypeCode; bylaws: any }>(
      `/municipality/${townId}/bylaws/${projectType}`
    ),
  report: (id: number | string) => jf<SuitabilityReport>(`/report/${id}`),
  parcelGeoJSON: (loc_id: string) =>
    jf<GeoJSON.Feature>(`/parcel/${encodeURIComponent(loc_id)}/geojson`),
  parcelPrecedents: (loc_id: string, limit = 5) =>
    jf<Array<{
      id: number;
      docket: string | null;
      project_type: string;
      project_address: string | null;
      applicant: string | null;
      decision: string | null;
      decision_date: string | null;
      filing_date: string | null;
      meeting_body: string | null;
      source_url: string;
      full_text: string | null;
      confidence: number | null;
      created_at: string;
    }>>(`/parcel/${encodeURIComponent(loc_id)}/precedents?limit=${limit}`),
  parcelOverlays: (loc_id: string, radius_m = 2000) =>
    jf<GeoJSON.FeatureCollection & { properties: { truncated: boolean; counts: Record<string, number> } }>(
      `/parcel/${encodeURIComponent(loc_id)}/overlays?radius_m=${radius_m}`
    ),
  portfolio: (id: string) => jf<PortfolioEnvelope>(`/portfolio/${id}`),
  createPortfolio: (body: { name?: string; addresses: string[]; project_type?: string }) =>
    jf<PortfolioEnvelope>('/portfolio', { method: 'POST', body: JSON.stringify(body) }),
};

export const bucketTone = (b?: Bucket | null) =>
  b === 'SUITABLE' ? 'good' : b === 'CONDITIONALLY SUITABLE' ? 'warn' : 'bad';

// ---------------------------------------------------------------------------
// DOER tracking + exemption check
// ---------------------------------------------------------------------------
export type DoerProjectType = 'solar' | 'bess';
export type DoerAdoptionStatus = 'adopted' | 'in_progress' | 'not_started' | 'unknown';
export type DoerSeverity = 'minor' | 'moderate' | 'major';
export type DoerSafeHarbor = 'safe' | 'at_risk' | 'unknown';

export interface DoerDeviation {
  category: string;
  severity: DoerSeverity;
  tier_context: string;
  town_value: string | null;
  doer_value: string | null;
  summary: string;
  dover_risk: boolean;
  source_bylaw_ref: string | null;
}

export interface DoerComparisonResult {
  project_type: DoerProjectType;
  comparison_available: boolean;
  reason_unavailable: string | null;
  deviations: DoerDeviation[];
  deviation_counts: Record<DoerSeverity, number>;
  dover_amendment_risk: boolean;
  doer_version_compared: string | null;
}

export interface DoerAdoptionDetail {
  project_type: DoerProjectType;
  adoption_status: DoerAdoptionStatus;
  adopted_date: string | null;
  town_meeting_article: string | null;
  current_local_bylaw_url: string | null;
  modification_summary: string | null;
  doer_circuit_rider: string | null;
  confidence: number;
  source_url: string;
  source_type: string;
  last_checked: string | null;
  doer_version_ref: string | null;
  comparison: DoerComparisonResult | null;
  safe_harbor_status: DoerSafeHarbor;
}

export interface DoerStatusResponse {
  town_id: number;
  town_name: string;
  solar: DoerAdoptionDetail | null;
  bess: DoerAdoptionDetail | null;
  deadline: string;
  days_remaining: number;
  other_project_types_note: string;
}

export interface ExemptionCheck {
  is_exempt: boolean | null;
  reason: string | null;
  regulation_reference: string;
  missing_fields: string[];
}

export interface ExemptionRequest {
  project_type: string;
  nameplate_capacity_kw?: number | null;
  site_footprint_acres?: number | null;
  is_behind_meter?: boolean;
  is_accessory_use?: boolean;
  in_existing_public_row?: boolean;
  td_design_rating_kv?: number | null;
}

export const doerApi = {
  townStatus: (townId: number) => jf<DoerStatusResponse>(`/towns/${townId}/doer-status`),
  checkExemption: (req: ExemptionRequest) =>
    jf<ExemptionCheck>('/exemption-check', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
};

// ---------------------------------------------------------------------------
// Mitigation cost estimates (grounded in precedents + industry benchmarks)
// ---------------------------------------------------------------------------
export interface MitigationItem {
  category: string;
  label: string;
  low: number;
  high: number;
  range_display: string;
  observed_in_precedents: Array<{ applicant: string; source_url: string | null }>;
  note: string | null;
}

export interface HcaInfo {
  triggers: boolean;
  reason: string | null;
  low: number;
  high: number;
  range_display?: string;
  pct_of_capital_display?: string;
}

export interface MitigationCostEstimate {
  project_type: string;
  items: MitigationItem[];
  hca: HcaInfo;
  total_low: number;
  total_high: number;
  total_range_display: string;
  precedent_count: number;
  caveats: string[];
}

export interface MoratoriumDetail {
  type?: string;
  start_date?: string | null;
  end_date?: string | null;
  source_url?: string | null;
  [k: string]: unknown;
}

export interface MoratoriumResponse {
  town_id: number | null;
  town_name: string | null;
  moratoriums: Record<string, MoratoriumDetail>;
}

export const reportApi = {
  mitigationCosts: (
    parcelId: string,
    args: {
      project_type: string;
      nameplate_kw?: number | null;
      site_footprint_acres?: number | null;
      wetland_impact_acres?: number | null;
    }
  ) => {
    const p = new URLSearchParams({ project_type: args.project_type });
    if (args.nameplate_kw != null) p.set('nameplate_kw', String(args.nameplate_kw));
    if (args.site_footprint_acres != null)
      p.set('site_footprint_acres', String(args.site_footprint_acres));
    if (args.wetland_impact_acres != null)
      p.set('wetland_impact_acres', String(args.wetland_impact_acres));
    return jf<MitigationCostEstimate>(
      `/parcel/${encodeURIComponent(parcelId)}/mitigation-costs?${p.toString()}`
    );
  },
  moratoriums: (parcelId: string) =>
    jf<MoratoriumResponse>(`/parcel/${encodeURIComponent(parcelId)}/moratoriums`),
};
