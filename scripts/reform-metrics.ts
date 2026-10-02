import { writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { MAX_REFORM_JSON_BYTES, parseReformJson } from '../shared/reform-semantics.js';
import { renderReformMetricsMarkdown } from '../shared/reform-metrics.js';
import {
  measureReformExport,
  parseReformMetricsReport,
  verifyReformMetricsReport,
} from '../server/reform-metrics.js';
import { reformExportSchema } from '../server/reform-receipts.js';
import { readReformFile } from './reform-file.js';

const { values, positionals } = parseArgs({
  options: {
    'issuer-key': { type: 'string' },
    annotations: { type: 'string' },
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
    'Usage: npm run reform:metrics -- <export.json> --issuer-key <trusted-public.pem> [--annotations <annotations.json>] [--format json|markdown] [--out <new-file>] [--report <report.json>]',
  );
const artifact = reformExportSchema.parse(parseReformJson(readReformFile(positionals[0])));
const key = readReformFile(values['issuer-key'], 16 * 1024);
const annotations = values.annotations
  ? parseReformJson(readReformFile(values.annotations))
  : undefined;
const report = values.report
  ? await verifyReformMetricsReport(
      parseReformMetricsReport(readReformFile(values.report)),
      artifact,
      key,
      annotations,
    )
  : await measureReformExport(artifact, key, annotations);
const content =
  values.format === 'json'
    ? `${JSON.stringify(report, null, 2)}\n`
    : renderReformMetricsMarkdown(report);
if (values.format === 'json' && Buffer.byteLength(content, 'utf8') > MAX_REFORM_JSON_BYTES)
  throw new Error('Metrics report exceeds the 512 KiB import limit');
if (values.out) {
  writeFileSync(values.out, content, { flag: 'wx' });
  console.log(`Metrics: ${values.out}; current=${report.evidence.current}`);
} else process.stdout.write(content);
if (!report.evidence.current) process.exitCode = 1;
