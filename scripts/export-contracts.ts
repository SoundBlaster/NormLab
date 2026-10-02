import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { exportedReformSchemas } from '../shared/reform-contracts.js';

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
console.log(`${check ? 'Checked' : 'Exported'} 10 schemas in ${fileURLToPath(output)}`);
