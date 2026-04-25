import { useEffect, useMemo, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import Map, { Layer, MapRef, NavigationControl, Popup, Source } from 'react-map-gl/maplibre';
import type { DiscoverResultItem } from '../lib/api';

const CARTO_STYLE = 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json';

const SATELLITE_STYLE = {
  version: 8,
  sources: {
    esri: {
      type: 'raster',
      tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
      tileSize: 256,
      attribution: '© Esri',
    },
  },
  layers: [{ id: 'satellite', type: 'raster', source: 'esri' }],
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
} as any;

const BUCKET_COLOR: Record<string, string> = {
  SUITABLE: '#4a7c4f',
  'CONDITIONALLY SUITABLE': '#c08a3e',
  CONSTRAINED: '#a85a4a',
};
const BUCKET_DEFAULT = '#787878';

interface Props {
  results: DiscoverResultItem[];
  selectedId: string | null;
  hoveredId: string | null;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
  basemap?: 'street' | 'satellite';
}

export function DiscoverMap({ results, selectedId, hoveredId, onSelect, onHover, basemap = 'street' }: Props) {
  const mapRef = useRef<MapRef | null>(null);

  // Build GeoJSON for all result pins
  const geojson = useMemo<GeoJSON.FeatureCollection>(() => ({
    type: 'FeatureCollection',
    features: results.map((r) => ({
      type: 'Feature',
      id: r.parcel_id,
      properties: {
        id: r.parcel_id,
        label: r.site_addr || 'Unnamed parcel',
        town: r.town_name,
        score: r.total_score,
        bucket: r.bucket || 'UNSCORED',
        color: BUCKET_COLOR[r.bucket || ''] || BUCKET_DEFAULT,
      },
      geometry: { type: 'Point', coordinates: [r.lon, r.lat] },
    })),
  }), [results]);

  // Fit camera to results bbox when results change
  useEffect(() => {
    if (!mapRef.current || results.length === 0) return;
    const lons = results.map((r) => r.lon);
    const lats = results.map((r) => r.lat);
    const bounds = new maplibregl.LngLatBounds(
      [Math.min(...lons), Math.min(...lats)],
      [Math.max(...lons), Math.max(...lats)]
    );
    mapRef.current.fitBounds(bounds, { padding: 60, duration: 600, maxZoom: 14 });
  }, [results]);

  // Pan to selected parcel
  useEffect(() => {
    if (!mapRef.current || !selectedId) return;
    const r = results.find((x) => x.parcel_id === selectedId);
    if (!r) return;
    mapRef.current.easeTo({ center: [r.lon, r.lat], zoom: 14, duration: 400 });
  }, [selectedId, results]);

  const selectedResult = selectedId ? results.find((r) => r.parcel_id === selectedId) : null;

  return (
    <div className="w-full h-full overflow-hidden relative">
      <Map
        ref={mapRef}
        initialViewState={{ longitude: -71.5, latitude: 42.2, zoom: 8 }}
        mapStyle={basemap === 'satellite' ? SATELLITE_STYLE : CARTO_STYLE}
        maxPitch={0}
        dragRotate={false}
        attributionControl={false}
        interactiveLayerIds={['discover-pins', 'discover-pins-halo']}
        onClick={(e) => {
          const feat = e.features?.[0];
          if (feat?.properties?.id) onSelect(feat.properties.id);
        }}
        onMouseMove={(e) => {
          const feat = e.features?.[0];
          onHover(feat?.properties?.id ?? null);
        }}
        onMouseLeave={() => onHover(null)}
        cursor={hoveredId ? 'pointer' : 'grab'}
      >
        <NavigationControl position="top-right" showCompass={false} showZoom />

        {results.length > 0 && (
          <Source id="discover-src" type="geojson" data={geojson}>
            {/* Halo for selected / hovered */}
            <Layer
              id="discover-pins-halo"
              type="circle"
              paint={{
                'circle-radius': [
                  'case',
                  ['==', ['get', 'id'], selectedId ?? ''], 20,
                  ['==', ['get', 'id'], hoveredId ?? ''], 16,
                  0,
                ],
                'circle-color': ['get', 'color'],
                'circle-opacity': 0.22,
              }}
            />
            {/* Main pins */}
            <Layer
              id="discover-pins"
              type="circle"
              paint={{
                'circle-radius': [
                  'case',
                  ['==', ['get', 'id'], selectedId ?? ''], 10,
                  ['==', ['get', 'id'], hoveredId ?? ''], 9,
                  7,
                ],
                'circle-color': ['get', 'color'],
                'circle-stroke-color': '#ffffff',
                'circle-stroke-width': 1.5,
                'circle-opacity': 1,
              }}
            />
          </Source>
        )}

        {selectedResult && (
          <Popup
            longitude={selectedResult.lon}
            latitude={selectedResult.lat}
            closeButton
            closeOnClick={false}
            onClose={() => onSelect('')}
            maxWidth="260px"
            style={{ fontFamily: 'var(--sans)' }}
          >
            <div style={{ padding: '4px 2px' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', lineHeight: 1.3 }}>
                {selectedResult.site_addr || 'Unnamed parcel'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
                {selectedResult.town_name} · {selectedResult.lot_size_acres?.toFixed(1) ?? '?'} ac
              </div>
              {selectedResult.bucket && (
                <div
                  style={{
                    marginTop: 6,
                    fontSize: 11,
                    fontWeight: 500,
                    color: BUCKET_COLOR[selectedResult.bucket] || BUCKET_DEFAULT,
                  }}
                >
                  {selectedResult.bucket}
                  {selectedResult.total_score != null
                    ? ` · ${Math.round(selectedResult.total_score)}/100`
                    : ''}
                </div>
              )}
            </div>
          </Popup>
        )}
      </Map>

      {/* Empty state overlay */}
      {results.length === 0 && (
        <div
          style={{
            position: 'absolute',
            bottom: 16,
            left: '50%',
            transform: 'translateX(-50%)',
            background: 'var(--bg)',
            border: '1px solid var(--border-soft)',
            borderRadius: 10,
            padding: '8px 16px',
            fontSize: 12,
            color: 'var(--text-dim)',
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
          }}
        >
          Massachusetts · ESMP project sites visible after search
        </div>
      )}

      {/* Legend */}
      {results.length > 0 && (
        <div
          style={{
            position: 'absolute',
            bottom: 10,
            left: 10,
            background: 'var(--bg)',
            border: '1px solid var(--border-soft)',
            borderRadius: 8,
            padding: '6px 10px',
            display: 'flex',
            gap: 10,
            alignItems: 'center',
            fontSize: 11,
            color: 'var(--text-mid)',
            boxShadow: '0 1px 2px rgba(15,15,15,0.05)',
          }}
        >
          {Object.entries(BUCKET_COLOR).map(([label, color]) => (
            <span key={label} style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: color,
                  display: 'inline-block',
                }}
              />
              {label === 'CONDITIONALLY SUITABLE' ? 'Conditional' : label.charAt(0) + label.slice(1).toLowerCase()}
            </span>
          ))}
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: BUCKET_DEFAULT,
                display: 'inline-block',
              }}
            />
            Unscored
          </span>
        </div>
      )}
    </div>
  );
}
