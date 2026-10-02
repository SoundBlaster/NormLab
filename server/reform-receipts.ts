import {
  createPrivateKey,
  createPublicKey,
  generateKeyPairSync,
  randomUUID,
  sign,
  verify,
  type KeyObject,
} from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { z } from 'zod';
import {
  reformBundleSchema,
  reformCertificateSchema,
  reformQuerySchema,
  reformReceiptSchema,
  reformSnapshotSchema,
  type ReformBundle,
  type ReformCertificate,
  type ReformQuery,
  type ReformReceipt,
  type ReformSnapshot,
} from '../shared/reform-contracts.js';
import { completions, parseReformJson, ReformContractError } from '../shared/reform-semantics.js';
import {
  boundReformBundles,
  validateReformCertificateBindings,
  validateReformQuery,
  validateReformReceiptBindings,
  validateReformSnapshot,
} from './reform-bindings.js';
import { canonical, digest } from './hash.js';
import { verifyReformCertificate, type ReformVerification } from './reform-verifier.js';

export const reformExportSchema = z.strictObject({
  schema: z.literal('normlab.reform-export/v1'),
  query: reformQuerySchema,
  bundles: z.array(reformBundleSchema).min(1).max(2),
  snapshot: reformSnapshotSchema.nullable(),
  certificate: reformCertificateSchema,
  receipt: reformReceiptSchema,
});
export type ReformExport = z.infer<typeof reformExportSchema>;

function inputContext(
  query: ReformQuery,
  bundles: ReformBundle[],
  certificate: unknown,
  snapshot?: ReformSnapshot,
) {
  const snap = snapshot === undefined ? undefined : validateReformSnapshot(snapshot);
  const parsed = validateReformQuery(query, bundles, snap);
  const models = boundReformBundles(parsed, bundles, snap);
  const cert = validateReformCertificateBindings(certificate, parsed, models, snap);
  return { query: parsed, bundles: models, certificate: cert, snapshot: snap };
}
function coverage(
  query: ReformQuery,
  certificate: ReformCertificate,
  snapshot?: ReformSnapshot,
): ReformReceipt['payload']['coverage'] {
  const declaredCardinality =
    query.kind === 'decision'
      ? completions({
          narrative: snapshot!.narrative,
          group: snapshot!.group,
          findings: snapshot!.findings,
        }).length
      : query.kind === 'property' || query.condition !== null
        ? 8
        : 16;
  const coveredCardinality =
    certificate.kind === 'decision'
      ? certificate.result.branches.length
      : certificate.kind === 'comparison'
        ? certificate.result.rows.length
        : certificate.result.pairs.length;
  const corpus = certificate.kind !== 'decision' && certificate.result.method === 'corpus';
  return {
    domainDigest: digest(query.domain),
    kind: query.kind === 'decision' ? 'snapshot-completions' : corpus ? 'corpus' : 'finite-domain',
    status: corpus ? 'partial' : 'declared-complete',
    declaredCardinality,
    coveredCardinality,
  };
}

export class ReformReceiptSigner {
  private readonly key: KeyObject;
  readonly publicKey: string;
  constructor(directory?: string) {
    const path = directory === undefined ? null : join(directory, 'reform-issuer-private.pem');
    if (path && existsSync(path)) this.key = createPrivateKey(readFileSync(path));
    else {
      this.key = generateKeyPairSync('ed25519').privateKey;
      if (path)
        writeFileSync(path, this.key.export({ format: 'pem', type: 'pkcs8' }), {
          mode: 0o600,
          flag: 'wx',
        });
    }
    if (this.key.asymmetricKeyType !== 'ed25519') throw new Error('Expected an Ed25519 issuer key');
    this.publicKey = createPublicKey(this.key).export({ format: 'pem', type: 'spki' }).toString();
  }
  // Verification metadata cannot be supplied by the caller. Run the independent checker here.
  async issue(
    query: ReformQuery,
    bundles: ReformBundle[],
    certificate: unknown,
    snapshot?: ReformSnapshot,
  ): Promise<ReformReceipt> {
    const context = inputContext(query, bundles, certificate, snapshot);
    const proof = await verifyReformCertificate(
      context.query,
      context.bundles,
      context.certificate,
      context.snapshot,
    );
    if (proof.status !== 'verified')
      throw new Error(`Verified receipt unavailable: ${proof.status}: ${proof.reason}`);
    const q = context.query;
    const payload: ReformReceipt['payload'] = {
      schema: 'normlab.receipt/v2',
      id: randomUUID(),
      createdAt: new Date().toISOString(),
      queryKind: q.kind,
      bindings: {
        queryDigest: proof.queryDigest,
        certificateDigest: digest(context.certificate),
        resultDigest: digest(context.certificate.result),
        statementDigest: proof.statementDigest,
        assumptionsDigest: digest(q.assumptions),
        models:
          q.kind === 'comparison'
            ? [
                { role: 'baseline', bundle: q.baseline },
                { role: 'candidate', bundle: q.candidate },
              ]
            : [{ role: 'model', bundle: q.model }],
      },
      coverage: coverage(q, context.certificate, context.snapshot),
      verification: {
        status: proof.status,
        engine: proof.engine,
        version: proof.version,
        method: proof.method,
        toolchainDigest: proof.toolchainDigest,
        axioms: proof.axioms,
        reason: proof.reason,
      },
      issuer: digest(this.publicKey),
    };
    const receipt = {
      payload,
      signature: sign(null, Buffer.from(canonical(payload)), this.key).toString('base64'),
      publicKey: this.publicKey,
    };
    return validateReformReceiptBindings(
      receipt,
      q,
      context.certificate,
      context.bundles,
      context.snapshot,
    );
  }
}

