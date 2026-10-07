import { resolve } from 'node:path';
import { readFileSync } from 'node:fs';
import { createApp } from './app.js';
import { configuredParkingExtractor } from './inference-client.js';

const port = Number(process.env.PORT ?? 4317);
const host = process.env.HOST ?? '127.0.0.1';
const operatorAuthEnabled = process.env.NORMLAB_OPERATOR_AUTH_ENABLED === 'true';
const operatorPasswordFile = process.env.NORMLAB_OPERATOR_AUTH_PASSWORD_FILE;
const operatorPassword = operatorPasswordFile
  ? readFileSync(operatorPasswordFile, 'utf8').replace(/\r?\n$/, '')
  : process.env.NORMLAB_OPERATOR_AUTH_PASSWORD;
if (!Number.isInteger(port) || port < 1 || port > 65535)
  throw new Error('PORT must be between 1 and 65535');
const app = await createApp({
  dataDir: resolve(process.env.NORMLAB_DATA_DIR ?? '.data'),
  production: process.argv.includes('--production'),
  publicOrigin: process.env.NORMLAB_PUBLIC_ORIGIN,
  parkingExtractor: configuredParkingExtractor({
    ...process.env,
    NORMLAB_INFERENCE_MODE:
      process.env.NORMLAB_INFERENCE_MODE ??
      (process.argv.includes('--production') ? 'disabled' : 'local'),
  }),
  operatorAuth: operatorAuthEnabled
    ? {
        username: process.env.NORMLAB_OPERATOR_AUTH_USERNAME ?? '',
        password: operatorPassword ?? '',
      }
    : undefined,
});
app.server.listen(port, host, () => console.log(`NormLab → http://127.0.0.1:${port}`));
app.server.on('error', async (error) => {
  console.error(error.message);
  await app.close();
  process.exitCode = 1;
});
for (const signal of ['SIGINT', 'SIGTERM'] as const)
  process.once(signal, async () => {
    await app.close();
    process.exit(0);
  });
