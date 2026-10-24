import { inferenceClientConfig } from './inference-config.js';
import { inferencePost } from './inference-http.js';
import {
  hostedProfileSchema,
  hostedStageResultSchema,
  type HostedStageTransport,
} from '../shared/hosted-stage.js';
import { hostedStageDigest } from './hosted-stages.js';
import { InferenceAccessError } from './inference-errors.js';
import { contextProposalSchema } from '../shared/parking-context-proposal.js';
import {
  legalProposalInputSchema,
  legalProposalMatches,
  legalProposalSchema,
  type LegalProposalInput,
} from '../shared/parking-legal-proposal.js';
import { digest } from './hash.js';

export type ParkingExtractor = ((input: {
  narrative: string;
  sourceDigest: string;
}) => Promise<unknown>) & {
  stages?: HostedStageTransport;
  context?: (input: { narrative: string; sourceDigest: string }) => Promise<unknown>;
  legalProposal?: (input: LegalProposalInput) => Promise<unknown>;
};
export function configuredParkingExtractor(
  env: NodeJS.ProcessEnv,
): ParkingExtractor | null | undefined {
  const config = inferenceClientConfig(env);
  if (config.mode === 'local') return undefined;
  if (config.mode === 'disabled') return null;
  const extractor: ParkingExtractor = (input) =>
    inferencePost(
      `${config.url}/v1/extract`,
      config.token!,
      input,
      AbortSignal.timeout(305000),
      fetch,
      305000,
      { provider: 'gateway', stage: 'extraction' },
      true,
    );
  extractor.stages = hostedStageTransport(config.url!, config.token!);
  extractor.context = async (input) => {
    const result = contextProposalSchema.safeParse(
      await inferencePost(
        `${config.url}/v1/context`,
        config.token!,
        input,
        AbortSignal.timeout(150000),
        fetch,
        150000,
        { provider: 'gateway', stage: 'context' },
        true,
      ),
    );
    if (!result.success || result.data.sourceDigest !== input.sourceDigest)
      throw new InferenceAccessError({
        provider: 'gateway',
        stage: 'context',
        code: 'invalid_response',
      });
    return result.data;
  };
  extractor.legalProposal = async (rawInput) => {
    const input = legalProposalInputSchema.parse(rawInput);
    const result = legalProposalSchema.safeParse(
      await inferencePost(
        `${config.url}/v1/legal-proposal`,
        config.token!,
        input,
        AbortSignal.timeout(150000),
        fetch,
        150000,
        { provider: 'gateway', stage: 'legal-proposal' },
        true,
      ),
    );
    if (
      !result.success ||
      !legalProposalMatches(input, result.data) ||
      result.data.inputDigest !== digest(input)
    )
      throw new InferenceAccessError({
        provider: 'gateway',
        stage: 'legal-proposal',
        code: 'invalid_response',
      });
    return result.data;
  };
  return extractor;
}

/** Internal app-to-gateway transport. Browser requests cannot choose its destination. */
export function hostedStageTransport(
  url: string,
  token: string,
  fetcher: typeof fetch = fetch,
): HostedStageTransport {
  const post = (path: string, input: unknown, signal: AbortSignal) =>
    inferencePost(
      `${url}${path}`,
      token,
      input,
      signal,
      fetcher,
      305000,
      { provider: 'gateway', stage: 'extraction' },
      true,
    );
  return {
    profile: async (signal) => {
      const profile = hostedProfileSchema.safeParse(await post('/v1/profile', {}, signal));
      if (!profile.success)
        throw new InferenceAccessError({
          provider: 'gateway',
          stage: 'extraction',
          code: 'invalid_response',
        });
      return profile.data;
    },
    execute: async (input, signal) => {
      const parsed = hostedStageResultSchema.safeParse(await post('/v1/stage', input, signal));
      if (!parsed.success)
        throw new InferenceAccessError({
          provider: 'gateway',
          stage: input.stage,
          code: 'invalid_response',
        });
      const result = parsed.data;
      if (
        result.inputDigest !== hostedStageDigest(input) ||
        result.configDigest !== input.configDigest ||
        result.sourceDigest !== input.sourceDigest ||
        result.stage !== input.stage ||
        (result.stage === 'classification' &&
          input.stage === 'classification' &&
          result.batchIndex !== input.batchIndex)
      )
        throw new InferenceAccessError({
          provider: 'gateway',
          stage: input.stage,
          code: 'invalid_response',
        });
      return result;
    },
  };
}
