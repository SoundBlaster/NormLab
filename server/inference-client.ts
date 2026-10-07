import { inferenceClientConfig } from './inference-config.js';
import { inferencePost } from './inference-http.js';

export type ParkingExtractor = (input: {
  narrative: string;
  sourceDigest: string;
}) => Promise<unknown>;
export function configuredParkingExtractor(
  env: NodeJS.ProcessEnv,
): ParkingExtractor | null | undefined {
  const config = inferenceClientConfig(env);
  if (config.mode === 'local') return undefined;
  if (config.mode === 'disabled') return null;
  return (input) =>
    inferencePost(
      `${config.url}/v1/extract`,
      config.token!,
      input,
      AbortSignal.timeout(305000),
      fetch,
      305000,
    );
}
