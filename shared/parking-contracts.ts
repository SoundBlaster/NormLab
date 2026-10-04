import { z } from 'zod';
import core from '../ontology/parking-pilot/generated/case-core/ontology.normalized.json';
import parking from '../ontology/parking-pilot/generated/parking/ontology.normalized.json';

export const PARKING_EXTRACTION_CONTRACT = 'normlab.parking-extraction/v1' as const;
export const PARKING_LIMITS = {
  sourceCodeUnits: 32768,
  outputCodeUnits: 262144,
  entities: 128,
  assertions: 256,
  spans: 512,
  unmapped: 64,
} as const;
const id = z.string().regex(/^[A-Za-z][A-Za-z0-9_-]{0,63}$/);
// Match JSON Schema Unicode code-point length, including astral characters.
const text = (max: number) =>
  z
    .string()
    .regex(new RegExp(`^[\\s\\S]{1,${max}}(?![\\s\\S])`, 'u'))
    .meta({ minLength: 1, maxLength: max });
const evidence = z.array(id).min(1).max(8);
const entityBase = { id, evidence };
const emptyEntity = <T extends string>(concept: T) =>
  z.strictObject({ ...entityBase, concept: z.literal(concept) });

const entitySchema = z.discriminatedUnion('concept', [
  z.strictObject({
    ...entityBase,
    concept: z.literal('nlcase:Participant'),
    alias: text(100),
    participantKind: z.enum(['person', 'organization', 'unknown']),
  }),
  z.strictObject({ ...entityBase, concept: z.literal('nlcase:Vehicle'), alias: text(100) }),
  z.strictObject({ ...entityBase, concept: z.literal('nlcase:Episode'), label: text(300) }),
  z.strictObject({ ...entityBase, concept: z.literal('nlcase:Location'), label: text(500) }),
  z.strictObject({
    ...entityBase,
    concept: z.literal('nlcase:TimeInterval'),
    startText: text(200).optional(),
    endText: text(200).optional(),
    timezoneText: text(100).optional(),
    precision: z.enum(['exact', 'approximate', 'mixed', 'unknown']),
  }),
  z.strictObject({
    ...entityBase,
    concept: z.literal('nlcase:RoleAssignment'),
    role: z.enum(['owner', 'driver', 'user', 'narrator', 'other']),
  }),
  z.strictObject({
    ...entityBase,
    concept: z.literal('nlcase:MoneyAmount'),
    amount: z.number().min(0).max(1000000000),
    currency: z.string().regex(/^[A-Z]{3}$/),
  }),
  emptyEntity('nlpark:ParkingPlacement'),
  emptyEntity('nlpark:ParkingPlace'),
  emptyEntity('nlpark:ParkingZone'),
  emptyEntity('nlpark:ParkingSession'),
  emptyEntity('nlpark:PaymentAttempt'),
  emptyEntity('nlpark:Payment'),
  emptyEntity('nlpark:PermitClaim'),
  emptyEntity('nlpark:SessionCorrectionClaim'),
  z.strictObject({
    ...entityBase,
    concept: z.literal('nlpark:SanctionClaim'),
    normReferenceText: text(300).optional(),
  }),
]);

