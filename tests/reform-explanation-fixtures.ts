import type { ReformSnapshot, ReformSnapshotInput } from '../shared/reform-contracts.js';
import { digest } from '../server/hash.js';

export const findingStates = ['unreviewed', 'established', 'refuted', 'not-established'] as const;
export function explanationSnapshot(
  group: 'K1' | 'K2' = 'K1',
  M: (typeof findingStates)[number] = 'established',
  N: (typeof findingStates)[number] = 'not-established',
  E: (typeof findingStates)[number] = 'refuted',
): ReformSnapshot {
  const finding = (state: (typeof findingStates)[number]) => ({
    state,
    rationale: state === 'unreviewed' ? '' : 'Synthetic rationale',
  });
  const input: ReformSnapshotInput = {
    narrative: 'Synthetic explanation scenario',
    group,
    findings: { M: finding(M), N: finding(N), E: finding(E) },
  };
  const content = {
    ...input,
    schema: 'normlab.snapshot/v2' as const,
    id: '00000000-0000-4000-8000-000000000406',
    caseId: 'explanation-case',
    revision: 1,
    createdAt: '2026-10-02T15:00:00.000Z',
    supersedes: null,
    authority: 'simulated-reviewer' as const,
  };
  return { ...content, digest: digest(content) };
}
