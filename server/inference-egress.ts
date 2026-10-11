import type { LookupAddress } from 'node:dns';
import { lookup } from 'node:dns/promises';
import { createServer } from 'node:http';
import { BlockList, connect, isIP, Socket, type LookupFunction } from 'node:net';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  DEFAULT_INFERENCE_ENDPOINTS,
  inferenceEndpoints,
  type InferenceEndpoints,
} from './inference-endpoints.js';

const blocked = new BlockList();
for (const [address, prefix] of [
  ['0.0.0.0', 8],
  ['10.0.0.0', 8],
  ['100.64.0.0', 10],
  ['127.0.0.0', 8],
  ['169.254.0.0', 16],
  ['172.16.0.0', 12],
  ['192.0.0.0', 24],
  ['192.0.2.0', 24],
  ['192.168.0.0', 16],
  ['198.18.0.0', 15],
  ['198.51.100.0', 24],
  ['203.0.113.0', 24],
  ['224.0.0.0', 3],
] as const)
  blocked.addSubnet(address, prefix, 'ipv4');
for (const [address, prefix] of [
  ['2001::', 32],
  ['2001:db8::', 32],
  ['2002::', 16],
] as const)
  blocked.addSubnet(address, prefix, 'ipv6');
const globalV6 = new BlockList();
globalV6.addSubnet('2000::', 3, 'ipv6');
export function isPublicInferenceAddress(address: string): boolean {
  const family = isIP(address);
  return family === 4
    ? !blocked.check(address, 'ipv4')
    : family === 6 && globalV6.check(address, 'ipv6') && !blocked.check(address, 'ipv6');
}
export function inferenceTunnelHost(
  authority: string | undefined,
  endpoints: InferenceEndpoints = DEFAULT_INFERENCE_ENDPOINTS,
): string | undefined {
  const endpoint = Object.values(endpoints).find((entry) => authority === entry.authority);
  return endpoint ? new URL(endpoint.url).hostname : undefined;
}

export function checkedLookup(addresses: LookupAddress[]): LookupFunction {
  return (_hostname, options, callback) => {
    if (options.all) callback(null, addresses);
    else callback(null, addresses[0].address, addresses[0].family);
  };
}

/** Opaque TLS tunnels only; no credentials, volumes, arbitrary hosts or plaintext HTTP. */
export function createInferenceEgress(
  resolver: typeof lookup = lookup,
  endpoints: InferenceEndpoints = DEFAULT_INFERENCE_ENDPOINTS,
) {
  let active = 0;
  const server = createServer((req, res) => {
    const ok = req.method === 'GET' && req.url === '/health';
    res.writeHead(ok ? 200 : 403, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(ok ? { ok: true } : { error: 'CONNECT only.' }));
  });
  server.on('connect', (req, client, head) => {
    if (!(client instanceof Socket)) {
      client.destroy();
      return;
    }
    const host = inferenceTunnelHost(req.url, endpoints);
    if (!host || active >= 4) {
      client.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n');
      return;
    }
    active++;
    client.setTimeout(125000, () => client.destroy());
    client.on('error', () => client.destroy());
    client.once('close', () => {
      active--;
    });
    void (async () => {
      try {
        const addresses = await resolver(host, { all: true });
        if (
          !addresses.length ||
          addresses.some(({ address }) => !isPublicInferenceAddress(address))
        )
          throw new Error('Non-public DNS answer.');
        if (client.destroyed) return;
        // Dial only the checked answers, never a fresh resolution (DNS rebinding), and let
        // Node fall back across them (e.g. an AAAA answer without an IPv6 route).
        const remote = connect({
          host,
          port: 443,
          autoSelectFamily: true,
          lookup: checkedLookup(addresses),
        });
        remote.setTimeout(125000, () => remote.destroy());
        remote.on('error', () => {
          remote.destroy();
          client.destroy();
        });
        remote.once('close', () => client.destroy());
        client.once('close', () => remote.destroy());
        remote.once('connect', () => {
          if (client.destroyed) {
            remote.destroy();
            return;
          }
          client.write('HTTP/1.1 200 Connection Established\r\n\r\n');
          if (head.length) remote.write(head);
          client.pipe(remote);
          remote.pipe(client);
        });
      } catch {
        if (!client.destroyed) client.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n');
      }
    })();
  });
  server.headersTimeout = 10000;
  server.requestTimeout = 15000;
  return server;
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const server = createInferenceEgress(lookup, inferenceEndpoints(process.env));
  server.listen(4319, '0.0.0.0', () =>
    console.log('NormLab inference egress listening on port 4319.'),
  );
  for (const signal of ['SIGINT', 'SIGTERM'] as const)
    process.once(signal, () => {
      server.close();
    });
}
