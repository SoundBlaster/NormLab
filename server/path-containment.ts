import { sep } from 'node:path';

export function isWithinDirectory(directory: string, file: string, separator = sep): boolean {
  const prefix = directory.endsWith(separator) ? directory : `${directory}${separator}`;
  return file.startsWith(prefix);
}
