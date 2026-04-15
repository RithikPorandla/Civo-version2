/**
 * Google Photorealistic 3D Tiles viewer.
 *
 * Uses the Google Maps JavaScript API alpha3d Map3DElement web component.
 * Requires VITE_GOOGLE_MAPS_API_KEY in .env.local with both
 * "Map Tiles API" and "Maps JavaScript API" enabled.
 *
 * The component geocodes the address via the Places text-search on the
 * backend (/score uses the same cache), then centers the 3D camera over
 * the resolved lat/lng with a 65° tilt for an architectural-model feel.
 */
import { useEffect, useRef, useState } from 'react';

declare global {
  interface Window {
    google: any;
    initGoogleMaps?: () => void;
    __googleMapsScriptLoading?: Promise<void>;
  }
}

const API_KEY = (import.meta as any).env?.VITE_GOOGLE_MAPS_API_KEY as string | undefined;

function loadGoogleMaps(): Promise<void> {
  if (window.google?.maps?.Map3DElement) return Promise.resolve();
  if (window.__googleMapsScriptLoading) return window.__googleMapsScriptLoading;
  const promise = new Promise<void>((resolve, reject) => {
    const s = document.createElement('script');
    s.src = `https://maps.googleapis.com/maps/api/js?key=${API_KEY}&v=alpha&libraries=maps3d,marker,geometry`;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error('Google Maps failed to load'));
    document.head.appendChild(s);
  });
  window.__googleMapsScriptLoading = promise;
  return promise;
}

export default function ThreeDMap({
  address,
  lat,
  lng,
}: {
  address?: string;
  lat?: number;
  lng?: number;
}) {
  const host = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!API_KEY) {
      setErr('Missing VITE_GOOGLE_MAPS_API_KEY');
      return;
    }
    let cancelled = false;

    (async () => {
      try {
        await loadGoogleMaps();
        if (cancelled || !host.current) return;

        const { Map3DElement, MapMode } = await window.google.maps.importLibrary('maps3d');

        let center = lat != null && lng != null ? { lat, lng, altitude: 0 } : null;
        if (!center && address) {
          const { Geocoder } = await window.google.maps.importLibrary('geocoding');
          const geocoder = new Geocoder();
          const res = await geocoder.geocode({ address, componentRestrictions: { country: 'US' } });
          const g = res.results?.[0]?.geometry?.location;
          if (g) center = { lat: g.lat(), lng: g.lng(), altitude: 0 };
        }
        if (!center) center = { lat: 42.3626, lng: -71.0843, altitude: 0 };

        host.current.innerHTML = '';
        const map = new Map3DElement({
          center,
          range: 450,
          tilt: 65,
          heading: 30,
          mode: MapMode.SATELLITE,
        });
        map.style.width = '100%';
        map.style.height = '100%';
        host.current.appendChild(map);
      } catch (e: any) {
        setErr(String(e?.message || e));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [address, lat, lng]);

  return (
    <div ref={host} style={{ width: '100%', height: '100%', position: 'relative' }}>
      {err && (
        <div className="p-6 text-sm text-textMid">
          3D map unavailable — {err}.
          <br />
          Add <code>VITE_GOOGLE_MAPS_API_KEY</code> to <code>frontend/.env.local</code>
          and enable Map Tiles + Maps JavaScript APIs on your GCP project.
        </div>
      )}
    </div>
  );
}
