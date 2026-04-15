import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../lib/api';
import maplibregl from 'maplibre-gl';
import Map, { Layer, Source } from 'react-map-gl/maplibre';
const LAYER_STYLE = {
    parcel: { fill: 'transparent', line: '#8b7355', opacity: 1 },
    biomap_core: { fill: '#4a7c4f', line: '#4a7c4f', opacity: 0.22 },
    biomap_cnl: { fill: '#4a7c4f', line: '#4a7c4f', opacity: 0.1 },
    nhesp_priority: { fill: '#a85a4a', line: '#a85a4a', opacity: 0.18 },
    nhesp_estimated: { fill: '#a85a4a', line: '#a85a4a', opacity: 0.1 },
    fema_flood: { fill: '#c08a3e', line: '#c08a3e', opacity: 0.2 },
    wetlands: { fill: '#6b6b6b', line: '#6b6b6b', opacity: 0.12 },
};
export function MapView({ parcelId }) {
    const mapRef = useRef(null);
    const [loaded, setLoaded] = useState(false);
    const [overlay, setOverlay] = useState(null);
    useEffect(() => {
        api.parcelOverlays(parcelId, 2000).then(setOverlay).catch(console.error);
    }, [parcelId]);
    const parcelFeat = useMemo(() => overlay?.features.find((f) => f.properties?.layer === 'parcel'), [overlay]);
    useEffect(() => {
        if (!loaded || !parcelFeat || !mapRef.current)
            return;
        const bounds = new maplibregl.LngLatBounds();
        const walk = (c) => {
            if (typeof c[0] === 'number') {
                bounds.extend(c);
            }
            else {
                c.forEach(walk);
            }
        };
        walk(parcelFeat.geometry.coordinates);
        mapRef.current.fitBounds(bounds, { padding: 80, duration: 0, maxZoom: 15 });
    }, [loaded, parcelFeat]);
    const polygons = useMemo(() => {
        const grouped = {};
        overlay?.features.forEach((f) => {
            const layer = f.properties?.layer || 'other';
            if (f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon') {
                grouped[layer] = grouped[layer] || [];
                grouped[layer].push(f);
            }
        });
        return grouped;
    }, [overlay]);
    const esmpPoints = useMemo(() => {
        const pts = overlay?.features.filter((f) => f.properties?.layer === 'esmp') || [];
        return { type: 'FeatureCollection', features: pts };
    }, [overlay]);
    return (_jsx("div", { className: "w-full h-[540px] rounded-lg border hairline overflow-hidden", children: _jsxs(Map, { ref: mapRef, onLoad: () => setLoaded(true), initialViewState: { longitude: -71.5, latitude: 42.3, zoom: 10 }, mapStyle: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json", attributionControl: false, children: [Object.entries(polygons).map(([layer, feats]) => {
                    const style = LAYER_STYLE[layer];
                    if (!style)
                        return null;
                    const fc = { type: 'FeatureCollection', features: feats };
                    return (_jsxs(Source, { id: `src-${layer}`, type: "geojson", data: fc, children: [style.fill !== 'transparent' && (_jsx(Layer, { id: `fill-${layer}`, type: "fill", paint: { 'fill-color': style.fill, 'fill-opacity': style.opacity } })), _jsx(Layer, { id: `line-${layer}`, type: "line", paint: {
                                    'line-color': style.line,
                                    'line-width': layer === 'parcel' ? 2.5 : 1,
                                    'line-opacity': layer === 'parcel' ? 1 : 0.7,
                                } })] }, layer));
                }), esmpPoints.features.length > 0 && (_jsxs(Source, { id: "src-esmp", type: "geojson", data: esmpPoints, children: [_jsx(Layer, { id: "pt-esmp-halo", type: "circle", paint: {
                                'circle-radius': 11,
                                'circle-color': '#8b7355',
                                'circle-opacity': 0.12,
                            } }), _jsx(Layer, { id: "pt-esmp", type: "circle", paint: {
                                'circle-radius': 5,
                                'circle-color': '#8b7355',
                                'circle-stroke-color': '#ffffff',
                                'circle-stroke-width': 1.5,
                            } })] }))] }) }));
}
