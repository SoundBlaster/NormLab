import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import test from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { parkingFixture, inconclusiveParkingProof } from './parking-legal-fixture.js';
import {
  evaluateParkingFragment,
  parkingNormDraft,
  type LegalAssessment,
} from '../shared/parking-legal.js';

// CSS is supplied by Vite in the app; this render-only test needs no stylesheet loader.
const hooks = registerHooks({
  load(url, context, nextLoad) {
    return url.endsWith('.css')
      ? { format: 'module', source: '', shortCircuit: true }
      : nextLoad(url, context);
  },
});
const { LegalResultView } = await import('../client/pages/parking-review/ui/LegalResultView.js');
hooks.deregister();

function render(status: 'verified' | 'rejected', previous = false, stale = false) {
  const { input } = parkingFixture();
  const result = evaluateParkingFragment(input);
  const record: LegalAssessment = {
    schema: 'normlab.parking-legal-assessment/v2',
    id: input.requestId,
    sequence: 1,
    createdAt: new Date().toISOString(),
    actor: 'human-operator',
    sourceDigest: '0'.repeat(64),
    input,
    result,
    package: parkingNormDraft,
    verification: { ...inconclusiveParkingProof(input, result), status },
    verifiedByPreviousProfile: previous,
  };
  return renderToStaticMarkup(
    createElement(LegalResultView, {
      record,
      stale,
      workspace: {
        package: parkingNormDraft,
        packageDigest: input.packageDigest,
        assessments: [record],
      },
    }),
  );
}

test('previous profiles and stale inputs cannot render green Lean verification', () => {
  assert.match(render('verified'), /data-tone="success"/);
  const previous = render('verified', true);
  assert.match(previous, /Проверено прежней моделью PoC/);
  assert.doesNotMatch(previous, /data-tone="success"/);
  assert.doesNotMatch(render('verified', false, true), /data-tone="success"/);
});

test('rejected candidate and sanction are inside a closed disclosure below the failure heading', () => {
  const html = render('rejected');
  assert.match(html, /<h3>Расчёт отклонён проверкой Lean<\/h3>/);
  assert.match(html, /data-tone="danger"/);
  assert.doesNotMatch(html, /data-tone="success"/);
  const details = html.match(
    /<details[^>]*><summary>Показать отвергнутый draft-расчёт<\/summary>([\s\S]*?)<\/details>/,
  );
  assert.ok(details);
  assert.doesNotMatch(details[0].slice(0, details[0].indexOf('>')), /\bopen\b/);
  assert.match(details[1], /Санкция-кандидат/);
  assert.doesNotMatch(html.slice(0, html.indexOf(details[0])), /Санкция-кандидат/);
});
