import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../lib/api';
import maplibregl from 'maplibre-gl';
import Map, { Layer, MapRef, NavigationControl, Source } from 'react-map-gl/maplibre';

/**
 * PDF-friendly parcel map.
 *
 * Per the 2026-04-17 Chris meeting: he asked for a cleaner site map
 * with labeled streets + property boundary + address, that renders
 * well when exported to PDF. Esri World Imagery was "too complex,
 * doesn't load sometimes" and the 3D pitch was overkill.
 *
 * Choices:
 * - CartoDB Voyager as the basemap — light, has street labels, vector
 *   style so it renders crisply at any scale (including PDF print).
 * - 2D only (no pitch), no rotate UI — the reports are ground-truth
 *   documents, not fly-around experiences.
 * - Parcel outline is rendered with a white halo + accent stroke so it
 *   reads clearly over the basemap without looking like a map markup.
 * - A label chip at the top-left carries the site address so a PDF
 *   viewer knows what they're looking at even out of context.
 */

const LAYER_STYLE: Record<string, { fill: string; line: string; opacity: number }> = {
  biomap_core: { fill: '#4a7c4f', line: '#4a7c4f', opacity: 0.18 },
  biomap_cnl: { fill: '#4a7c4f', line: '#4a7c4f', opacity: 0.1 },
  nhesp_priority: { fill: '#a85a4a', line: '#a85a4a', opacity: 0.18 },
  nhesp_estimated: { fill: '#a85a4a', line: '#a85a4a', opacity: 0.1 },
  fema_flood: { fill: '#2563eb', line: '#2563eb', opacity: 0.16 },
  wetlands: { fill: '#525252', line: '#525252', opacity: 0.12 },
};

const CARTO_STYLE = 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json';

interface Props {
  parcelId: string;
  /** Optional address label shown top-left on the map (used on Report page). */
  address?: string | null;
}

