import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';

export default defineConfig({
  root: 'client',
  base: process.env.VITE_BASE_PATH ?? '/',
  resolve: { alias: { '@': fileURLToPath(new URL('./client', import.meta.url)) } },
  build: { outDir: '../dist', emptyOutDir: true },
});
