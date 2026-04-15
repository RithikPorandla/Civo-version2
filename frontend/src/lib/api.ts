export type CriterionStatus = 'ok' | 'flagged' | 'ineligible' | 'data_unavailable';
export type Bucket = 'SUITABLE' | 'CONDITIONALLY SUITABLE' | 'CONSTRAINED';

export interface SourceCitation {
  dataset: string;
  row_id?: string | null;
  url?: string | null;
  detail?: string | null;
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
