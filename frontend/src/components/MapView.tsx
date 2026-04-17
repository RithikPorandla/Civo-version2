import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../lib/api';
import maplibregl from 'maplibre-gl';
import Map, {
  Layer,
  MapRef,
  NavigationControl,
  Source,
} from 'react-map-gl/maplibre';
import type { StyleSpecification } from 'maplibre-gl';

const LAYER_STYLE: Record<string, { fill: string; line: string; opacity: number }> = {
  parcel: { fill: 'transparent', line: '#f4d03f', opacity: 1 },
  biomap_core: { fill: '#4a7c4f', line: '#6fbf73', opacity: 0.32 },
  biomap_cnl: { fill: '#4a7c4f', line: '#6fbf73', opacity: 0.18 },
  nhesp_priority: { fill: '#a85a4a', line: '#ff7a66', opacity: 0.28 },
  nhesp_estimated: { fill: '#a85a4a', line: '#ff7a66', opacity: 0.18 },
  fema_flood: { fill: '#c08a3e', line: '#ffb84a', opacity: 0.3 },
  wetlands: { fill: '#6b6b6b', line: '#cfcfcf', opacity: 0.2 },
};

const SATELLITE_STYLE: StyleSpecification = {
  version: 8,
  glyphs: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/glyphs/{fontstack}/{range}.pbf',
  sources: {
    esri: {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      ],
      tileSize: 256,
      attribution: 'Imagery © Esri, Maxar, Earthstar Geographics',
    },
  },
  layers: [
    {
      id: 'esri-tiles',
      type: 'raster',
      source: 'esri',
      minzoom: 0,
      maxzoom: 22,
    },
  ],
};

interface Props {
  parcelId: string;
}

export function MapView({ parcelId }: Props) {
  const mapRef = useRef<MapRef | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [overlay, setOverlay] = useState<GeoJSON.FeatureCollection | null>(null);

  useEffect(() => {
    api.parcelOverlays(parcelId, 2000).then(setOverlay).catch(console.error);
  }, [parcelId]);

  const parcelFeat = useMemo(
    () => overlay?.features.find((f) => f.properties?.layer === 'parcel'),
    [overlay]
  );

  useEffect(() => {
    if (!loaded || !parcelFeat || !mapRef.current) return;
    const bounds = new maplibregl.LngLatBounds();
    const walk = (c: any): void => {
      if (typeof c[0] === 'number') {
        bounds.extend(c as [number, number]);
      } else {
        c.forEach(walk);
      }
    };
    walk((parcelFeat.geometry as any).coordinates);
    mapRef.current.fitBounds(bounds, { padding: 90, duration: 0, maxZoom: 18 });
    mapRef.current.easeTo({ pitch: 50, bearing: 20, duration: 600 });
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

  return (
    <div className="w-full h-full overflow-hidden relative">
      <Map
        ref={mapRef}
        onLoad={() => setLoaded(true)}
        initialViewState={{
          longitude: -71.5,
          latitude: 42.3,
          zoom: 10,
          pitch: 45,
          bearing: 0,
        }}
        mapStyle={SATELLITE_STYLE}
        maxPitch={85}
        dragRotate
        pitchWithRotate
        attributionControl={false}
      >
        <NavigationControl position="top-right" visualizePitch showCompass showZoom />

        {Object.entries(polygons).map(([layer, feats]) => {
          if (layer === 'parcel') return null; // rendered separately below, above other layers
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
                  'line-width': 1.2,
                  'line-opacity': 0.85,
                }}
              />
            </Source>
          );
        })}

        {parcelFc && (
          <Source id="src-parcel" type="geojson" data={parcelFc}>
            <Layer
              id="parcel-halo"
              type="line"
              paint={{
                'line-color': '#000000',
                'line-width': 6,
                'line-opacity': 0.55,
              }}
            />
            <Layer
              id="parcel-outline"
              type="line"
              paint={{
                'line-color': LAYER_STYLE.parcel.line,
                'line-width': 2.5,
                'line-opacity': 1,
              }}
            />
          </Source>
        )}

        {esmpPoints.features.length > 0 && (
          <Source id="src-esmp" type="geojson" data={esmpPoints}>
            <Layer
              id="pt-esmp-halo"
              type="circle"
              paint={{
                'circle-radius': 12,
                'circle-color': '#f4d03f',
                'circle-opacity': 0.25,
              }}
            />
            <Layer
              id="pt-esmp"
              type="circle"
              paint={{
                'circle-radius': 5,
                'circle-color': '#f4d03f',
                'circle-stroke-color': '#1a1a1a',
                'circle-stroke-width': 1.5,
              }}
            />
          </Source>
        )}
      </Map>
      <div
        style={{
          position: 'absolute',
          left: 12,
          bottom: 10,
          fontSize: 10,
          color: 'rgba(255,255,255,0.85)',
          background: 'rgba(0,0,0,0.45)',
          padding: '3px 8px',
          borderRadius: 4,
          letterSpacing: 0.3,
          pointerEvents: 'none',
        }}
      >
        Imagery © Esri · Right-click + drag to tilt · Shift + drag to rotate
      </div>
    </div>
  );
}
