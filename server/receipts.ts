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
import type {
  Bundle,
  Certificate,
  ReceiptPayload,
  SignedReceipt,
  Snapshot,
  Verification,
} from '../shared/domain.js';
import { canonical, digest } from './hash.js';

export class ReceiptSigner {
  private key: KeyObject;
  readonly publicKey: string;
  constructor(directory?: string) {
    const path = directory ? join(directory, 'issuer-private.pem') : null;
    if (path && existsSync(path)) this.key = createPrivateKey(readFileSync(path));
    else {
      this.key = generateKeyPairSync('ed25519').privateKey;
      if (path)
        writeFileSync(path, this.key.export({ format: 'pem', type: 'pkcs8' }), {
          mode: 0o600,
          flag: 'wx',
        });
    }
    this.publicKey = createPublicKey(this.key).export({ format: 'pem', type: 'spki' }).toString();
  }
  issue(
    snapshot: Snapshot,
    bundle: Bundle,
    certificate: Certificate,
    verification: Verification,
  ): SignedReceipt {
    const assumptions = [
      'Synthetic norms only; no claim about real legislation.',
      'Finding recorded by a simulated reviewer; truth of the narrative is not proved.',
      'Exactly one adjustment; no external rules; integer months and DEMO currency.',
      'Trusted local registry, statement constructor, Lean 4.30.0 kernel and local host.',
    ];
    const payload: ReceiptPayload = {
      schema: 'normlab.receipt/v1',
      id: randomUUID(),
      createdAt: new Date().toISOString(),
      snapshotId: snapshot.id,
      snapshotDigest: snapshot.digest,
      bundleId: bundle.id,
      bundleSemanticDigest: bundle.semanticDigest,
      bundleProvenanceDigest: bundle.provenanceDigest,
      queryDigest: digest({
        kind: certificate.query,
        snapshot: snapshot.digest,
        bundle: bundle.semanticDigest,
      }),
      certificateDigest: digest(certificate),
      resultDigest: digest(certificate.result),
      assumptionDigest: digest(assumptions),
      assumptions,
      scope: 'synthetic-single-adjustment',
      coverageStatus: 'declared-complete',
      verification,
      issuer: digest(this.publicKey),
    };
    return {
      payload,
      signature: sign(null, Buffer.from(canonical(payload)), this.key).toString('base64'),
      publicKey: this.publicKey,
    };
  }
}

export function verifyReceipt(receipt: SignedReceipt, trustedPublicKey: string): boolean {
  try {
    if (
      receipt.publicKey !== trustedPublicKey ||
      receipt.payload.issuer !== digest(trustedPublicKey)
    )
      return false;
    return verify(
      null,
      Buffer.from(canonical(receipt.payload)),
      trustedPublicKey,
      Buffer.from(receipt.signature, 'base64'),
    );
  } catch {
    return false;
  }
}
