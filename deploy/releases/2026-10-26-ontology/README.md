# Parking ontology and source actor — deployed 2026-10-26

[Operations #236](https://github.com/SoundBlaster/NormLab/issues/236).
[Implementation #235](https://github.com/SoundBlaster/NormLab/pull/235), source
`e8041c937f28d3644d4df3680db5d81f0cff8ace`.
[Sanitized evidence](release.json).

- Deployed to <https://managed.specgraph.tech/normlab/> using immutable image
  `ghcr.io/soundblaster/normlab@sha256:ecf74c1b818c351b513a700a34810887f64eb84e284e7ff9ae8d6bbc0dfa7de3`.
  Main CI and publication succeeded. The image-lock archive checksum matched
  GitHub metadata; six source-file hashes and the built/served revision matched
  the source commit. Separate attestation/signature verification was not performed.
- Only the three NormLab image selections changed. Environment, secret/data
  mounts, networks and ports were retained. App, gateway and egress are healthy;
  five active Platform neighbors remain healthy with unchanged container IDs and
  start times. The pre-existing stopped worker was also left unchanged.
- A private quiescent backup contains all 204 data-volume files: 100,471 bytes,
  SHA-256 `7ab198ea8868ce56d2f6a494a4ea3a5af0537800d0403186b24bfb6ddb21b49e`.
  All 201 non-SQLite files remained byte-identical after rollout. The seven-table
  SQLite logical snapshot matched the backup and `quick_check` returned `ok`.
  Eight drafts and their revision, assessment and journal counts were preserved.
- HTTPS health returned 200; unauthenticated UI/API returned 401. Authenticated
  HTML, current JS/CSS, both bootstraps and saved-data reads returned 200. The new
  fabula GET route read all 12 saved assessments with matching source/revision
  identities; it returned 10 candidate entries across those receipts and no saved
  actor decisions. These are counts across historical receipts, not unique actors.
- The free internal gateway profile returned 200 with its existing config digest
  and Luna model settings. No provider inference, Lean proof run, or case/actor
  write was performed. This is HTTP/data acceptance, not a production browser
  walkthrough or a new human approval of a role.

Disk preflight found only 1.87 GB free. Before pulling, one unreferenced NormLab
cache image from 5 October (`sha256:17e394175ba6c32ea096fab13f338a7341544e813a7cb414e60e6cff3e2256b2`)
was evicted after its anonymous GHCR manifest was verified reachable. No broad
prune or volume deletion was used. The running image and the previous rollback
image were retained. This freed space to 6.33 GB; about 2.04 GB remained after
pulling and switching.

Private backup/rollback files are retained on the VPS under
`/srv/0al/backups/normlab/2026-10-26-ontology-e8041c9`. Full runtime/config evidence,
including secret-bearing configuration snapshots, stays private under
`/srv/0al/releases/normlab/2026-10-26-ontology-e8041c9` and is not included here.

The active Compose selection uses the original runtime env plus the new image
override, in this order:

```sh
docker compose --project-name normlab-staging \
  --env-file /etc/0al/normlab-staging.env \
  --env-file /srv/0al/releases/normlab/2026-10-26-ontology-e8041c9/image.env \
  --file /srv/0al/platform/docker-compose.normlab-staging.example.yml \
  --file /srv/0al/platform/docker-compose.normlab-inference.example.yml ps
```

Retain this override for subsequent operations. The previous override and image
are retained for rollback; the original runtime env alone selects an older image.
