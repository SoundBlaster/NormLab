import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';

// Temporary mitigation for GHSA-vfj7-8cjw-p6xm, not a patched dependency.
// Count literal/escaped delimiters too: this is deliberately conservative.
export const maxGlobOpeners = 64;

function checkInput(input: unknown): void {
  if (typeof input === 'string') {
    if (input.length > 65_536) throw new Error('FSD glob exceeds 65536 characters');
    let openers = 0;
    for (const character of input) {
      if (character === '{' || character === '(') openers++;
      if (openers > maxGlobOpeners) throw new Error('FSD glob exceeds 64 opening delimiters');
    }
    return;
  }

  // Public braces walkers also accept ASTs. Traverse children iteratively;
  // parent/prev links are intentionally excluded.
  const pending: { node: unknown; depth: number }[] = [{ node: input, depth: 0 }];
  const seen = new Set<object>();
  while (pending.length > 0) {
    const entry = pending.pop();
    if (!entry || !entry.node || typeof entry.node !== 'object') continue;
    if (entry.depth > maxGlobOpeners || seen.has(entry.node) || seen.size >= 65_536) {
      throw new Error('FSD glob AST exceeds traversal limits or contains a cycle');
    }
    seen.add(entry.node);
    const nodes = (entry.node as { nodes?: unknown }).nodes;
    if (Array.isArray(nodes)) {
      if (nodes.length + pending.length > 65_536) throw new Error('FSD glob AST is too large');
      for (const node of nodes) pending.push({ node, depth: entry.depth + 1 });
    }
  }
}

type Braces = Record<
  'parse' | 'compile' | 'expand' | 'stringify',
  (input: unknown, options?: unknown) => unknown
>;
const protectedModules = new Set<string>();

export function installBracesGuard(): void {
  const steiger = createRequire(import.meta.resolve('steiger'));
  const globby = createRequire(steiger.resolve('globby'));
  const fastGlob = createRequire(globby.resolve('fast-glob'));

  // Resolve from each consumer, including nested copies after a lockfile change.
  for (const consumer of [steiger, globby, fastGlob]) {
    const micromatch = createRequire(consumer.resolve('micromatch'));
    const path = micromatch.resolve('braces');
    if (protectedModules.has(path)) continue;
    const metadata = JSON.parse(readFileSync(join(dirname(path), 'package.json'), 'utf8')) as {
      version: string;
    };
    if (metadata.version !== '3.0.3') {
      throw new Error(
        'Review/remove the temporary FSD braces guard for the new dependency version',
      );
    }
    const braces = micromatch('braces') as Braces;
    for (const method of ['parse', 'compile', 'expand', 'stringify'] as const) {
      const original = braces[method];
      braces[method] = (input, options) => {
        checkInput(input);
        return original(input, options);
      };
    }
    protectedModules.add(path);
  }
}
