import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';
import { installBracesGuard, maxGlobOpeners } from '../scripts/steiger-braces-guard';

installBracesGuard();
const require = createRequire(import.meta.url);
const braces = require('braces') as Record<string, (input: unknown, options?: unknown) => unknown>;

test('guard preserves normal brace expansion and compilation', () => {
  assert.deepEqual(braces.expand('client/{pages,shared}/**/*.{ts,tsx}'), [
    'client/pages/**/*.ts',
    'client/pages/**/*.tsx',
    'client/shared/**/*.ts',
    'client/shared/**/*.tsx',
  ]);
  assert.equal(braces.compile('{a,b}'), '(a|b)');
});

test('guard rejects nested braces and parentheses before recursive walkers', () => {
  for (const [open, close] of [
    ['{', '}'],
    ['(', ')'],
  ]) {
    for (const count of [maxGlobOpeners + 1, 10_000]) {
      const input = open.repeat(count) + 'a,b' + close.repeat(count);
      for (const method of ['parse', 'compile', 'expand', 'stringify']) {
        assert.throws(() => braces[method](input), /FSD glob exceeds 64 opening delimiters/);
      }
    }
  }
});

test('guard rejects deep/cyclic AST inputs and excessive string length', () => {
  let ast: { nodes: unknown[] } = { nodes: [] };
  for (let i = 0; i < 100; i++) ast = { nodes: [ast] };
  for (const method of ['compile', 'expand', 'stringify']) {
    assert.throws(() => braces[method](ast), /AST exceeds traversal limits/);
  }
  const cyclic = { nodes: [] as unknown[] };
  cyclic.nodes.push(cyclic);
  assert.throws(() => braces.compile(cyclic), /contains a cycle/);
  assert.throws(() => braces.parse('x'.repeat(65_537)), /exceeds 65536 characters/);
});

test('repeated installation is safe and transitive consumers use the guard', () => {
  installBracesGuard();
  const consumer = createRequire(import.meta.resolve('steiger'));
  const globby = createRequire(consumer.resolve('globby'));
  const fastGlob = createRequire(globby.resolve('fast-glob'));
  for (const resolver of [consumer, globby, fastGlob]) {
    const micromatch = resolver('micromatch') as { braceExpand: (pattern: string) => unknown };
    assert.throws(
      () => micromatch.braceExpand('{'.repeat(100) + 'a,b' + '}'.repeat(100)),
      /FSD glob/,
    );
  }
});
