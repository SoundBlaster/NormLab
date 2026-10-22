import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';

const revision = process.env.NORMLAB_BUILD_REVISION?.trim() || null;
if (revision !== null && !/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/i.test(revision)) {
  throw new Error('NORMLAB_BUILD_REVISION must be a full Git commit SHA.');
}

export default defineConfig({
  root: 'client',
  base: process.env.VITE_BASE_PATH ?? '/',
  resolve: { alias: { '@': fileURLToPath(new URL('./client', import.meta.url)) } },
  define: {
    __NORMLAB_BUILD__: JSON.stringify({ revision, builtAt: new Date().toISOString() }),
  },
  build: { outDir: '../dist', emptyOutDir: true },
});
