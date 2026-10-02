# Generated schemas for the reform profile

Source: [shared/reform-contracts.ts](../../shared/reform-contracts.ts). Documentation: [CONTRACTS.md](../../docs/CONTRACTS.md).

These files use [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12). Each local `$id` is an opaque `urn:normlab:contract:v2:*` identifier. No remote resolver is required.

```sh
npm run schemas:write
npm run schemas:check
```

Edit the Zod source and regenerate the JSON files. The generated files preserve the deterministic encoding of the exporter. Contextual validation, supported semantics, artifact bindings, signature trust and proof verification are separate from JSON shape validation.

The v2 contracts are implemented as a separate core. The current HTTP API and UI continue to use M0/v1.
