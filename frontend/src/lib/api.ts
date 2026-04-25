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
  moratorium_active: boolean;
  moratoriums: Record<string, MoratoriumDetail> | null;
}

export interface MunicipalityDetail {
  town_id: number;
  town_name: string;
  county: string | null;
  project_type_bylaws: Record<string, any>;
  last_refreshed_at: string | null;
  moratorium_active: boolean;
  moratoriums: Record<string, MoratoriumDetail> | null;
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
  dataSources: () => jf<DataSourcesResponse>('/data-sources'),
};

// ---------------------------------------------------------------------------
// Data sources (public provenance index)
// ---------------------------------------------------------------------------
export type DataSourceCategory =
  | 'spatial'
  | 'regulatory'
  | 'municipal'
  | 'benchmark'
  | 'external';

export type DataSourceStatus = 'ingested' | 'planned' | 'external';

export interface DataSource {
  id: string;
  name: string;
  agency: string;
  category: DataSourceCategory;
  url?: string | null;
  docket?: string | null;
  coverage?: string | null;
  used_by: string[];
  tables: string[];
  row_count?: number | null;
  last_refreshed?: string | null;
  last_reviewed?: string | null;
  citation_format?: string | null;
  status: DataSourceStatus;
  notes?: string | null;
}

export interface DataSourcesResponse {
  last_reviewed: string;
  total_sources: number;
  by_category: Record<string, number>;
  sources: DataSource[];
}

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

// ---------------------------------------------------------------------------
// Candidate site discovery (ESMP-anchored)
// ---------------------------------------------------------------------------
export type Utility = 'Eversource' | 'National Grid' | 'Unitil' | 'Unknown';

export interface EsmpAnchor {
  id: number;
  project_name: string;
  project_type: string | null;
  mw: number | null;
  municipality: string | null;
  source_filing: string;
  siting_status: string | null;
  utility: Utility;
  lat: number;
  lon: number;
}

export interface CandidateSite {
  parcel_id: string;
  site_addr: string | null;
  town_name: string | null;
  lot_size_acres: number | null;
  distance_to_anchor_m: number;
  distance_to_anchor_mi: number;
  use_code: string | null;
  total_val: number | null;
  total_score: number | null;
  bucket: string | null;
  primary_constraint: string | null;
  composite_rank: number;
}

export interface CandidateSearchResponse {
  anchor: Record<string, unknown>;
  project_type: string;
  radius_m: number;
  min_acres: number;
  max_acres: number;
  config_version: string;
  pre_filter_count: number;
  scored_count: number;
  candidates: CandidateSite[];
}

// ---------------------------------------------------------------------------
// NL-powered Discover API (new)
// ---------------------------------------------------------------------------

export interface DiscoverResultItem {
  parcel_id: string;
  site_addr: string | null;
  town_name: string;
  lot_size_acres: number | null;
  lat: number;
  lon: number;
  total_score: number | null;
  bucket: Bucket | null;
  primary_constraint: string | null;
  in_biomap_core: boolean;
  in_nhesp_priority: boolean;
  in_flood_zone: boolean;
  in_wetlands: boolean;
  in_article97: boolean;
  moratorium_active: boolean;
  doer_status: string | null;
  risk_multiplier: number;
}

export interface DiscoverInterpretedFilters {
  municipalities: string[];
  sub_region: string | null;
  min_acres: number | null;
  max_acres: number | null;
  exclude_layers: string[];
  include_layers: string[];
  doer_bess_status: string | null;
  doer_solar_status: string | null;
  project_type: string | null;
  project_size_mw: number | null;
  min_score: number | null;
  sort_by: string;
}

export interface DiscoverCitation {
  claim: string;
  source: string;
}

export interface DiscoverResponse {
  query_id: string;
  intent_type: string;
  interpreted_filters: DiscoverInterpretedFilters;
  results: DiscoverResultItem[];
  narrative: string | null;
  citations: DiscoverCitation[];
  total_count: number;
  confidence: number;
}

export const discoverNlApi = {
  search: (query: string, limit = 50) =>
    jf<DiscoverResponse>('/discover', {
      method: 'POST',
      body: JSON.stringify({ query, limit }),
    }),
  suggestions: (q = '') =>
    jf<string[]>(`/discover/suggestions${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  followup: (query_id: string, follow_up: string, limit = 50) =>
    jf<DiscoverResponse>('/discover/followup', {
      method: 'POST',
      body: JSON.stringify({ query_id, follow_up, limit }),
    }),
};

export const discoverApi = {
  listAnchors: (utility?: string, sitingStatus?: string) => {
    const p = new URLSearchParams();
    if (utility) p.set('utility', utility);
    if (sitingStatus) p.set('siting_status', sitingStatus);
    const qs = p.toString();
    return jf<EsmpAnchor[]>(`/esmp-projects${qs ? '?' + qs : ''}`);
  },
  findCandidates: (
    anchorId: number,
    args: {
      project_type: string;
      radius_m?: number;
      min_acres?: number;
      max_acres?: number;
      limit?: number;
    }
  ) => {
    const p = new URLSearchParams({ project_type: args.project_type });
    if (args.radius_m != null) p.set('radius_m', String(args.radius_m));
    if (args.min_acres != null) p.set('min_acres', String(args.min_acres));
    if (args.max_acres != null) p.set('max_acres', String(args.max_acres));
    if (args.limit != null) p.set('limit', String(args.limit));
    return jf<CandidateSearchResponse>(`/esmp-projects/${anchorId}/candidates?${p.toString()}`);
  },
};

// ---------------------------------------------------------------------------
// AI site characterization (Claude vision on the aerial tile)
// ---------------------------------------------------------------------------
export interface SiteCharacterization {
  impervious_pct: number;
  tree_canopy_pct: number;
  open_ground_pct: number;
  water_visible: boolean;
  water_description: string | null;
  detected_building_count: number;
  detected_paved_area_description: string | null;
  surface_breakdown: Array<{ surface: string; pct: number }>;
  narrative: string;
  site_characteristics: string[];
  confidence: number;
}

export interface SiteAnalysisReconciliation {
  massgis_developed_pct: number | null;
  vision_impervious_pct: number;
  delta: number | null;
  flag: 'aligned' | 'diverges' | null;
  note: string | null;
}

export interface SiteAnalysisResponse {
  parcel_loc_id: string;
  vision_version: string;
  model_id: string;
  image_source: string;
  image_bbox_wgs84: { lon_w: number; lat_s: number; lon_e: number; lat_n: number };
  characterization: SiteCharacterization;
  reconciliation: SiteAnalysisReconciliation | null;
  cached: boolean;
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
  siteAnalysis: (parcelId: string, force = false) =>
    jf<SiteAnalysisResponse>(
      `/parcel/${encodeURIComponent(parcelId)}/site-analysis${force ? '?force=true' : ''}`
    ),
};
