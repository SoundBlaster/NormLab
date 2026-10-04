import { createHash, randomUUID } from 'node:crypto';
import { z } from 'zod';
import core from '../ontology/parking-pilot/generated/case-core/ontology.normalized.json';
import parking from '../ontology/parking-pilot/generated/parking/ontology.normalized.json';
import manifest from '../ontology/parking-pilot/artifact-manifest.json';
import {
  parkingExtractionSchema,
  parkingLinkPredicates,
  parkingScalarPredicates,
  PARKING_LIMITS,
  validateParkingExtraction,
  type ParkingValidationResult,
  type ParkingExtraction,
  type ParkingValidationIssue,
} from '../shared/parking-contracts.js';
import { PARKING_EXTRACTION_INSTRUCTIONS } from './parking-extraction.js';

export const PARKING_MODEL_V2 = 'normlab.parking-extraction-proposal/v2' as const;
const modelSpan = parkingExtractionSchema.shape.spans.element
  .omit({ startOffset: true, endOffset: true })
  .extend({
    occurrence: z
      .number()
      .int()
      .min(0)
      .max(PARKING_LIMITS.sourceCodeUnits - 1)
      .optional(),
  });
export const parkingModelV2Schema = parkingExtractionSchema.extend({
  schema: z.literal(PARKING_MODEL_V2),
  spans: z.array(modelSpan).max(PARKING_LIMITS.spans),
});
export const parkingModelV2JsonSchema = {
  ...z.toJSONSchema(parkingModelV2Schema, {
    target: 'draft-2020-12',
    unrepresentable: 'throw',
    reused: 'ref',
  }),
  $id: 'urn:normlab:contract:parking-extraction-proposal:v2',
};
const relations = new Map(
  [...core.relations, ...parking.relations].map((relation) => [relation.fqid, relation]),
);
export const parkingTypedLinkCatalogue = parkingLinkPredicates.map((predicate) => {
  const relation = relations.get(predicate);
  if (!relation) throw new Error(`Unresolved link predicate: ${predicate}`);
  return {
    predicate,
    domain: relation.domain,
    range: relation.range,
    description: relation.description,
  };
});
const entityConcepts: ReadonlySet<string> = new Set(
  parkingExtractionSchema.shape.entities.element.options.map(
    (option) => option.shape.concept.value,
  ),
);
const entityCatalogue = [...core.classes, ...parking.classes]
  .filter((concept) => entityConcepts.has(concept.fqid))
  .map((concept) => ({ concept: concept.fqid, description: concept.description }));
const instructions =
  PARKING_EXTRACTION_INSTRUCTIONS.replace(
    'Quotes must be exact substrings; offsets are UTF-16 code units, with exclusive end.',
    'Quotes must be exact substrings. Do not emit offsets. For a unique quote omit occurrence. For repeated quotes supply an explicit zero-based occurrence to identify the intended mention; never invent a quote.',
  ) +
  `\nUse the supplied typed predicate catalogue: subject must have domain concept; object must be an existing entity ID with range concept. Create referenced entities before using their IDs.
roleParticipant is RoleAssignment -> Participant, never Participant -> a role word. roleAboutEpisode is RoleAssignment -> Episode.
Do not add label/code to ParkingZone; its source evidence preserves the zone text. Payment, ParkingPlacement and ParkingSession are distinct concepts.
Use aliases such as Participant 1 / Vehicle 1, never source names or source names inside IDs. Explicit negative statements must survive as denied assertions, not missing data.
`;
const sha256 = (text: string) => createHash('sha256').update(text, 'utf8').digest('hex');
const contractDigest = sha256(
  JSON.stringify({
    schema: parkingModelV2JsonSchema,
    links: parkingTypedLinkCatalogue,
    scalars: parkingScalarPredicates,
    entities: entityCatalogue,
    instructions,
  }),
);

