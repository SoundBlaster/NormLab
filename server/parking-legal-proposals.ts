import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import {
  legalProposalInputSchema,
  legalProposalMatches,
  savedLegalProposalSchema,
  type LegalProposalInput,
  type SavedLegalProposal,
} from '../shared/parking-legal-proposal.js';
import { parkingRunSchema, type ParkingJournalEvent } from '../shared/parking-journal.js';
import { reviewMetadataIssues } from '../shared/parking-context.js';
import {
  reviewDraftMetadata,
  reviewStatementIssues,
  type ReviewDraft,
} from '../shared/parking-review.js';
import { digest } from './hash.js';
import { parkingNormDigest } from './parking-verifier.js';

export class ParkingLegalProposalError extends Error {
  constructor(
    message: string,
    readonly status = 409,
  ) {
    super(message);
  }
}

/** The browser chooses an episode; the server chooses its reviewed source material. */
export function legalProposalInputForDraft(
  draft: ReviewDraft,
  episode: string,
): LegalProposalInput {
  const metadata = reviewDraftMetadata(draft);
  if (
    draft.status !== 'reviewed' ||
    reviewMetadataIssues(metadata.context, metadata.hypotheses).length ||
    !draft.statements.length ||
    draft.statements.some((statement) => statement.decision === 'pending') ||
    !Object.values(draft.checklist).every(Boolean)
  )
    throw new ParkingLegalProposalError('Сначала завершите проверку текста и метаданных.', 400);
  const statements = draft.statements.filter(
    (statement) => statement.decision === 'confirmed' && statement.aboutEpisode === episode,
  );
  if (!statements.length)
    throw new ParkingLegalProposalError('Выберите эпизод с подтверждёнными утверждениями.', 400);
  if (
    createHash('sha256').update(draft.narrative).digest('hex') !== draft.sourceDigest ||
    statements.some((statement) => reviewStatementIssues(statement, draft.narrative).length)
  )
    throw new ParkingLegalProposalError('Не удалось подтвердить цитаты выбранного эпизода.');
  return legalProposalInputSchema.parse({
    draftId: draft.draftId,
    revisionId: draft.revisionId,
    sourceDigest: draft.sourceDigest,
    packageDigest: parkingNormDigest,
    episode,
    statements: statements.map((statement) => ({
      id: statement.id,
      predicate: statement.predicate,
      stance: statement.stance,
      subject: statement.subject,
      speaker: statement.speaker ?? null,
      valueText: statement.valueText,
      quote: statement.quote,
    })),
  });
}

function runs(folder: string) {
  return readdirSync(folder, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && /^legal-proposal-[a-f0-9-]{36}$/.test(entry.name))
    .flatMap((entry) => {
      const path = join(folder, entry.name);
      try {
        const run = parkingRunSchema.parse(
          JSON.parse(readFileSync(join(path, 'journal.json'), 'utf8')),
        );
        if (entry.name !== `legal-proposal-${run.runId}`)
          throw new ParkingLegalProposalError('Не удалось проверить журнал предложения.');
        return [{ path, run }];
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
        throw error;
      }
    });
}

/** Verify the stored input, all bindings and reference membership before exposing a candidate. */
export function readCompletedLegalProposal(folder: string, proposalId: string): SavedLegalProposal {
  try {
    const id = savedLegalProposalSchema.shape.proposalId.parse(proposalId);
    const path = join(folder, `legal-proposal-${id}`);
    const run = parkingRunSchema.parse(
      JSON.parse(readFileSync(join(path, 'journal.json'), 'utf8')),
    );
    const input = legalProposalInputSchema.parse(
      JSON.parse(readFileSync(join(path, 'input.json'), 'utf8')),
    );
    const proposal = savedLegalProposalSchema.parse(
      JSON.parse(readFileSync(join(path, 'proposal.json'), 'utf8')),
    );
    if (
      run.status !== 'completed' ||
      run.runId !== id ||
      proposal.proposalId !== id ||
      run.revisionId !== input.revisionId ||
      proposal.inputDigest !== digest(input) ||
      !legalProposalMatches(input, proposal)
    )
      throw new Error('Stored proposal binding mismatch.');
    return proposal;
  } catch {
    throw new ParkingLegalProposalError('Не удалось проверить сохранённое предложение модели.');
  }
}

export function legalProposalForDraft(
  folder: string,
  draft: ReviewDraft,
  proposalId: string,
  episode: string,
): SavedLegalProposal {
  const proposal = readCompletedLegalProposal(folder, proposalId);
  const input = legalProposalInputForDraft(draft, episode);
  if (!legalProposalMatches(input, proposal) || proposal.inputDigest !== digest(input))
    throw new ParkingLegalProposalError(
      'Предложение относится к другой ревизии, пакету или эпизоду. Получите актуальное предложение.',
    );
  return proposal;
}

export function legalProposalsForDraft(folder: string, draft: ReviewDraft): SavedLegalProposal[] {
  return runs(folder)
    .filter(({ run }) => run.status === 'completed' && run.revisionId === draft.revisionId)
    .sort((a, b) => {
      const at = a.run.status === 'completed' ? a.run.finishedAt : a.run.startedAt;
      const bt = b.run.status === 'completed' ? b.run.finishedAt : b.run.startedAt;
      return bt.localeCompare(at) || b.run.runId.localeCompare(a.run.runId);
    })
    .flatMap(({ run }) => {
      const proposal = readCompletedLegalProposal(folder, run.runId);
      if (
        proposal.sourceDigest !== draft.sourceDigest ||
        proposal.packageDigest !== parkingNormDigest
      )
        return [];
      return [legalProposalForDraft(folder, draft, proposal.proposalId, proposal.episode)];
    })
    .slice(0, 10);
}

export function legalProposalJournal(folder: string, activeRunId?: string): ParkingJournalEvent[] {
  return runs(folder).flatMap(({ run }) => {
    const base = {
      kind: 'legal-proposal' as const,
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
