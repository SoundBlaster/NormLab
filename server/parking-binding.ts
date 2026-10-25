import type { LegalInput, ParkingScopeBinding } from '../shared/parking-legal.js';
import { createHash } from 'node:crypto';
import { parkingNormDraft, parkingScopeBindingSchema } from '../shared/parking-legal.js';
import {
  reviewDraftSchema,
  reviewDraftMetadata,
  reviewStatementIssues,
  type ReviewDraft,
} from '../shared/parking-review.js';
import { reviewMetadataIssues } from '../shared/parking-context.js';
import { digest } from './hash.js';

// Archived extraction is arbitrary persisted JSON, including finite fractional
// confidence/probability values. The norm IR encoder intentionally has a more
// restrictive number domain, so it is not used for the complete revision.
function canonicalRevision(value: unknown): string {
  if (value === null || typeof value === 'string' || typeof value === 'boolean')
    return JSON.stringify(value);
  if (typeof value === 'number' && Number.isFinite(value)) return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalRevision).join(',')}]`;
  if (typeof value === 'object' && value !== null)
    return `{${Object.entries(value)
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonicalRevision(item)}`)
      .join(',')}}`;
  throw new Error('Revision contains a value outside persisted JSON');
}
const revisionDigest = (draft: ReviewDraft) =>
  createHash('sha256').update(canonicalRevision(draft)).digest('hex');

/** Lossless UTF-16 code-unit identity. Only bounded hexadecimal digits enter Lean. */
function token(value: string): string {
  let encoded = '0x1';
  for (let index = 0; index < value.length; index++)
    encoded += value.charCodeAt(index).toString(16).padStart(4, '0');
  return encoded;
}

export function parkingBindingReceipt(
  input: LegalInput,
  rawDraft: ReviewDraft,
): ParkingScopeBinding {
  const draft = reviewDraftSchema.parse(rawDraft);
  const metadata = reviewDraftMetadata(draft);
  const statements = new Map(draft.statements.map((statement) => [statement.id, statement]));
  if (
    draft.draftId !== input.draftId ||
    draft.revisionId !== input.expectedRevisionId ||
    draft.sourceDigest !== createHash('sha256').update(draft.narrative).digest('hex') ||
    draft.status !== 'reviewed' ||
    !Object.values(draft.checklist).every(Boolean) ||
    (draft.schema === 'normlab.parking-review/v2' &&
      reviewMetadataIssues(metadata.context, metadata.hypotheses).length > 0) ||
    statements.size !== draft.statements.length ||
    draft.statements.some(
      (statement) =>
        statement.decision === 'pending' ||
        reviewStatementIssues(statement, draft.narrative).length > 0,
    ) ||
    !draft.statements.some(
      (statement) => statement.decision === 'confirmed' && statement.aboutEpisode === input.episode,
    )
  )
    throw new Error('Parking binding requires the exact reviewed source revision');
  const ids = [...new Set(input.findings.flatMap((finding) => finding.statementIds))].sort();
  for (const id of ids) {
    const statement = statements.get(id);
    if (
      !statement ||
      statement.decision !== 'confirmed' ||
      statement.aboutEpisode !== input.episode
    )
      throw new Error(
        'Parking binding source reference belongs to another episode or review state',
      );
  }
  return parkingScopeBindingSchema.parse({
    schema: 'normlab.parking-scope-binding/v1',
    action: 'record-reviewed-findings',
    draftId: input.draftId,
    revisionId: input.expectedRevisionId,
    assessmentId: input.requestId,
    sourceDigest: draft.sourceDigest,
    sourceRevisionDigest: revisionDigest(draft),
    sourceStatementsDigest: digest(draft.statements),
    findingsDigest: digest(input.findings),
    scope: {
      episode: input.episode,
      participant: input.participant,
      vehicle: input.vehicle,
      eventDate: input.eventDate,
      location: input.location,
      timeInterval: input.timeInterval,
    },
    statementIds: ids,
  });
}

const stateTokens = {
  unreviewed: 'unreviewed',
  established: 'established',
  refuted: 'refuted',
  'not-established': 'notEstablished',
  conflict: 'conflict',
} as const;

export function constructParkingBinding(input: LegalInput, draft: ReviewDraft) {
  draft = reviewDraftSchema.parse(draft);
  const binding = parkingBindingReceipt(input, draft);
  const sourceRows = draft.statements.map(
    (statement) =>
      `{ id := ${token(statement.id)}, episode := ${token(statement.aboutEpisode)}, confirmed := ${statement.decision === 'confirmed'} }`,
  );
  const rows = parkingNormDraft.conditions.map(({ id }) => {
    const finding = input.findings.find((item) => item.conditionId === id)!;
    return `{ condition := .${id}, state := .${stateTokens[finding.state]}, supports := [${finding.statementIds.map(token).join(', ')}] }`;
  });
  const statement = `namespace NormLabParkingRuntime
def boundSource : Source := {
  draft := ${token(draft.draftId)}
  revision := ${token(draft.revisionId)}
  revisionDigest := ${token(revisionDigest(draft))}
  reviewed := ${draft.status === 'reviewed'}
  statements := [${sourceRows.join(',\n')}]
}
def boundRequest : Request := {
  scope := {
    draft := ${token(input.draftId)}
    revision := ${token(input.expectedRevisionId)}
    assessment := ${token(input.requestId)}
    revisionDigest := ${token(binding.sourceRevisionDigest)}
    episode := ${token(input.episode)}
    participant := ${token(input.participant)}
    vehicle := ${token(input.vehicle)}
    eventDate := ${token(input.eventDate)}
    location := ${token(input.location)}
    timeInterval := ${token(input.timeInterval)}
  }
  findings := [${rows.join(',\n')}]
  claimedFine := ${input.claimedFine === null ? 'none' : `(some ${input.claimedFine})`}
}
theorem binding_checked : bindingValid boundSource boundRequest = true := by decide +kernel
def boundReview := input boundSource boundRequest binding_checked
theorem review_checked : (NormLabParkingAttribution.propose boundReview).isSome = true := by decide +kernel
theorem scope_checked (result) (accepted : NormLabParkingAttribution.propose boundReview = some result) :
    HasScope boundRequest result := accepted_scope _ _ binding_checked result accepted
theorem snapshot_checked (result) (accepted : NormLabParkingAttribution.propose boundReview = some result) :
    result.context.event.record.after = snapshot boundRequest := accepted_snapshot _ _ binding_checked result accepted
theorem supports_checked (row) (member : row ∈ boundRequest.findings) (id) (cited : id ∈ row.supports) :
    ∃ statement ∈ boundSource.statements, statement.id = id ∧ statement.episode = boundRequest.scope.episode ∧ statement.confirmed = true :=
  supports_scoped _ _ binding_checked row member id cited
end NormLabParkingRuntime
`;
  return { binding, statement };
}
