import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { parkingRunSchema, type ParkingJournalEvent } from '../shared/parking-journal.js';
import { contextProposalSchema } from '../shared/parking-context-proposal.js';

function runs(folder: string) {
  return readdirSync(folder, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && /^context-proposal-[a-f0-9-]{36}$/.test(entry.name))
    .flatMap((entry) => {
      const path = join(folder, entry.name);
      try {
        return [
          {
            path,
            run: parkingRunSchema.parse(
              JSON.parse(readFileSync(join(path, 'journal.json'), 'utf8')),
            ),
          },
        ];
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
        throw error;
      }
    });
}
export function contextProposalJournal(
  folder: string,
  activeRunId?: string,
): ParkingJournalEvent[] {
  return runs(folder).flatMap(({ run }) => {
    const base = {
      kind: 'context-proposal' as const,
      revisionId: run.revisionId,
      runId: run.runId,
    };
    const events: ParkingJournalEvent[] = [
      { ...base, id: `${run.runId}-start`, at: run.startedAt, action: 'started' },
    ];
    if (run.status === 'running')
      events.push({
        ...base,
        id: `${run.runId}-status`,
        at: run.startedAt,
        action: activeRunId === run.runId ? 'running' : 'interrupted',
      });
    else
      events.push({
        ...base,
        id: `${run.runId}-finish`,
        at: run.finishedAt,
        action: run.status,
        durationMs: Math.max(0, Date.parse(run.finishedAt) - Date.parse(run.startedAt)),
        ...(run.status === 'failed' ? { failure: run.failure } : {}),
      });
    return events;
  });
}
export function latestContextProposal(folder: string, revisionId: string, sourceDigest: string) {
  const item = runs(folder)
    .filter(({ run }) => run.status === 'completed' && run.revisionId === revisionId)
    .sort((a, b) => b.run.startedAt.localeCompare(a.run.startedAt))[0];
  if (!item) return null;
  const result = contextProposalSchema.parse(
    JSON.parse(readFileSync(join(item.path, 'proposal.json'), 'utf8')),
  );
  if (result.sourceDigest !== sourceDigest) throw new Error('Saved context source mismatch.');
  return result;
}
