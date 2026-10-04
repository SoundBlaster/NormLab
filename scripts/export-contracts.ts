import { parkingModelV2JsonSchema } from '../server/parking-typed-extraction.js';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { exportedReformSchemas } from '../shared/reform-contracts.js';
import { z } from 'zod';
import { exportedParkingExtractionSchema } from '../shared/parking-contracts.js';
import { portableExperimentSchema } from '../server/reform-transfer.js';

const output = new URL('../schemas/v2/', import.meta.url);
const check = process.argv.includes('--check');
if (!check) mkdirSync(output, { recursive: true });
for (const [name, schema] of Object.entries(exportedReformSchemas())) {
  const file = new URL(`${name}.schema.json`, output);
  const content = `${JSON.stringify(schema, null, 2)}\n`;
  if (check) {
    if (readFileSync(file, 'utf8') !== content) throw new Error(`Stale schema: ${name}`);
  } else {
    writeFileSync(file, content);
  }
}
const transferOutput = new URL('../schemas/transfer/', import.meta.url);
const transferFile = new URL('experiment.schema.json', transferOutput);
const transferContent = `${JSON.stringify(z.toJSONSchema(portableExperimentSchema, { target: 'draft-2020-12' }), null, 2)}\n`;
if (check) {
  if (readFileSync(transferFile, 'utf8') !== transferContent)
    throw new Error('Stale experiment schema');
} else {
  mkdirSync(transferOutput, { recursive: true });
  writeFileSync(transferFile, transferContent);
}
console.log(
  `${check ? 'Checked' : 'Exported'} 10 v2 schemas and experiment schema in ${fileURLToPath(output)}`,
);

const parkingOutput = new URL('../schemas/parking/', import.meta.url);
const parkingFile = new URL('extraction.schema.json', parkingOutput);
const parkingContent = `${JSON.stringify(exportedParkingExtractionSchema(), null, 2)}\n`;
if (check) {
  if (readFileSync(parkingFile, 'utf8') !== parkingContent)
    throw new Error('Stale parking extraction schema');
} else {
  mkdirSync(parkingOutput, { recursive: true });
  writeFileSync(parkingFile, parkingContent);
}
console.log(`${check ? 'Checked' : 'Exported'} parking extraction schema`);

const typedParkingOutput = new URL('../schemas/parking/', import.meta.url);
const typedParkingFile = new URL('model-proposal-v2.schema.json', typedParkingOutput);
const typedParkingContent = `${JSON.stringify(parkingModelV2JsonSchema, null, 2)}\n`;
if (check) {
  if (readFileSync(typedParkingFile, 'utf8') !== typedParkingContent)
    throw new Error('Stale parking model proposal v2 schema');
} else {
  mkdirSync(typedParkingOutput, { recursive: true });
  writeFileSync(typedParkingFile, typedParkingContent);
}
console.log(`${check ? 'Checked' : 'Exported'} parking model proposal v2 schema`);