export function MapView({ parcelId, address }: Props) {
  const mapRef = useRef<MapRef | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [overlay, setOverlay] = useState<GeoJSON.FeatureCollection | null>(null);
  const [parcelProps, setParcelProps] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    api.parcelOverlays(parcelId, 2000).then(setOverlay).catch(console.error);
  }, [parcelId]);

  const parcelFeat = useMemo(
    () => overlay?.features.find((f) => f.properties?.layer === 'parcel'),
    [overlay]
  );

  useEffect(() => {
    if (parcelFeat?.properties) setParcelProps(parcelFeat.properties as any);
  }, [parcelFeat]);

  useEffect(() => {
    if (!loaded || !parcelFeat || !mapRef.current) return;
    const bounds = new maplibregl.LngLatBounds();
    const walk = (c: any): void => {
      if (typeof c[0] === 'number') bounds.extend(c as [number, number]);
      else c.forEach(walk);
    };
    walk((parcelFeat.geometry as any).coordinates);
    // Flat, tight framing — the parcel is the subject.
    mapRef.current.fitBounds(bounds, { padding: 80, duration: 0, maxZoom: 18 });
  }, [loaded, parcelFeat]);

  const polygons = useMemo(() => {
    const grouped: Record<string, GeoJSON.Feature[]> = {};
    overlay?.features.forEach((f) => {
      const layer = (f.properties as any)?.layer || 'other';
      if (f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon') {
        grouped[layer] = grouped[layer] || [];
        grouped[layer].push(f);
      }
    });
    return grouped;
  }, [overlay]);

  const esmpPoints = useMemo(() => {
    const pts = overlay?.features.filter((f) => (f.properties as any)?.layer === 'esmp') || [];
    return { type: 'FeatureCollection' as const, features: pts };
  }, [overlay]);

  const parcelFc = useMemo(
    () =>
      parcelFeat
        ? ({ type: 'FeatureCollection', features: [parcelFeat] } as GeoJSON.FeatureCollection)
        : null,
    [parcelFeat]
  );

  const addressText = (address || (parcelProps?.site_addr as string | undefined) || '').trim();
  const townText = (parcelProps?.town_name as string | undefined) || '';
  const locIdText = (parcelProps?.loc_id as string | undefined) || parcelId;

  return (
    <div className="w-full h-full overflow-hidden relative">
      <Map
        ref={mapRef}
        onLoad={() => setLoaded(true)}
        initialViewState={{ longitude: -71.5, latitude: 42.3, zoom: 10 }}
        mapStyle={CARTO_STYLE}
        // Flat 2D only — no pitch, no drag-rotate. Keeps the output
        // PDF-deterministic and matches what Chris asked for (2D street map).
        maxPitch={0}
        dragRotate={false}
        attributionControl={false}
      >
        <NavigationControl position="top-right" showCompass={false} showZoom />

        {Object.entries(polygons).map(([layer, feats]) => {
          if (layer === 'parcel') return null;
          const style = LAYER_STYLE[layer];
          if (!style) return null;
          const fc = { type: 'FeatureCollection', features: feats } as GeoJSON.FeatureCollection;
          return (
            <Source key={layer} id={`src-${layer}`} type="geojson" data={fc}>
              {style.fill !== 'transparent' && (
                <Layer
                  id={`fill-${layer}`}
                  type="fill"
                  paint={{ 'fill-color': style.fill, 'fill-opacity': style.opacity }}
                />
              )}
              <Layer
                id={`line-${layer}`}
                type="line"
                paint={{
                  'line-color': style.line,
                  'line-width': 1,
                  'line-opacity': 0.75,
                }}
              />
            </Source>
          );
        })}

        {parcelFc && (
          <Source id="src-parcel" type="geojson" data={parcelFc}>
            {/* white halo under the parcel stroke so it stays legible on any basemap cell */}
            <Layer
              id="parcel-halo"
              type="line"
              paint={{ 'line-color': '#ffffff', 'line-width': 6, 'line-opacity': 0.95 }}
            />
            <Layer
              id="parcel-outline"
              type="line"
              paint={{ 'line-color': '#1a1a1a', 'line-width': 2.5, 'line-opacity': 1 }}
            />
          </Source>
        )}

        {esmpPoints.features.length > 0 && (
          <Source id="src-esmp" type="geojson" data={esmpPoints}>
            <Layer
              id="pt-esmp-halo"
              type="circle"
              paint={{ 'circle-radius': 12, 'circle-color': '#2563eb', 'circle-opacity': 0.18 }}
            />
            <Layer
              id="pt-esmp"
              type="circle"
              paint={{
                'circle-radius': 5,
                'circle-color': '#2563eb',
                'circle-stroke-color': '#ffffff',
                'circle-stroke-width': 1.5,
              }}
            />
          </Source>
        )}
      </Map>

      {/* Address chip — visible on-screen AND in PDF prints */}
      {(addressText || townText) && (
        <div
          style={{
            position: 'absolute',
            top: 12,
            left: 12,
            background: '#ffffff',
            border: '1px solid #e8eaed',
            borderRadius: 8,
            padding: '8px 12px',
            boxShadow: '0 1px 2px rgba(15,15,15,0.05)',
            maxWidth: 320,
          }}
        >
          {addressText && (
            <div style={{ fontSize: 13, fontWeight: 600, color: '#1a1a1a', lineHeight: 1.3 }}>
              {addressText}
            </div>
          )}
          <div style={{ fontSize: 11, color: '#8a8a8a', marginTop: 2, lineHeight: 1.4 }}>
            {townText && <span>{townText} · </span>}
            <span>Parcel {locIdText}</span>
          </div>
        </div>
      )}

      {/* Legend chip — bottom-left */}
      <div
        style={{
          position: 'absolute',
          bottom: 10,
          left: 12,
          background: '#ffffff',
          border: '1px solid #e8eaed',
          borderRadius: 8,
          padding: '6px 10px',
          fontSize: 11,
          color: '#525252',
          boxShadow: '0 1px 2px rgba(15,15,15,0.05)',
          display: 'flex',
          gap: 12,
          alignItems: 'center',
        }}
      >
        <LegendSwatch color="#1a1a1a" label="Parcel" />
        <LegendSwatch color="#4a7c4f" label="Habitat" fill />
        <LegendSwatch color="#a85a4a" label="NHESP" fill />
        <LegendSwatch color="#2563eb" label="Flood" fill />
        <LegendSwatch color="#525252" label="Wetlands" fill />
      </div>
    </div>
  );
}

function LegendSwatch({ color, label, fill }: { color: string; label: string; fill?: boolean }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span
        aria-hidden="true"
        style={{
          width: 10,
          height: 10,
          borderRadius: 2,
          background: fill ? color : 'transparent',
          border: `1.5px solid ${color}`,
          opacity: fill ? 0.55 : 1,
          display: 'inline-block',
        }}
      />
      {label}
    </span>
  );
}
