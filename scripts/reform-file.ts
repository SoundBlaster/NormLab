import { closeSync, fstatSync, openSync, readSync } from 'node:fs';
import { resolve } from 'node:path';
import { MAX_REFORM_JSON_BYTES } from '../shared/reform-semantics.js';

export function readReformFile(path: string, limit = MAX_REFORM_JSON_BYTES): string {
  const absolute = resolve(path);
  const fd = openSync(absolute, 'r');
  try {
    const stat = fstatSync(fd);
    if (!stat.isFile() || stat.size > limit)
      throw new Error(`Expected a file within ${limit} bytes: ${absolute}`);
    const buffer = Buffer.alloc(limit + 1);
    let length = 0;
    while (length < buffer.length) {
      const count = readSync(fd, buffer, length, buffer.length - length, null);
      if (count === 0) break;
      length += count;
    }
    if (length > limit) throw new Error(`File exceeds ${limit} bytes: ${absolute}`);
    return new TextDecoder('utf-8', { fatal: true }).decode(buffer.subarray(0, length));
  } finally {
    closeSync(fd);
  }
}