export function createParkingTypedRequest(sourceRevisionId: string, sourceText: string) {
  if (
    !sourceRevisionId ||
    sourceRevisionId.length > 128 ||
    !sourceText.length ||
    sourceText.length > PARKING_LIMITS.sourceCodeUnits
  )
    throw new Error('Invalid source revision/text');
  const bindings = Object.freeze({
    requestId: randomUUID(),
    sourceRevisionId,
    sourceDigest: sha256(sourceText),
    contract: PARKING_MODEL_V2,
    contractDigest,
    ontologyInputs: Object.freeze(manifest.inputs.map((entry) => Object.freeze({ ...entry }))),
  });
  return Object.freeze({
    bindings,
    sourceText,
    instructions,
    modelInput: JSON.stringify({
      sourceText,
      entities: entityCatalogue,
      linkPredicates: parkingTypedLinkCatalogue,
      scalarPredicates: parkingScalarPredicates,
      schema: parkingModelV2JsonSchema,
    }),
  });
}
export type ParkingTypedRequest = ReturnType<typeof createParkingTypedRequest>;

/** Resolve only exact source locations; never change asserted facts or silently choose repeated quotes. */
export type ParkingTypedResult =
  | Extract<ParkingValidationResult, { ok: false }>
  | {
      ok: true;
      proposal: ParkingExtraction;
      bindings: ParkingTypedRequest['bindings'];
      reviewState: 'unreviewed';
      anchoringMethod: 'exact-source-substring';
    };
export function consumeParkingTypedExtraction(
  raw: string,
  request: ParkingTypedRequest,
): ParkingTypedResult {
  if (
    sha256(request.sourceText) !== request.bindings.sourceDigest ||
    request.bindings.contract !== PARKING_MODEL_V2 ||
    request.bindings.contractDigest !== contractDigest ||
    JSON.stringify(request.bindings.ontologyInputs) !== JSON.stringify(manifest.inputs)
  )
    throw new Error('Typed extraction binding mismatch');
  if (raw.length > PARKING_LIMITS.outputCodeUnits)
    return {
      ok: false,
      issues: [{ path: '', code: 'output_limit', message: 'Model output too long' }],
    };
  let input: unknown;
  try {
    input = JSON.parse(raw) as unknown;
  } catch {
    return {
      ok: false,
      issues: [{ path: '', code: 'invalid_json', message: 'Expected one JSON object' }],
    };
  }
  const parsed = parkingModelV2Schema.safeParse(input);
  if (!parsed.success)
    return {
      ok: false,
      issues: parsed.error.issues.map((issue) => ({
        path: issue.path.join('.'),
        code: 'shape',
        message: issue.message,
      })),
    };
  const issues: ParkingValidationIssue[] = [];
  const spans = parsed.data.spans.map((span, index) => {
    const matches: number[] = [];
    let cursor = 0;
    while (cursor <= request.sourceText.length) {
      const found = request.sourceText.indexOf(span.quote, cursor);
      if (found < 0) break;
      matches.push(found);
      cursor = found + 1;
    }
    let position: number | undefined;
    if (!matches.length)
      issues.push({
        path: `spans.${index}`,
        code: 'quote_not_found',
        message: 'Exact quote absent from source',
      });
    else if (span.occurrence === undefined && matches.length > 1)
      issues.push({
        path: `spans.${index}`,
        code: 'ambiguous_quote',
        message: 'Repeated quote requires explicit occurrence',
      });
    else {
      position = matches[span.occurrence ?? 0];
      if (position === undefined)
        issues.push({
          path: `spans.${index}`,
          code: 'invalid_occurrence',
          message: 'Occurrence out of range',
        });
    }
    return {
      id: span.id,
      quote: span.quote,
      startOffset: position ?? 0,
      endOffset: (position ?? 0) + span.quote.length,
    };
  });
  if (issues.length) return { ok: false, issues };
  const validation = validateParkingExtraction(
    { ...parsed.data, schema: 'normlab.parking-extraction/v1', spans },
    request.sourceText,
  );
  if (!validation.ok) return validation;
  return {
    ...validation,
    bindings: request.bindings,
    reviewState: 'unreviewed',
    anchoringMethod: 'exact-source-substring',
  };
}
