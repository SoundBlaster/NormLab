const configuredMemory = Number(process.env.NORMLAB_LEAN_MEMORY_MB ?? 512);
const memory =
  Number.isInteger(configuredMemory) && configuredMemory >= 512 && configuredMemory <= 4096
    ? configuredMemory
    : 512;

export const leanMemoryArgument = `-M${memory}`;
