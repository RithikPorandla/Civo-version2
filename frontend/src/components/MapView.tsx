import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../lib/api';
import maplibregl from 'maplibre-gl';
import Map, { Layer, MapRef, Source } from 'react-map-gl/maplibre';

const LAYER_STYLE: Record<string, { fill: string; line: string; opacity: number }> = {
  parcel: { fill: 'transparent', line: '#8b7355', opacity: 1 },
  biomap_core: { fill: '#4a7c4f', line: '#4a7c4f', opacity: 0.22 },
  biomap_cnl: { fill: '#4a7c4f', line: '#4a7c4f', opacity: 0.1 },
  nhesp_priority: { fill: '#a85a4a', line: '#a85a4a', opacity: 0.18 },
  nhesp_estimated: { fill: '#a85a4a', line: '#a85a4a', opacity: 0.1 },
  fema_flood: { fill: '#c08a3e', line: '#c08a3e', opacity: 0.2 },
  wetlands: { fill: '#6b6b6b', line: '#6b6b6b', opacity: 0.12 },
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
    mapRef.current.fitBounds(bounds, { padding: 80, duration: 0, maxZoom: 15 });
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

  return (
    <div className="w-full h-[540px] rounded-lg border hairline overflow-hidden">
      <Map
        ref={mapRef}
        onLoad={() => setLoaded(true)}
        initialViewState={{ longitude: -71.5, latitude: 42.3, zoom: 10 }}
        mapStyle="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"
        attributionControl={false}
      >
        {Object.entries(polygons).map(([layer, feats]) => {
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
                  'line-width': layer === 'parcel' ? 2.5 : 1,
                  'line-opacity': layer === 'parcel' ? 1 : 0.7,
                }}
              />
            </Source>
          );
        })}

        {esmpPoints.features.length > 0 && (
          <Source id="src-esmp" type="geojson" data={esmpPoints}>
            <Layer
              id="pt-esmp-halo"
              type="circle"
              paint={{
                'circle-radius': 11,
                'circle-color': '#8b7355',
                'circle-opacity': 0.12,
              }}
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
    </div>
  );
}
