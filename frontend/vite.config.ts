import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Proxy API calls to the FastAPI backend in dev so CORS is a non-issue.
const apiRoutes = ['/health', '/score', '/report', '/parcel', '/portfolio'];

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      apiRoutes.map((p) => [p, { target: 'http://127.0.0.1:8000', changeOrigin: true }])
    ),
  },
});
