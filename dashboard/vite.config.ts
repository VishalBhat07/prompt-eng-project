import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

const gateway = process.env.CTG_DASHBOARD_GATEWAY ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  server: {
    port: 5173,
    proxy: {
      '/api': gateway,
      '/ws': { target: gateway.replace(/^http/, 'ws'), ws: true },
    },
  },
});