// Explicit consumer predicates; these are not invented imported ontology concepts.
export const parkingScalarPredicates = {
  'nlinput:eventTime': { condition: 'C02', domain: 'nlcase:Episode' },
  'nlinput:inMoscow': { condition: 'C03', domain: 'nlcase:Location' },
  'nlinput:cityParking': { condition: 'C04', domain: 'nlpark:ParkingPlace' },
  'nlinput:placement': { condition: 'C05', domain: 'nlcase:Episode' },
  'nlinput:paidRegime': { condition: 'C06', domain: 'nlcase:Episode' },
  'nlinput:subjectScope': { condition: 'C07', domain: 'nlcase:Episode' },
  'nlinput:attribution': { condition: 'C08', domain: 'nlcase:Episode' },
  'nlinput:payment': { condition: 'C09', domain: 'nlcase:Episode' },
  'nlinput:paymentStart': { condition: 'C10', domain: 'nlpark:Payment' },
  'nlinput:departure': { condition: 'C11', domain: 'nlpark:ParkingPlacement' },
  'nlinput:paymentComplexity': { condition: 'C12', domain: 'nlcase:Episode' },
  'nlinput:permit': { condition: 'C13', domain: 'nlcase:Episode' },
  'nlinput:disabilityConditions': { condition: 'C14', domain: 'nlcase:Episode' },
  'nlinput:specialTariff': { condition: 'C15', domain: 'nlcase:Episode' },
  'nlinput:faultAndExclusions': { condition: 'C16', domain: 'nlcase:Episode' },
} as const;
export const parkingLinkPredicates = [
  'nlcase:roleParticipant',
  'nlcase:roleAboutEpisode',
  'nlpark:placedAt',
  'nlpark:involvesVehicle',
  'nlpark:placeInZone',
  'nlpark:placementInEpisode',
  'nlpark:sessionInEpisode',
  'nlpark:paymentForSession',
  'nlpark:paymentTargetsVehicle',
  'nlpark:paymentTargetsZone',
  'nlpark:coversInterval',
  'nlpark:placementInterval',
  'nlpark:correctionAboutSession',
  'nlpark:permitAboutVehicle',
  'nlpark:sanctionAboutEpisode',
  'nlpark:sanctionAmount',
] as const;
const scalarKeys = Object.keys(parkingScalarPredicates) as [
  keyof typeof parkingScalarPredicates,
  ...(keyof typeof parkingScalarPredicates)[],
];
const assertionBase = {
  id,
  subject: id,
  aboutEpisode: id,
  evidence,
  stance: z.enum(['asserted', 'denied', 'uncertain']),
  attributedTo: z.array(id).max(8),
  attributionText: text(500).optional(),
};
const assertionSchema = z.union([
  z.strictObject({ ...assertionBase, predicate: z.enum(parkingLinkPredicates), object: id }),
  z.strictObject({ ...assertionBase, predicate: z.enum(scalarKeys), valueText: text(1000) }),
]);

export const parkingExtractionSchema = z.strictObject({
  schema: z.literal(PARKING_EXTRACTION_CONTRACT),
  entities: z.array(entitySchema).max(PARKING_LIMITS.entities),
  spans: z
    .array(
      z.strictObject({
        id,
        quote: text(2000),
        startOffset: z.number().int().min(0).max(PARKING_LIMITS.sourceCodeUnits),
        endOffset: z.number().int().min(1).max(PARKING_LIMITS.sourceCodeUnits),
      }),
    )
    .max(PARKING_LIMITS.spans),
  assertions: z.array(assertionSchema).max(PARKING_LIMITS.assertions),
  unmappedMentions: z
    .array(z.strictObject({ id, description: text(1000), evidence, aboutEpisode: id.optional() }))
    .max(PARKING_LIMITS.unmapped),
});
export type ParkingExtraction = z.infer<typeof parkingExtractionSchema>;
export type ParkingEntity = ParkingExtraction['entities'][number];
export type ParkingValidationIssue = { path: string; code: string; message: string };
export type ParkingValidationResult =
  { ok: true; proposal: ParkingExtraction } | { ok: false; issues: ParkingValidationIssue[] };

const relationCatalog = new Map(
  [...core.relations, ...parking.relations].map((relation) => [relation.fqid, relation]),
);

