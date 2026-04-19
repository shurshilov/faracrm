import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';
// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  server: {
    host: process.env.DOCKER === 'true' ? '0.0.0.0' : '127.0.0.1',
    port: 5173,
  },
  // optimizeDeps: {
  // exclude: ['.vite'],
  // entries: ['./src/**/*.{js,jsx,ts,tsx}'],
  // },
  // resolve: {
  //   alias: {
  //     // /esm/icons/index.mjs only exports the icons statically, so no separate chunks are created
  //     '@tabler/icons-react': '@tabler/icons-react/dist/esm/icons/index.mjs',
  //   },
  // },
});
