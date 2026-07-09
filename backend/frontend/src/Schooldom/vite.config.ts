import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig, type PluginOption} from 'vite';

export default defineConfig({
  // Cast needed: @tailwindcss/vite v4 bundles Vite 6 types but installed Vite is v5.
  plugins: [react(), tailwindcss() as unknown as PluginOption],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  build: {
    assetsDir: 'lp-assets',
  },
  server: {
    hmr: process.env.DISABLE_HMR !== 'true',
    watch: process.env.DISABLE_HMR === 'true' ? null : {},
  },
});
