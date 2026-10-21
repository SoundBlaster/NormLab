import type { InferenceGatewayConfig } from './inference-config.js';
import type { InferenceProviders } from './inference-providers.js';
import {
  HOSTED_PROMPT_DIGEST,
  HOSTED_DECISIONS_PROMPT_DIGEST,
  sourceDigest,
  discoverHostedFragments,
  classifyHostedFragments,
} from './hosted-extraction.js';
import {
  hostedProfileSchema,
  hostedStageInputSchema,
  hostedStageResultSchema,
  type HostedStageInput,
} from '../shared/hosted-stage.js';

export function hostedProfile(config: InferenceGatewayConfig) {
  const classificationModel =
    config.classifier === 'openai'
      ? config.openaiModel
      : config.classifier === 'decisions'
        ? config.decisionsModel
        : config.typesafeModel;
  const classificationEndpoint =
    config.classifier === 'openai'
      ? config.endpoints.openai.url
      : config.classifier === 'decisions'
        ? config.endpoints.decisions.url
        : config.endpoints.typesafe.url;
  const profile = {
    protocol: 'normlab.hosted-stage/v1' as const,
    classifier: config.classifier,
    discoveryModel: config.openaiModel,
    classificationModel,
    batchSize: 8 as const,
    maxFragments: 256 as const,
  };
  return hostedProfileSchema.parse({
    ...profile,
    configDigest: sourceDigest(
      JSON.stringify({
        ...profile,
        discoveryEndpoint: config.endpoints.openai.url,
        classificationEndpoint,
        promptDigest:
          config.classifier === 'decisions' ? HOSTED_DECISIONS_PROMPT_DIGEST : HOSTED_PROMPT_DIGEST,
      }),
    ),
  });
}

/** Deterministic parsed field order; never the integer-only canonical artifact hash. */
export const hostedStageDigest = (input: HostedStageInput) =>
  sourceDigest(JSON.stringify(hostedStageInputSchema.parse(input)));

/** Validate every source anchor and batch ID before spending quota or making a provider call. */
export function checkedHostedStage(input: unknown): HostedStageInput {
  const parsed = hostedStageInputSchema.parse(input);
  if (sourceDigest(parsed.narrative) !== parsed.sourceDigest)
    throw new Error('Source binding mismatch.');
  if (parsed.stage === 'classification') {
    for (const [index, fragment] of parsed.fragments.entries()) {
      if (
        fragment.fragmentId !== `fragment_${parsed.batchIndex * 8 + index + 1}` ||
        fragment.endOffset !== fragment.startOffset + fragment.quote.length ||
        parsed.narrative.slice(fragment.startOffset, fragment.endOffset) !== fragment.quote ||
        parsed.narrative.indexOf(fragment.quote) !== fragment.startOffset ||
        parsed.narrative.indexOf(fragment.quote, fragment.startOffset + 1) !== -1
      )
        throw new Error('Invalid stage fragment.');
    }
    if (
      new Set(parsed.fragments.map((f) => JSON.stringify([f.quote, f.attributes]))).size !==
      parsed.fragments.length
    )
      throw new Error('Duplicate stage fragment.');
  }
  return parsed;
}

export async function runHostedStage(
  input: HostedStageInput,
  providers: InferenceProviders,
  config: InferenceGatewayConfig,
  signal: AbortSignal,
) {
  const parsed = checkedHostedStage(input);
  if (parsed.configDigest !== hostedProfile(config).configDigest)
    throw new Error('Stage configuration changed.');
  const binding = {
    protocol: 'normlab.hosted-stage/v1' as const,
    inputDigest: hostedStageDigest(parsed),
    sourceDigest: parsed.sourceDigest,
    configDigest: parsed.configDigest,
  };
  if (parsed.stage === 'discovery')
    return hostedStageResultSchema.parse({
      ...binding,
      stage: parsed.stage,
      ...(await discoverHostedFragments(parsed.narrative, providers, signal)),
    });
  return hostedStageResultSchema.parse({
    ...binding,
    stage: parsed.stage,
    batchIndex: parsed.batchIndex,
    ...(await classifyHostedFragments(parsed.fragments, providers, config.classifier, signal)),
  });
}
