# R4 runtime bridge — deployed 2026-10-25

[Operations #234](https://github.com/SoundBlaster/NormLab/issues/234). Implementation
[#230](https://github.com/SoundBlaster/NormLab/pull/230), source `da5cd7e298867db9cb2361aeb261acb630157bff`.
[Sanitized evidence](release.json) pins publication, image, checks and proof latency.

- Three NormLab services use `ghcr.io/soundblaster/normlab@sha256:aaac76ded9c5ed7ef338ff77362095ba64634c73d5035d560f69e09e39ed967b`.
- Quiescent volume backup retained privately on the VPS with the previous image and rollback selection. No volume reset, secret changes or neighboring container restarts. All eight containers healthy after rollout.
- HTTPS health 200; unauthenticated UI 401; authenticated UI, assets, bootstrap and parking bootstrap 200. New build revision/operator-notice strings found in the served asset. Seven drafts visible. 189 archived non-SQLite files byte-identical to backup; SQLite stays on its existing volume with a consistent backup. This is HTTP/data evidence, not a browser workflow audit.
- Gateway profile answered without inference; its existing Luna configuration was retained. No provider calls or case edits.
- One-CPU / 2 GiB container, Lean cap 1024 MiB. Read-only replay of an existing archived calculation: expected fragment-refuted, all three verifier calls verified with profile/binding v2. Single: 15,347 ms; concurrent first: 19,230 ms; waiting: 34,291 ms including queue. No HTTP calculation was submitted and no receipts edited. This narrow sample is not a latency distribution; the 20-second execution window still has little margin. Optimization is [#232](https://github.com/SoundBlaster/NormLab/issues/232).
- Disk after the image pull: about 1.88 GB free. Previous images were retained; no cleanup was performed.

The active Compose selection includes both the original runtime env file and
the release image override, in this order:

```sh
docker compose --project-name normlab-staging \
  --env-file /etc/0al/normlab-staging.env \
  --env-file /srv/0al/releases/normlab/2026-10-25-r4-da5cd7e/image.env \
  --file /srv/0al/platform/docker-compose.normlab-staging.example.yml \
  --file /srv/0al/platform/docker-compose.normlab-inference.example.yml ps
```

The original runtime env still selects the prior image on its own. Future
operations must retain the active override or deliberately replace it.
Backup/rollback selections are under `/srv/0al/backups/normlab/2026-10-25-r4-da5cd7e`;
backup contents remain private and are not included here.

The later ontology UI explanation is a separate change and is not included in
this deployed source revision.
