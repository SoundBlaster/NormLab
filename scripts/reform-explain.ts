import { writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { MAX_REFORM_JSON_BYTES, parseReformJson } from '../shared/reform-semantics.js';
import { renderReformExplanationMarkdown } from '../shared/reform-explanations.js';
import {
  explainReformExport,
  parseReformExplanationReport,
  verifyReformExplanationReport,
} from '../server/reform-explanations.js';
import { reformExportSchema } from '../server/reform-receipts.js';
import { readReformFile } from './reform-file.js';

const { values, positionals } = parseArgs({
  options: {
    'issuer-key': { type: 'string' },
    format: { type: 'string', default: 'markdown' },
    out: { type: 'string' },
    report: { type: 'string' },
  },
  allowPositionals: true,
});
if (
  positionals.length !== 1 ||
  !values['issuer-key'] ||
  !['json', 'markdown'].includes(values.format)
)
  throw new Error(
    'Usage: npm run reform:explain -- <export.json> --issuer-key <trusted-public.pem> [--format json|markdown] [--out <new-file>] [--report <report.json>]',
  );
const artifact = reformExportSchema.parse(parseReformJson(readReformFile(positionals[0])));
const key = readReformFile(values['issuer-key'], 16 * 1024);
const report = values.report
  ? await verifyReformExplanationReport(
      parseReformExplanationReport(readReformFile(values.report)),
      artifact,
      key,
    )
  : await explainReformExport(artifact, key);
const content =
  values.format === 'json'
    ? `${JSON.stringify(report, null, 2)}\n`
    : renderReformExplanationMarkdown(report);
if (values.format === 'json' && Buffer.byteLength(content, 'utf8') > MAX_REFORM_JSON_BYTES)
  throw new Error('Explanation report exceeds the 512 KiB import limit');
if (values.out) {
  writeFileSync(values.out, content, { flag: 'wx' });
  console.log(`Explanation: ${values.out}; current=${report.evidence.current}`);
} else process.stdout.write(content);
if (!report.evidence.current) process.exitCode = 1;
