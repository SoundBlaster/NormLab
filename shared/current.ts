import type { Analysis, Bundle, Snapshot } from './domain.js';

export function isCurrentAnalysis(
  analysis: Analysis,
  snapshot: Snapshot,
  bundle: Bundle,
  toolchainDigest: string | null,
): boolean {
  const receipt = analysis.receipt.payload;
  return (
    toolchainDigest !== null &&
    receipt.verification.toolchainDigest === toolchainDigest &&
    receipt.snapshotDigest === snapshot.digest &&
    receipt.bundleSemanticDigest === bundle.semanticDigest &&
    receipt.bundleProvenanceDigest === bundle.provenanceDigest &&
    analysis.snapshotId === snapshot.id &&
    analysis.bundleId === bundle.id
  );
}
