import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fabulaActorDecisionSchema, fabulaActorInputSchema } from '../shared/parking-fabula.js';
import type { FabulaActorCandidate } from '../shared/parking-fabula.js';
import type { LegalAssessment } from '../shared/parking-legal.js';
import { reviewDraftSchema, reviewStatementIssues } from '../shared/parking-review.js';
import type { ParkingJournalEvent } from '../shared/parking-journal.js';
import { ParkingLegalError } from './parking-legal.js';
import { digest } from './hash.js';

/** Surface proposal only: first-person references stay scoped to their statement's speaker. */
function candidates(folder: string, record: LegalAssessment) {
  const draft = reviewDraftSchema.parse(
    JSON.parse(readFileSync(join(folder, `${record.input.expectedRevisionId}.json`), 'utf8')),
  );
  if (
    draft.draftId !== record.input.draftId ||
    draft.revisionId !== record.input.expectedRevisionId ||
    draft.sourceDigest !== record.sourceDigest ||
    createHash('sha256').update(draft.narrative).digest('hex') !== record.sourceDigest
  )
    throw new ParkingLegalError('Источник фабулы не совпадает с сохранённым расчётом.', 409);
  const cited = new Set(
    record.input.findings.find((finding) => finding.conditionId === 'placement')?.statementIds,
  );
  const proposals: FabulaActorCandidate[] = [];
  for (const statement of draft.statements) {
    if (
      !cited.has(statement.id) ||
      statement.aboutEpisode !== record.input.episode ||
      statement.predicate !== 'nlinput:placement' ||
      statement.decision !== 'confirmed' ||
      statement.stance !== 'asserted' ||
      reviewStatementIssues(statement, draft.narrative).length
    )
      continue;
    // Deliberately narrow. Conditionals, reported speech and irony still need human review.
    const named =
      /(?:^|[^\p{L}\p{M}])[Яя],\s*([\p{Lu}][\p{L}\p{M}-]*(?:[ \t]+[\p{Lu}][\p{L}\p{M}-]*){0,3})\s*,\s*(?:оставил[аи]?|припарковал[аи]?|поставил[аи]?|разместил[аи]?)(?![\p{L}\p{M}])/gu;
    const unnamed =
      /(?:^|[^\p{L}\p{M}])([Яя])\s+(?:оставил[аи]?|припарковал[аи]?|поставил[аи]?|разместил[аи]?)(?![\p{L}\p{M}])/gu;
    for (const match of [
      ...statement.quote.matchAll(named),
      ...statement.quote.matchAll(unnamed),
    ]) {
      const label = match[1];
      if (label.length > 128) continue;
      const value = {
        statementId: statement.id,
        label,
        quote: statement.quote,
        startOffset: statement.startOffset,
        endOffset: statement.endOffset,
        method: 'explicit-first-person/v2' as const,
        ...(statement.speaker === undefined ? {} : { speaker: statement.speaker }),
      };
      const id = digest({ revision: draft.revisionId, assessment: record.id, ...value });
      if (!proposals.some((candidate) => candidate.id === id)) proposals.push({ id, ...value });
      if (proposals.length > 256)
        throw new ParkingLegalError('Слишком много кандидатов актора для одного расчёта.');
    }
  }
  return { draft, proposals };
}

/** Independent immutable interpretations; never edit a source revision or a Lean receipt. */
export function fabulaActorHistory(folder: string) {
  const root = join(folder, 'fabula');
  if (!existsSync(root)) return [];
  return readdirSync(root)
    .filter((name) => name.endsWith('.json'))
    .map((name) => {
      const value = fabulaActorDecisionSchema.parse(
        JSON.parse(readFileSync(join(root, name), 'utf8')),
      );
      if (
        name !== `${value.id}.json` ||
        value.id !== value.input.requestId ||
        value.candidate.id !== value.input.candidateId
      )
        throw new ParkingLegalError('Запись интерпретации фабулы повреждена.', 409);
      return value;
    })
    .sort((a, b) => b.sequence - a.sequence);
}

export function fabulaSource(folder: string, record: LegalAssessment) {
  const { draft, proposals } = candidates(folder, record);
  const decisions = fabulaActorHistory(folder).filter(
    (value) => value.input.assessmentId === record.id,
  );
  for (const value of decisions) {
    const candidate = value.candidate;
    const sourceStatement = draft.statements.find(
      (statement) => statement.id === candidate.statementId,
    );
    const { id, ...identity } = candidate;
    if (
      value.sourceDigest !== record.sourceDigest ||
      value.input.draftId !== draft.draftId ||
      value.input.expectedRevisionId !== draft.revisionId ||
      id !== digest({ revision: draft.revisionId, assessment: record.id, ...identity }) ||
      draft.narrative.slice(candidate.startOffset, candidate.endOffset) !== candidate.quote ||
      !candidate.quote.includes(candidate.label) ||
      !sourceStatement ||
      sourceStatement.quote !== candidate.quote ||
      sourceStatement.startOffset !== candidate.startOffset ||
      sourceStatement.endOffset !== candidate.endOffset ||
      (candidate.method === 'explicit-first-person/v2' &&
        candidate.speaker !== sourceStatement.speaker)
    )
      throw new ParkingLegalError('Интерпретация относится к другому источнику.', 409);
    // Historical decisions keep their original proposal, independent of future proposal rules.
    if (!proposals.some((candidate) => candidate.id === value.candidate.id))
      proposals.push(value.candidate);
  }
  return {
    draftId: draft.draftId,
    revisionId: draft.revisionId,
    assessmentId: record.id,
    sourceDigest: draft.sourceDigest,
    narrative: draft.narrative,
    candidates: proposals,
    decisions,
  };
}

export function saveFabulaActor(
  folder: string,
  record: LegalAssessment,
  body: unknown,
  authorize: () => void,
) {
  const input = fabulaActorInputSchema.parse(body);
  const history = fabulaActorHistory(folder);
  const repeated = history.find((value) => value.id === input.requestId);
  if (repeated) {
    if (digest(repeated.input) !== digest(input))
      throw new ParkingLegalError('ID интерпретации уже использован с другим решением.', 409);
    return fabulaSource(folder, record);
  }
  authorize();
  const source = fabulaSource(folder, record);
  const candidate = source.candidates.find((value) => value.id === input.candidateId);
  if (
    input.draftId !== source.draftId ||
    input.expectedRevisionId !== source.revisionId ||
    input.assessmentId !== source.assessmentId ||
    !candidate ||
    input.expectedDecisionId !== (source.decisions[0]?.id ?? null)
  )
    throw new ParkingLegalError('Интерпретация изменилась. Обновите её перед решением.', 409);
  const value = fabulaActorDecisionSchema.parse({
    schema: 'normlab.fabula-actor-decision/v1',
    id: input.requestId,
    sequence: (history[0]?.sequence ?? 0) + 1,
    at: new Date().toISOString(),
    sourceDigest: source.sourceDigest,
    input,
    candidate,
  });
  const root = join(folder, 'fabula');
  mkdirSync(root, { recursive: true, mode: 0o700 });
  writeFileSync(join(root, `${value.id}.json`), JSON.stringify(value), { flag: 'wx', mode: 0o600 });
  return fabulaSource(folder, record);
}

export function fabulaActorJournal(folder: string): ParkingJournalEvent[] {
  return fabulaActorHistory(folder).map((value) => ({
    id: value.id,
    at: value.at,
    revisionId: value.input.expectedRevisionId,
    kind: 'actor-interpretation',
    decision: value.input.decision,
  }));
}
