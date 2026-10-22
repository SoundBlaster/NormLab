import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { z } from 'zod';
import {
  evaluateParkingFragment,
  legalInputSchema,
  parkingNormDraft,
  parkingVerificationSchema,
  type LegalAssessment,
} from '../shared/parking-legal.js';
import { reviewDraftMetadata, type ReviewDraft } from '../shared/parking-review.js';
import { reviewMetadataIssues } from '../shared/parking-context.js';
import type { ParkingJournalEvent } from '../shared/parking-journal.js';
import { digest } from './hash.js';
import {
  parkingNormDigest,
  parkingProfileDigest,
  verifyParkingCalculation,
} from './parking-verifier.js';

export { parkingNormDigest } from './parking-verifier.js';

export class ParkingLegalError extends Error {
  constructor(
    message: string,
    readonly status = 400,
  ) {
    super(message);
  }
}
const hash = (value: unknown) => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const savedSchema = z
  .object({
    schema: z.enum(['normlab.parking-legal-assessment/v1', 'normlab.parking-legal-assessment/v2']),
    id: z.string().uuid(),
    sequence: z.number().int().positive(),
    createdAt: z.string().datetime(),
    actor: z.literal('human-operator'),
    sourceDigest: z.string().regex(/^[a-f0-9]{64}$/),
    input: legalInputSchema,
    package: z.unknown(),
    result: z.unknown().nullable(),
    verification: parkingVerificationSchema.nullable().optional(),
  })
  .strict()
  .refine(
    (value) =>
      value.schema !== 'normlab.parking-legal-assessment/v2' ||
      (value.input.action === 'calculate'
        ? value.verification != null
        : value.verification === null),
    'Assessment v2 must record the verification outcome for calculations.',
  );

/** Each write is its own immutable request receipt; retries use the same requestId. */
export class ParkingLegal {
  constructor(private readonly verify = verifyParkingCalculation) {}

  private view(record: LegalAssessment): LegalAssessment {
    return record.verification?.status === 'verified' &&
      record.verification.profileDigest !== parkingProfileDigest
      ? { ...record, verifiedByPreviousProfile: true }
      : record;
  }

  history(folder: string): LegalAssessment[] {
    const root = join(folder, 'legal');
    if (!existsSync(root)) return [];
    return readdirSync(root)
      .filter((name) => name.endsWith('.json'))
      .map((name) => {
        const value = savedSchema.parse(JSON.parse(readFileSync(join(root, name), 'utf8')));
        if (
          value.id !== value.input.requestId ||
          name !== `${value.id}.json` ||
          hash(value.package) !== value.input.packageDigest ||
          value.input.packageDigest !== parkingNormDigest ||
          hash(value.result) !==
            hash(
              value.input.action === 'calculate' ? evaluateParkingFragment(value.input) : null,
            ) ||
          (value.verification &&
            (value.result === null ||
              value.verification.inputDigest !== digest(value.input) ||
              value.verification.resultDigest !== digest(value.result) ||
              value.verification.packageDigest !== value.input.packageDigest))
        )
          throw new ParkingLegalError(
            'Не удалось проверить сохранённый расчёт. История не изменена.',
            409,
          );
        return this.view(value as LegalAssessment);
      })
      .sort((a, b) => b.sequence - a.sequence);
  }

  workspace(folder: string) {
    return {
      package: parkingNormDraft,
      packageDigest: parkingNormDigest,
      assessments: this.history(folder),
    };
  }

  journal(folder: string): ParkingJournalEvent[] {
    return this.history(folder).map((record) => ({
      id: record.id,
      at: record.createdAt,
      revisionId: record.input.expectedRevisionId,
      kind: 'legal-assessment',
      action: record.result ? 'calculated' : 'saved',
    }));
  }

  async submit(folder: string, currentDraft: () => ReviewDraft, body: unknown) {
    const input = legalInputSchema.parse(body);
    const check = () => {
      const draft = currentDraft();
      if (input.draftId !== draft.draftId || input.expectedRevisionId !== draft.revisionId)
        throw new ParkingLegalError('Разметка изменилась. Обновите её перед расчётом.', 409);
      if (input.packageDigest !== parkingNormDigest)
        throw new ParkingLegalError('Пакет изменился. Обновите страницу.', 409);
      const metadata = reviewDraftMetadata(draft);
      if (
        draft.status !== 'reviewed' ||
        reviewMetadataIssues(metadata.context, metadata.hypotheses).length ||
        !draft.statements.length ||
        draft.statements.some((s) => s.decision === 'pending') ||
        !Object.values(draft.checklist).every(Boolean)
      )
        throw new ParkingLegalError('Сначала завершите проверку текста и метаданных.');
      const confirmed = draft.statements.filter((s) => s.decision === 'confirmed');
      if (!confirmed.some((s) => s.aboutEpisode === input.episode))
        throw new ParkingLegalError('Выберите эпизод с подтверждёнными утверждениями.');
      for (const finding of input.findings) {
        if (
          finding.statementIds.some(
            (id) => !confirmed.some((s) => s.id === id && s.aboutEpisode === input.episode),
          )
        )
          throw new ParkingLegalError(
            'Основание должно ссылаться на подтверждённое утверждение выбранного эпизода.',
          );
      }
      const records = this.history(folder);
      const repeated = records.find((record) => record.id === input.requestId);
      if (repeated) {
        if (hash(repeated.input) !== hash(input))
          throw new ParkingLegalError('ID запроса уже использован с другими входами.', 409);
        return { draft, records, repeated };
      }
      if ((records[0]?.id ?? null) !== input.expectedAssessmentId)
        throw new ParkingLegalError(
          'Обстоятельства изменились в другой вкладке. Обновите их перед сохранением.',
          409,
        );
      return { draft, records, repeated: undefined };
    };
    const initial = check();
    if (initial.repeated) return initial.repeated;
    const result = input.action === 'calculate' ? evaluateParkingFragment(input) : null;
    const verification = result ? await this.verify(input, result) : null;
    // Lean yields to other requests. Recheck the draft and optimistic head before writing.
    const { draft, records, repeated } = check();
    if (repeated) return repeated;
    const record: LegalAssessment = {
      schema: 'normlab.parking-legal-assessment/v2',
      id: input.requestId,
      sequence: (records[0]?.sequence ?? 0) + 1,
      createdAt: new Date().toISOString(),
      actor: 'human-operator',
      sourceDigest: draft.sourceDigest,
      input,
      package: parkingNormDraft,
      result,
      verification,
    };
    const root = join(folder, 'legal');
    mkdirSync(root, { recursive: true, mode: 0o700 });
    writeFileSync(join(root, `${record.id}.json`), JSON.stringify(record), {
      flag: 'wx',
      mode: 0o600,
    });
    return this.view(record);
  }
}
