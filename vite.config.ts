import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';

export default defineConfig({
  root: 'client',
  resolve: { alias: { '@': fileURLToPath(new URL('./client', import.meta.url)) } },
  build: { outDir: '../dist', emptyOutDir: true },
});