/** Validate a proposal against one application-provided source revision; never establish facts. */
export function validateParkingExtraction(input: unknown, source: string): ParkingValidationResult {
  if (source.length > PARKING_LIMITS.sourceCodeUnits)
    return {
      ok: false,
      issues: [{ path: 'source', code: 'source_limit', message: 'Source is too long' }],
    };
  const parsed = parkingExtractionSchema.safeParse(input);
  if (!parsed.success)
    return {
      ok: false,
      issues: parsed.error.issues.map((issue) => ({
        path: issue.path.join('.'),
        code: 'shape',
        message: issue.message,
      })),
    };
  const proposal = parsed.data;
  const issues: ParkingValidationIssue[] = [];
  const fail = (path: string, code: string, message: string) =>
    issues.push({ path, code, message });
  const seen = new Set<string>();
  for (const [name, items] of Object.entries({
    entities: proposal.entities,
    spans: proposal.spans,
    assertions: proposal.assertions,
    unmappedMentions: proposal.unmappedMentions,
  })) {
    items.forEach((item, index) => {
      if (seen.has(item.id)) fail(`${name}.${index}.id`, 'duplicate_id', item.id);
      seen.add(item.id);
    });
  }
  const entities = new Map(proposal.entities.map((entity) => [entity.id, entity]));
  const spans = new Set(proposal.spans.map((span) => span.id));
  const reference = (ref: string, allowed: readonly string[], path: string) => {
    const entity = entities.get(ref);
    if (!entity) fail(path, 'missing_reference', ref);
    else if (!allowed.includes(entity.concept)) fail(path, 'concept_mismatch', entity.concept);
  };
  const checkEvidence = (refs: string[], path: string) => {
    if (new Set(refs).size !== refs.length) fail(path, 'duplicate_reference', 'Repeated evidence');
    refs.forEach((ref, index) => {
      if (!spans.has(ref)) fail(`${path}.${index}`, 'missing_span', ref);
    });
  };
  proposal.spans.forEach((span, index) => {
    const path = `spans.${index}`;
    // JavaScript slice offsets use UTF-16 code units, exclusive end.
    if (span.endOffset <= span.startOffset || span.endOffset > source.length)
      fail(path, 'invalid_offsets', 'Expected a nonempty in-bounds interval');
    else if (source.slice(span.startOffset, span.endOffset) !== span.quote)
      fail(path, 'quote_mismatch', 'Quote differs from source revision');
    const splitsSurrogate = (offset: number) =>
      offset > 0 &&
      offset < source.length &&
      /[\uD800-\uDBFF]/.test(source[offset - 1] ?? '') &&
      /[\uDC00-\uDFFF]/.test(source[offset] ?? '');
    if (splitsSurrogate(span.startOffset) || splitsSurrogate(span.endOffset))
      fail(path, 'split_surrogate', 'Offset splits a Unicode character');
  });
  proposal.entities.forEach((entity, index) =>
    checkEvidence(entity.evidence, `entities.${index}.evidence`),
  );
  proposal.assertions.forEach((assertion, index) => {
    const path = `assertions.${index}`;
    checkEvidence(assertion.evidence, `${path}.evidence`);
    reference(assertion.aboutEpisode, ['nlcase:Episode'], `${path}.aboutEpisode`);
    if (new Set(assertion.attributedTo).size !== assertion.attributedTo.length)
      fail(`${path}.attributedTo`, 'duplicate_reference', 'Repeated attribution');
    assertion.attributedTo.forEach((ref, i) =>
      reference(ref, ['nlcase:Participant'], `${path}.attributedTo.${i}`),
    );
    if ('object' in assertion) {
      const relation = relationCatalog.get(assertion.predicate);
      if (!relation) fail(`${path}.predicate`, 'unresolved_predicate', assertion.predicate);
      else {
        reference(assertion.subject, [relation.domain], `${path}.subject`);
        reference(
          assertion.object,
          typeof relation.range === 'string' ? [relation.range] : relation.range.oneOf,
          `${path}.object`,
        );
      }
      if (
        [
          'nlcase:roleAboutEpisode',
          'nlpark:placementInEpisode',
          'nlpark:sessionInEpisode',
          'nlpark:sanctionAboutEpisode',
        ].includes(assertion.predicate) &&
        assertion.object !== assertion.aboutEpisode
      )
        fail(
          `${path}.aboutEpisode`,
          'episode_mismatch',
          'Episode target differs from assertion context',
        );
    } else {
      reference(
        assertion.subject,
        [parkingScalarPredicates[assertion.predicate].domain],
        `${path}.subject`,
      );
    }
    if (
      entities.get(assertion.subject)?.concept === 'nlcase:Episode' &&
      assertion.subject !== assertion.aboutEpisode
    )
      fail(
        `${path}.aboutEpisode`,
        'episode_mismatch',
        'Episode subject differs from assertion context',
      );
  });
  proposal.unmappedMentions.forEach((mention, index) => {
    checkEvidence(mention.evidence, `unmappedMentions.${index}.evidence`);
    if (mention.aboutEpisode)
      reference(mention.aboutEpisode, ['nlcase:Episode'], `unmappedMentions.${index}.aboutEpisode`);
  });
  return issues.length ? { ok: false, issues } : { ok: true, proposal };
}

/** Bounded transport entry point. Do not accept Markdown fences or repair malformed JSON silently. */
export function parseParkingExtraction(raw: string, source: string): ParkingValidationResult {
  if (raw.length > PARKING_LIMITS.outputCodeUnits)
    return {
      ok: false,
      issues: [{ path: '', code: 'output_limit', message: 'Model output is too long' }],
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
  return validateParkingExtraction(input, source);
}

export function exportedParkingExtractionSchema() {
  return {
    ...z.toJSONSchema(parkingExtractionSchema, {
      target: 'draft-2020-12',
      unrepresentable: 'throw',
      reused: 'ref',
    }),
    $id: 'urn:normlab:contract:parking-extraction:v1',
  };
}
