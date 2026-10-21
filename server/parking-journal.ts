import { randomUUID } from 'node:crypto';
import { readFileSync, readdirSync, renameSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  parkingRunSchema,
  type ParkingJournalEvent,
  type ParkingRun,
} from '../shared/parking-journal.js';
import type { ReviewDraft } from '../shared/parking-review.js';

/** The saved revisions are the authority for manual actions, without a second write. */
export function revisionJournal(drafts: ReviewDraft[]): ParkingJournalEvent[] {
  const ordered = [...drafts].sort((a, b) => a.revision - b.revision);
  return ordered.map((draft, i) => ({
    id: draft.revisionId,
    revisionId: draft.revisionId,
    revision: draft.revision,
    at: draft.createdAt,
    kind:
      draft.revision === 1
        ? 'draft-created'
        : draft.originalExtraction !== null &&
            JSON.stringify(draft.originalExtraction) !==
              JSON.stringify(ordered[i - 1]?.originalExtraction)
          ? 'model-applied'
          : draft.status === 'reviewed' && ordered[i - 1]?.status !== 'reviewed'
            ? 'review-completed'
            : 'review-saved',
    statementCount: draft.statements.length,
    confirmed: draft.statements.filter((s) => s.decision === 'confirmed').length,
    rejected: draft.statements.filter((s) => s.decision === 'rejected').length,
  }));
}

export function saveParkingRun(folder: string, run: ParkingRun) {
  const value = parkingRunSchema.parse(run);
  const temporary = join(folder, `journal-${randomUUID()}.tmp`);
  writeFileSync(temporary, JSON.stringify(value), { flag: 'wx', mode: 0o600 });
  renameSync(temporary, join(folder, 'journal.json'));
}

export function extractionJournal(
  folder: string,
  activeRunId: string | undefined,
): ParkingJournalEvent[] {
  return readdirSync(folder, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && /^extraction-[a-f0-9-]{36}$/.test(entry.name))
    .flatMap((entry) => {
      const path = join(folder, entry.name, 'journal.json');
      let raw: string;
      try {
        raw = readFileSync(path, 'utf8');
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
        throw error;
      }
      const run = parkingRunSchema.parse(JSON.parse(raw));
      const common = { revisionId: run.revisionId, runId: run.runId };
      const events: ParkingJournalEvent[] = [
        {
          ...common,
          id: `${run.runId}-start`,
          at: run.startedAt,
          kind: 'extraction-started',
        },
      ];
      if (run.status === 'running')
        events.push({
          ...common,
          id: `${run.runId}-status`,
          at: run.startedAt,
          kind: activeRunId === run.runId ? 'extraction-running' : 'extraction-interrupted',
        });
      else if (run.status === 'conflict')
        events.push({
          ...common,
          id: `${run.runId}-finish`,
          at: run.finishedAt,
          kind: 'extraction-conflict',
        });
      else {
        const timing = {
          ...common,
          id: `${run.runId}-finish`,
          at: run.finishedAt,
          durationMs: Math.max(0, Date.parse(run.finishedAt) - Date.parse(run.startedAt)),
        };
        events.push(
          run.status === 'failed'
            ? { ...timing, kind: 'extraction-failed', failure: run.failure }
            : { ...timing, kind: 'extraction-completed', statementCount: run.statementCount },
        );
      }
      return events;
    });
}