// Signature trust alone does not establish the truth or current status of the Lean claim.
export function verifyReformReceiptSignature(value: unknown, trustedPublicKey: string): boolean {
  try {
    const receipt = reformReceiptSchema.parse(value);
    if (
      receipt.publicKey !== trustedPublicKey ||
      receipt.payload.issuer !== digest(trustedPublicKey)
    )
      return false;
    const key = createPublicKey(trustedPublicKey);
    const bytes = Buffer.from(receipt.signature, 'base64');
    if (
      key.asymmetricKeyType !== 'ed25519' ||
      bytes.length !== 64 ||
      bytes.toString('base64') !== receipt.signature
    )
      return false;
    return verify(null, Buffer.from(canonical(receipt.payload)), key, bytes);
  } catch {
    return false;
  }
}

export type ReformReceiptReplay = {
  signatureValid: boolean;
  bindingsValid: boolean;
  current: boolean;
  verification: ReformVerification | null;
  reason: string;
};
export async function replayReformReceipt(
  input: unknown,
  trustedPublicKey: string,
  query: ReformQuery,
  bundles: ReformBundle[],
  certificate: unknown,
  snapshot?: ReformSnapshot,
): Promise<ReformReceiptReplay> {
  const base: ReformReceiptReplay = {
    signatureValid: false,
    bindingsValid: false,
    current: false,
    verification: null,
    reason: 'Untrusted or invalid receipt signature',
  };
  if (!verifyReformReceiptSignature(input, trustedPublicKey)) return base;
  base.signatureValid = true;
  let receipt: ReformReceipt;
  let context: ReturnType<typeof inputContext>;
  try {
    context = inputContext(query, bundles, certificate, snapshot);
    receipt = validateReformReceiptBindings(
      input,
      context.query,
      context.certificate,
      context.bundles,
      context.snapshot,
    );
    base.bindingsValid = true;
  } catch (error) {
    return { ...base, reason: error instanceof Error ? error.message : 'Invalid receipt bindings' };
  }
  const proof = await verifyReformCertificate(
    context.query,
    context.bundles,
    context.certificate,
    context.snapshot,
  );
  const claimed = receipt.payload.verification;
  const actual = {
    status: proof.status,
    engine: proof.engine,
    version: proof.version,
    method: proof.method,
    toolchainDigest: proof.toolchainDigest,
    axioms: proof.axioms,
    reason: proof.reason,
  };
  const current =
    proof.status === 'verified' &&
    receipt.payload.bindings.statementDigest === proof.statementDigest &&
    digest(claimed) === digest(actual);
  return {
    ...base,
    current,
    verification: proof,
    reason: current
      ? 'Trusted signature, exact bindings and fresh Lean verification agree'
      : 'Historical or mismatched receipt; fresh verification does not confirm its exact claim/toolchain',
  };
}

export function exportReformArtifacts(
  query: ReformQuery,
  bundles: ReformBundle[],
  certificate: unknown,
  receipt: unknown,
  snapshot?: ReformSnapshot,
): ReformExport {
  const context = inputContext(query, bundles, certificate, snapshot);
  const boundReceipt = validateReformReceiptBindings(
    receipt,
    context.query,
    context.certificate,
    context.bundles,
    context.snapshot,
  );
  return reformExportSchema.parse({
    schema: 'normlab.reform-export/v1',
    ...context,
    snapshot: context.snapshot ?? null,
    receipt: boundReceipt,
  });
}
export async function replayReformExport(
  text: string,
  trustedPublicKey: string,
): Promise<ReformReceiptReplay> {
  let artifact: ReformExport;
  try {
    artifact = reformExportSchema.parse(parseReformJson(text));
  } catch (error) {
    throw new ReformContractError(
      'invalid',
      error instanceof Error ? error.message : 'Invalid export',
    );
  }
  return replayReformReceipt(
    artifact.receipt,
    trustedPublicKey,
    artifact.query,
    artifact.bundles,
    artifact.certificate,
    artifact.snapshot ?? undefined,
  );
}
