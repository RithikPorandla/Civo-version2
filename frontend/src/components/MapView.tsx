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

// Each layer has a fill + outline tone + fill opacity. Article 97 parks /
// protected open space get their own warm-taupe treatment so they read as
// civic open space, distinct from BioMap habitat (sage) and NHESP (rust).
const LAYER_STYLE: Record<string, { fill: string; line: string; opacity: number }> = {
  article97: { fill: '#b5a07a', line: '#8b7355', opacity: 0.28 },
  biomap_core: { fill: '#4a7c4f', line: '#4a7c4f', opacity: 0.18 },
  biomap_cnl: { fill: '#4a7c4f', line: '#4a7c4f', opacity: 0.1 },
  nhesp_priority: { fill: '#a85a4a', line: '#a85a4a', opacity: 0.18 },
  nhesp_estimated: { fill: '#a85a4a', line: '#a85a4a', opacity: 0.1 },
  fema_flood: { fill: '#3f6b9c', line: '#3f6b9c', opacity: 0.18 },
  wetlands: { fill: '#525252', line: '#525252', opacity: 0.12 },
};

const CARTO_STYLE = 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json';

const SATELLITE_STYLE = {
  version: 8 as const,
  sources: {
    'esri-sat': {
      type: 'raster' as const,
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      ],
      tileSize: 256,
      attribution: 'Esri World Imagery',
      maxzoom: 19,
    },
    'esri-labels': {
      type: 'raster' as const,
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
      ],
      tileSize: 256,
      maxzoom: 19,
    },
  },
  layers: [
    { id: 'bg', type: 'background' as const, paint: { 'background-color': '#111' } },
    { id: 'esri-sat', type: 'raster' as const, source: 'esri-sat' },
    { id: 'esri-labels', type: 'raster' as const, source: 'esri-labels' },
  ],
};

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
  const [satellite, setSatellite] = useState(true);
  const [showParcelGrid, setShowParcelGrid] = useState(true);
  const [showLayers, setShowLayers] = useState(false);

  useEffect(() => {
    api.parcelOverlays(parcelId, 2000).then(setOverlay).catch(console.error);
  }, [parcelId]);

  // All parcel features — primary + sibling lot records with same address.
  const parcelFeats = useMemo(
    () => overlay?.features.filter((f) => f.properties?.layer === 'parcel') ?? [],
    [overlay]
  );
  const parcelFeat = parcelFeats[0] ?? null;

  useEffect(() => {
    if (parcelFeat?.properties) setParcelProps(parcelFeat.properties as any);
  }, [parcelFeat]);

  useEffect(() => {
    if (!loaded || parcelFeats.length === 0 || !mapRef.current) return;
    const bounds = new maplibregl.LngLatBounds();
    const walk = (c: any): void => {
      if (typeof c[0] === 'number') bounds.extend(c as [number, number]);
      else c.forEach(walk);
    };
    // Extend bounds across ALL parcel lots so the full site boundary is framed.
    parcelFeats.forEach((f) => walk((f.geometry as any).coordinates));
    mapRef.current.fitBounds(bounds, { padding: 80, duration: 0, maxZoom: 18 });
  }, [loaded, parcelFeats]);

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
      parcelFeats.length > 0
        ? ({ type: 'FeatureCollection', features: parcelFeats } as GeoJSON.FeatureCollection)
        : null,
    [parcelFeats]
  );

  // Parcel boundary styling flips between modes:
  // Satellite → bright amber so the line pops against dark imagery; dark shadow halo
  // Map       → dark ink stroke with white halo for the paper-map look
  const parcelStroke = satellite ? '#f5a623' : '#1a1a1a';
  const parcelHalo = satellite ? 'rgba(0,0,0,0.75)' : '#ffffff';
  const parcelFillOpacity = satellite ? 0.18 : 0.06;

  const addressText = (address || (parcelProps?.site_addr as string | undefined) || '').trim();
  const townText = (parcelProps?.town_name as string | undefined) || '';
  const locIdText = (parcelProps?.loc_id as string | undefined) || parcelId;

  return (
    <div className="w-full h-full overflow-hidden relative">
      <Map
        ref={mapRef}
        onLoad={() => setLoaded(true)}
        initialViewState={{ longitude: -71.5, latitude: 42.3, zoom: 10 }}
        mapStyle={satellite ? SATELLITE_STYLE : CARTO_STYLE}
        // Flat 2D only — no pitch, no drag-rotate. Keeps the output
        // PDF-deterministic and matches what Chris asked for (2D street map).
        maxPitch={0}
        dragRotate={false}
        attributionControl={false}
      >
        <NavigationControl position="top-right" showCompass={false} showZoom />


        {showLayers && Object.entries(polygons).map(([layer, feats]) => {
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

        {/* Context: all MassGIS L3 parcel boundaries in the current viewport */}
        {showParcelGrid && (
          <Source
            id="src-parcel-grid"
            type="raster"
            tileSize={256}
            tiles={[
              'https://services1.arcgis.com/hGdibHYSPO59RG1h/arcgis/rest/services/Massachusetts_Property_Tax_Parcels/MapServer/export?f=image&format=png32&transparent=true&size=256%2C256&bbox={bbox-epsg-3857}&bboxSR=102100&imageSR=102100&dpi=96',
            ]}
          >
            <Layer
              id="layer-parcel-grid"
              type="raster"
              paint={{ 'raster-opacity': satellite ? 0.55 : 0.45 }}
            />
          </Source>
        )}

        {parcelFc && (
          <Source id="src-parcel" type="geojson" data={parcelFc}>
            {/* Faint tint — on satellite helps the eye register the parcel area instantly */}
            <Layer
              id="parcel-fill"
              type="fill"
              paint={{ 'fill-color': '#f5a623', 'fill-opacity': parcelFillOpacity }}
            />
            {/* Shadow/halo behind the stroke so it reads on any basemap cell */}
            <Layer
              id="parcel-halo"
              type="line"
              paint={{ 'line-color': parcelHalo, 'line-width': 9, 'line-opacity': 0.9 }}
            />
            {/* Main boundary — amber on satellite, dark ink on map */}
            <Layer
              id="parcel-outline"
              type="line"
              paint={{ 'line-color': parcelStroke, 'line-width': 3, 'line-opacity': 1 }}
            />
          </Source>
        )}

        {showLayers && esmpPoints.features.length > 0 && (
          <Source id="src-esmp" type="geojson" data={esmpPoints}>
            <Layer
              id="pt-esmp-halo"
              type="circle"
              paint={{ 'circle-radius': 12, 'circle-color': '#8b7355', 'circle-opacity': 0.18 }}
            />
            <Layer
              id="pt-esmp"
              type="circle"
              paint={{
                'circle-radius': 5,
                'circle-color': '#8b7355',
                'circle-stroke-color': '#ffffff',
                'circle-stroke-width': 1.5,
              }}
            />
          </Source>
        )}
      </Map>

      {/* Satellite toggle — top right, below the nav control */}
      <button
        onClick={() => setSatellite((v) => !v)}
        style={{
          position: 'absolute',
          top: 86,
          right: 10,
          background: satellite ? 'var(--ink)' : 'var(--bg)',
          color: satellite ? 'var(--bg)' : 'var(--text)',
          border: '1px solid var(--border)',
          borderRadius: 6,
          padding: '5px 10px',
          fontSize: 11,
          fontWeight: 500,
          cursor: 'pointer',
          fontFamily: 'var(--sans)',
          boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
          letterSpacing: '0.03em',
        }}
        title={satellite ? 'Switch to street map' : 'Switch to satellite imagery'}
      >
        {satellite ? 'Map' : 'Satellite'}
      </button>

      {/* Environmental layers toggle — habitat, flood, NHESP, ESMP */}
      <button
        onClick={() => setShowLayers((v) => !v)}
        style={{
          position: 'absolute',
          top: 122,
          right: 10,
          background: showLayers ? 'var(--ink)' : 'var(--bg)',
          color: showLayers ? 'var(--bg)' : 'var(--text)',
          border: '1px solid var(--border)',
          borderRadius: 6,
          padding: '5px 10px',
          fontSize: 11,
          fontWeight: 500,
          cursor: 'pointer',
          fontFamily: 'var(--sans)',
          boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
          letterSpacing: '0.03em',
        }}
        title="Show environmental constraint layers (habitat, flood, NHESP)"
      >
        Layers
      </button>

      {/* All-parcels context grid toggle — shows MassGIS L3 boundary tiles for all nearby lots */}
      <button
        onClick={() => setShowParcelGrid((v) => !v)}
        style={{
          position: 'absolute',
          top: 158,
          right: 10,
          background: showParcelGrid ? 'var(--ink)' : 'var(--bg)',
          color: showParcelGrid ? 'var(--bg)' : 'var(--text)',
          border: '1px solid var(--border)',
          borderRadius: 6,
          padding: '5px 10px',
          fontSize: 11,
          fontWeight: 500,
          cursor: 'pointer',
          fontFamily: 'var(--sans)',
          boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
          letterSpacing: '0.03em',
        }}
        title="Show all parcel boundaries in view (MassGIS L3)"
      >
        All lots
      </button>

      {/* Address chip — visible on-screen AND in PDF prints */}
      {(addressText || townText) && (
        <div
          style={{
            position: 'absolute',
            top: 12,
            left: 12,
            background: 'var(--bg)',
            border: '1px solid var(--border-soft)',
            borderRadius: 8,
            padding: '8px 12px',
            boxShadow: '0 1px 2px rgba(15,15,15,0.05)',
            maxWidth: 440,
          }}
        >
          {addressText && (
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', lineHeight: 1.3 }}>
              {addressText}
            </div>
          )}
          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2, lineHeight: 1.4 }}>
            {townText && <span>{townText} · </span>}
            <span>Parcel {locIdText}</span>
          </div>
        </div>
      )}

      {/* Legend chip — bottom-left, only when environmental layers are active */}
      <div
        style={{
          position: 'absolute',
          bottom: 10,
          left: 12,
          background: 'var(--bg)',
          border: '1px solid var(--border-soft)',
          borderRadius: 8,
          padding: '6px 10px',
          fontSize: 11,
          color: 'var(--text-mid)',
          boxShadow: '0 1px 2px rgba(15,15,15,0.05)',
          display: 'flex',
          gap: 12,
          alignItems: 'center',
        }}
      >
        <LegendSwatch color={parcelStroke} label="Parcel" />
        {showLayers && <>
          <LegendSwatch color="#b5a07a" label="Parks · Art. 97" fill />
          <LegendSwatch color="#4a7c4f" label="Habitat" fill />
          <LegendSwatch color="#a85a4a" label="NHESP" fill />
          <LegendSwatch color="#3f6b9c" label="Flood" fill />
          <LegendSwatch color="#525252" label="Wetlands" fill />
        </>}
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
