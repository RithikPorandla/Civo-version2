import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The backend owns these URL prefixes. Vite forwards XHR/fetch requests
// here through its proxy.
//
// BUT: browser NAVIGATIONS (URL-bar visits to `/report/123`, `/municipalities/2`)
// use the same paths and would otherwise be proxied — returning JSON instead
// of our SPA. The `bypass` function detects navigations by `Accept: text/html`
// and returns the SPA index so react-router can pick up the route client-side.
const apiRoutes = [
  '/health',
  '/score',
  '/report',
  '/parcel',
  '/portfolio',
  '/municipalities',
  '/municipality',
  '/towns',
  '/exemption-check',
  '/data-sources',
  '/esmp-projects',
  '/discover',
];

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      apiRoutes.map((p) => [
        p,
        {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          bypass: (req) => {
            const accept = (req.headers.accept || '').toString();
            if (accept.includes('text/html')) {
              // Let the SPA handle this URL client-side.
              return '/index.html';
            }
          },
        },
      ])
    ),
  },
});
