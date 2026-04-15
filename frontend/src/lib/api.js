async function jf(path, init) {
    const res = await fetch(path, {
        ...init,
        headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    });
    if (!res.ok) {
        let detail = '';
        try {
            detail = JSON.stringify(await res.json());
        }
        catch {
            detail = await res.text();
        }
        throw new Error(`${res.status} ${res.statusText}: ${detail}`);
    }
    return res.json();
}
export const api = {
    health: () => jf('/health'),
    score: (address, project_type = 'generic') => jf('/score', {
        method: 'POST',
        body: JSON.stringify({ address, project_type }),
    }),
    listMunicipalities: () => jf('/municipalities'),
    getMunicipality: (townId) => jf(`/municipality/${townId}`),
    getProjectTypeBylaws: (townId, projectType) => jf(`/municipality/${townId}/bylaws/${projectType}`),
    report: (id) => jf(`/report/${id}`),
    parcelGeoJSON: (loc_id) => jf(`/parcel/${encodeURIComponent(loc_id)}/geojson`),
    parcelPrecedents: (loc_id, limit = 5) => jf(`/parcel/${encodeURIComponent(loc_id)}/precedents?limit=${limit}`),
    parcelOverlays: (loc_id, radius_m = 2000) => jf(`/parcel/${encodeURIComponent(loc_id)}/overlays?radius_m=${radius_m}`),
    portfolio: (id) => jf(`/portfolio/${id}`),
    createPortfolio: (body) => jf('/portfolio', { method: 'POST', body: JSON.stringify(body) }),
};
export const bucketTone = (b) => b === 'SUITABLE' ? 'good' : b === 'CONDITIONALLY SUITABLE' ? 'warn' : 'bad';
