import { deepStrictEqual } from 'node:assert';
import { type Bundle, legalIrSchema } from '../shared/domain.js';
import { digest } from './hash.js';

function bundle(id: Bundle['id'], denominator: number): Bundle {
  const first = id === 'reduction-v1';
  const ir = legalIrSchema.parse({
    schema: 'normlab.legal-ir/v1',
    profile: 'demo.conditional-transform/v1',
    baseline: { prisonMonths: 120, fineAmount: 200000, currency: 'DEMO' },
    adjustment: {
      id: 'reduce-prison-term',
      trigger: 'A',
      numerator: first ? 2 : 1,
      denominator,
      mandatory: true,
      target: 'prison-months',
      applyCount: 1,
      preserveFine: true,
    },
    coverage: 'synthetic-single-adjustment',
  });
  const source = first
    ? 'Базовый срок 120 месяцев и штраф 200000 DEMO. При установленном A срок уменьшается на треть; штраф сохраняется. Иных поправок нет.'
    : 'Экспериментальная редакция: при установленном A базовый срок 120 месяцев уменьшается наполовину; штраф 200000 DEMO сохраняется. Иных поправок нет.';
  const version = first ? '0.1.0' : '0.2.0';
  const provenance = {
    source,
    version,
    author: 'NormLab synthetic laboratory',
    origin: first
      ? 'prototype/normlab-architecture/examples/reduction.hcs'
      : 'MVP comparison fixture',
    review: 'local-demo-only',
  };
  return {
    id,
    version,
    title: first ? 'Уменьшение на треть' : 'Уменьшение наполовину',
    description: first ? 'Исходная синтетическая модель' : 'Экспериментальная редакция',
    ir,
    semanticDigest: digest(ir),
    provenanceDigest: digest(provenance),
    source,
    sourceKind: 'synthetic',
  };
}

export const bundles: Bundle[] = [bundle('reduction-v1', 3), bundle('reduction-v2', 2)];
export function getBundle(id: string): Bundle {
  const value = bundles.find((item) => item.id === id);
  if (!value) throw new Error('Unknown bundle');
  // Callers receive copies so the registered immutable bundle cannot be changed.
  return structuredClone(value);
}
export function validateLockedBundle(value: Bundle): void {
  deepStrictEqual(value, getBundle(value.id), 'Bundle does not match the trusted registry');
}
