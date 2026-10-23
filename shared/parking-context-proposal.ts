import { z } from 'zod';
import { narrativeContextSchema, narrativeContextIssues } from './parking-context.js';

export const contextSuggestionSchema = narrativeContextSchema
  .omit({ origin: true, decision: true })
  .refine(
    (value) =>
      narrativeContextIssues({ ...value, origin: 'human', decision: 'pending' }).length === 0,
    'Inconsistent proposed context.',
  );
export const contextProposalSchema = z.strictObject({
  schema: z.literal('normlab.parking-context-proposal/v1'),
  sourceDigest: z.string().regex(/^[a-f0-9]{64}$/),
  promptDigest: z.string().regex(/^[a-f0-9]{64}$/),
  configDigest: z.string().regex(/^[a-f0-9]{64}$/),
  model: z.string().min(1).max(256),
  usage: z.strictObject({
    inputTokens: z.number().int().nonnegative(),
    outputTokens: z.number().int().nonnegative(),
  }),
  suggestion: contextSuggestionSchema,
});
export type ContextProposal = z.infer<typeof contextProposalSchema>;
