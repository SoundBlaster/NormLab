import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { installBracesGuard } from './steiger-braces-guard';

installBracesGuard();
// Load the CLI only after protecting its CommonJS braces dependency instances.
const cli = join(dirname(fileURLToPath(import.meta.resolve('steiger'))), 'cli.mjs');
await import(pathToFileURL(cli).href);
