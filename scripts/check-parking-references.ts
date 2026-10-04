import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import manifest from '../fixtures/parking-pilot/reference/manifest.json';
import { parseParkingExtraction } from '../shared/parking-contracts.js';

const root = new URL('../fixtures/parking-pilot/reference/', import.meta.url);
const corpus = readFileSync(new URL('../fixtures/parking-pilot/CASES.md', import.meta.url), 'utf8');
const expectedIds = ['P01', 'P02', 'P04', 'P09'];
const sha256 = (text: string) => createHash('sha256').update(text, 'utf8').digest('hex');
if (JSON.stringify(manifest.cases.map((item) => item.id)) !== JSON.stringify(expectedIds))
  throw new Error('Unexpected reference case set/order');
if (
  manifest.contract !== 'normlab.parking-extraction/v1' ||
  manifest.status !== 'candidate-reference-draft'
)
  throw new Error('Unexpected reference manifest');

for (const item of manifest.cases) {
  if (item.sourceFile !== `${item.id}.source.txt` || item.graphFile !== `${item.id}.graph.json`)
    throw new Error(`Invalid reference path: ${item.id}`);
  const source = readFileSync(new URL(item.sourceFile, root), 'utf8');
  const raw = readFileSync(new URL(item.graphFile, root), 'utf8');
  if (sha256(source) !== item.sourceSha256 || sha256(raw) !== item.graphSha256)
    throw new Error(`Reference digest mismatch: ${item.id}`);
  const section = corpus.split(`## ${item.id} — `)[1]?.split('\n## ')[0];
  const narrative = section?.match(/### Фабула\n\n> ([^\n]+)/)?.[1];
  if (!narrative || source !== `${narrative}\n`)
    throw new Error(`Reference source differs from CASES.md: ${item.id}`);
  const validation = parseParkingExtraction(raw, source);
  if (!validation.ok) throw new Error(`${item.id}: ${JSON.stringify(validation.issues)}`);
  const graph = validation.proposal;
  const conflicts = item.reviewerOnly.conflictAssertionIds.map((id) => {
    const assertion = graph.assertions.find((entry) => entry.id === id);
    if (!assertion) throw new Error(`Missing reviewer conflict assertion: ${item.id}/${id}`);
    return assertion;
  });
  // Confirm the annotated pair survives structurally; do not claim generic semantic detection.
  if (
    item.id === 'P09' &&
    (conflicts.length !== 2 ||
      conflicts[0]?.predicate !== 'nlinput:payment' ||
      conflicts[1]?.predicate !== 'nlinput:payment' ||
      conflicts[0]?.subject !== conflicts[1]?.subject ||
      conflicts[0]?.aboutEpisode !== conflicts[1]?.aboutEpisode ||
      conflicts[0]?.stance !== 'asserted' ||
      conflicts[1]?.stance !== 'denied')
  )
    throw new Error('P09 must preserve the annotated opposing payment proposals');
  console.log(
    `${item.id}: PASS (${graph.entities.length} entities, ${graph.assertions.length} assertions, ${graph.unmappedMentions.length} unmapped mentions)`,
  );
}
console.log(
  '4 candidate reference graphs match source digests, corpus, and extraction contract. Semantic/legal approval and model evaluation remain separate.',
);
