# NormLab demo update: checkpoints and Continue

Prepared 2026-10-21 for [task #183](https://github.com/SoundBlaster/NormLab/issues/183).
Implementation: [#179](https://github.com/SoundBlaster/NormLab/issues/179), merged
PRs #180–182. This package is **prepared, not deployed**.

| Item                                     | Pinned value / observation                                                                             |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Application source                       | `299d85b371e83e112e66aa0b6f00177524b219b5`                                                             |
| Image                                    | `ghcr.io/soundblaster/normlab@sha256:21315695312d53fb19ce73f07de529cb8a79527c4d41b75ee3cdaf6e7f1fca68` |
| Architecture / UI prefix                 | `linux/amd64`, `/normlab/` (publication workflow build argument)                                       |
| Publication                              | [successful run 39659310316](https://github.com/SoundBlaster/NormLab/actions/runs/39659310316)         |
| Platform reference for offline rendering | `0al-spec/Platform@00de155b8bccd7e751d21d7df43c9b0e81a6e7d8`                                           |
| Intended route                           | `https://managed.specgraph.tech/normlab/`                                                              |
| Public checks during preparation         | Health 200; unauthenticated UI 401 on controlled IPv4 retry                                            |
| Current remote image                     | `ghcr.io/soundblaster/normlab@sha256:17e394175ba6c32ea096fab13f338a7341544e813a7cb414e60e6cff3e2256b2` |
| Live inventory                           | Verified 2026-10-22; [live-preflight.json](live-preflight.json)                                        |
| Registry / rollout                       | Target manifest access rejected for authentication; no layers downloaded or deployment performed       |

[release.json](release.json) records the publication/artifact provenance.
`artifact_archive_digest` authenticates the GitHub artifact archive, **not** the
container image. The OCI image digest is the one in `image_ref` and
[image.env](image.env). Publication succeeded; registry pull access and independent
SBOM/provenance verification have not been established by this preparation.
The producer lock declares a private source repository, but the source repo is
currently public; that stale producer flag is not copied into our readiness data.

## Verified VPS baseline — 2026-10-22

The operator unlocked the existing `0al-platform-canary` identity in the local
SSH agent. The server accepted it. Some new connections still closed before
authentication; one multiplexed SSH session allowed the read-only inventory to
complete. The cause of those intermittent closures was not established.

- Project `normlab-staging`, working directory `/srv/0al/platform`; one active
  file, `docker-compose.normlab-staging.example.yml`, with SHA-256 matching the
  pinned Platform reference. Runtime env file: `/etc/0al/normlab-staging.env`.
- App started 2026-10-06 and is healthy. Its old image has no source revision
  label; do not infer a source commit from its digest.
- Existing volume `normlab-staging_normlab-data` is mounted at `/var/lib/normlab`;
  operator password is mounted read-only. Existing ingress network is
  `platform-managed-normlab`; no application host port is published.
- No inference gateway is running. The inference mode variable is unset, no
  provider-key variable or mount is present in the app, and the supported
  `/srv/0al/secrets/normlab-inference` directory does not exist. This describes
  the current NormLab configuration, not every unrelated file on the VPS.
- All six running containers are healthy. The snapshot has about 40.7 GB free
  disk and 3.05 GB available RAM (decimal units); download/backup sizes and
  maintenance-window idleness still require an apply-time check.
- Current Compose environment matches the running app. Rendering with the target
  digest changes **only** `services.normlab.image`; volume, secrets, networks and
  all other rendered service settings remain identical. VPS Compose is 2.40.3.
- Public HTTPS: health 200, UI without auth 401, authenticated UI, JavaScript
  asset and `/normlab/api/bootstrap` 200. Existing operator credentials were used
  inside a server-side process, without exporting or recording their values.
  Direct internal HTTP checks returned 403 even with the public Host header;
  they did not reproduce the ingress context and are not the public auth result.

### Image access and automatic updates

The existing publisher workflow builds/pushes an image on `main`; it contains no
SSH or VPS deploy step. No matching NormLab/Watchtower/Compose updater was found
in the inspected root cron files or direct `/etc/systemd/system` unit files, and
the running timer list contains no NormLab deploy timer. This bounded inventory
does not audit external orchestration or every vendor-provided unit.

The target image is **not cached on the VPS**. A read-only `docker manifest
inspect` for its exact digest was rejected for authentication; no pull was
attempted. The local `gh` token currently lacks `read:packages`. Do not treat
image publication or a public source repository as verified registry access.
Package visibility was not independently queried. GitHub documents package
permissions separately and permits public image access anonymously; for a
private package a classic token with `read:packages`, or an authorized workflow
`GITHUB_TOKEN`, supplies the pull access. See
[GitHub Container registry authentication](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-to-the-container-registry).

For this image-only rollout, authorize the registry pull before stopping the
app. Supply a least-privilege credential privately through stdin; keep any
temporary Docker auth config outside the repository and remove it after the
pull. Never reuse provider API keys or the operator password as registry tokens.
No registry credential has been installed by this preparation.

Automatic VPS rollout remains a separate implementation: successful publication
must hand the exact image digest to a deploy job with its own SSH machine
identity, backup/check/rollback policy and explicit credential provisioning.
Loading the operator's encrypted SSH key into the Mac agent does not provision
that identity for GitHub Actions. No auto-updater is installed by this package.

### What this concrete update will provide

The verified live profile is the **base manual profile**. Its approved rollout
updates only `normlab`, retaining the volume, password and ingress; it does not
recreate the five Platform neighbors. It brings the published application
changes to the demo. Hosted extraction/checkpoint Continue will still need an
explicit inference activation: install the selected supplier's key, configure
its endpoint and add the gateway/egress profile. D1 remains an additional hosted
adapter task; research support alone is insufficient.

Preparation does not install API keys or authorize a paid smoke. Keep the
existing service running until registry access, rollout review, idleness and
the verified backup gates below are complete.

## Scope and apply gates

This is an **image-only** update in the existing VPS Compose project. Keep the
current file list, networks, volume, operator password, inference mode, provider,
models, endpoints, quota and secret mounts. The package does not enable inference,
install keys, switch models, create a Timeweb application or update shared Caddy.

- Base manual profile: update only `normlab`. Manual features/journal update, but
  hosted jobs/Continue remain unavailable while inference is disabled.
- Already-enabled inference profile: update `normlab`,
  `normlab-inference-gateway` and `normlab-inference-egress` to the **same digest**.
  The new app needs authenticated `/v1/profile` and `/v1/stage`; leaving an old
  gateway behind can produce an endpoint/protocol failure despite green health.
- TypeScript hosted classifiers are `openai`, `typesafe`, `decisions`. The D1
  research/evaluation adapter does not itself add a D1 hosted gateway slot. No
  provider choice is inferred from past evaluation results.
- New API endpoints/key provisioning require a separately reviewed activation
  change. Platform reference overlays still use base-URL settings; arbitrary
  full-endpoint overrides are not forwarded by those reference files.

**Do not apply until the live inventory below is complete and the operator has
approved the concrete rollout.** A 200 health response checks a process, not
its image version, auth workflow, persistence, credentials or paid inference.

## 1. Read-only inventory on the VPS

Use the actual operator account/accepted SSH identity. Initial batch-mode attempts
failed while the encrypted private key was absent from the local agent. After
the operator unlocked it, read-only access succeeded. Recheck the snapshot below
before apply; do not disable SSH host-key verification or guess other keys.

On the host, inspect only the relevant service and safe metadata:

```bash
docker ps --format '{{.Names}} | {{.Image}} | {{.Status}}'
docker compose ls
df -h /
free -m
docker stats --no-stream

# Set this only after confirming the project in docker compose ls.
PROJECT=normlab-staging
mapfile -t CIDS < <(docker ps -q \
  --filter "label=com.docker.compose.project=$PROJECT" \
  --filter label=com.docker.compose.service=normlab)
test "${#CIDS[@]}" -eq 1 || exit 1
CID="${CIDS[0]}"
docker inspect --format \
  'image={{.Config.Image}} id={{.Image}} dir={{index .Config.Labels "com.docker.compose.project.working_dir"}} files={{index .Config.Labels "com.docker.compose.project.config_files"}}' "$CID"
docker inspect --format \
  '{{range .Mounts}}{{if eq .Destination "/var/lib/normlab"}}{{.Type}} {{.Name}} {{.Source}}{{end}}{{end}}' "$CID"
docker inspect --format '{{json .NetworkSettings.Networks}}' "$CID"
```

Record the actual project, complete active Compose file list and order, env-file
path, app image digest and actual named data volume. The historical volume hint
`normlab-staging_normlab-data` must match the mount; do not create a replacement
empty volume if it differs. Inventory neighbors and service health. Check the
inference mode using an allowlisted output, not a full environment dump:

```bash
docker exec "$CID" node -e \
  'console.log(JSON.stringify({mode:process.env.NORMLAB_INFERENCE_MODE??"disabled"}))'
```

Confirm one app owner, no active extraction/job and a maintenance window before
stopping the app. Do not interrupt an active billed request merely to deploy;
an interrupted reservation remains unknown, not a free failure. Confirm enough
disk for the old/new images and a full backup and enough RAM for existing service
limits. Record the accepted previous digest as `OLD_IMAGE`; confirm its image is
locally retained. If current files/env do not reproduce the inspected topology,
stop and reconcile them first. Do not print rendered secrets or provider bodies.
For a three-service deployment, require that the previously running services also
share that captured digest; otherwise a single `rollback.env` cannot reproduce
the old state and this recipe must be adjusted before apply.

## 2. Assemble the exact existing profile and render

Use a root-owned private work directory on the host. Copy this release folder
there; it contains no credential values. The following values match the
2026-10-22 inventory and must be rechecked before apply:

```bash
RELEASE_DIR=/srv/0al/releases/normlab/2026-10-21-checkpoints
RUNTIME_ENV=/etc/0al/normlab-staging.env
PLATFORM_DIR=/srv/0al/platform
cd "$PLATFORM_DIR"

# EXACT current list/order from inventory. For a base-only deployment:
FILES=(--file docker-compose.normlab-staging.example.yml)
SERVICES=(normlab)
# If inference is ALREADY enabled, add its current overlay and existing services:
# FILES+=(--file docker-compose.normlab-inference.example.yml)
# SERVICES+=(normlab-inference-gateway normlab-inference-egress)
# Retain the existing TypeSafe overlay, if selected, in its original order.

next_compose() (
  # Shell variables outrank --env-file. Exclude a stale image-only shell override.
  unset PLATFORM_NORMLAB_IMAGE
  docker compose --project-name "$PROJECT" \
    --env-file "$RUNTIME_ENV" --env-file "$RELEASE_DIR/image.env" \
    "${FILES[@]}" "$@"
)
next_compose config --quiet
next_compose config --images
next_compose pull "${SERVICES[@]}"
```

Verify rendered images equal the pinned digest for every selected NormLab
service, the data mount is unchanged and no helper publishes a host port. Compare
all other settings with the inspected configuration in a private file if needed;
never paste a full rendered environment into chat/CI. Stop if the env-file or
shell would change anything other than the intended image. Pull success is a
separate gate: authenticate privately with the existing least-privilege registry
credential if needed, not with browser/operator/provider keys.

## 3. Quiesce and back up before recreation

Capture `OLD_IMAGE` and `DATA_VOLUME` from inventory; both must be verified.
Protect backup contents: the volume includes SQLite/WAL, signing identity,
narratives/revisions, journals, job state and raw checkpoints. No volume schema
reset is needed for this release. Stop only the NormLab app after confirming it
is idle; neighboring Platform services keep running.

```bash
umask 077
: "${OLD_IMAGE:?capture the previous digest from inventory}"
: "${DATA_VOLUME:?capture the actual mounted data volume}"
: "${CID:?capture the current app container ID}"
docker volume inspect "$DATA_VOLUME" >/dev/null
LIVE_VOLUME="$(docker inspect --format '{{range .Mounts}}{{if and (eq .Type "volume") (eq .Destination "/var/lib/normlab")}}{{.Name}}{{end}}{{end}}' "$CID")"
test "$DATA_VOLUME" = "$LIVE_VOLUME" || exit 1
LIVE_IMAGE="$(docker inspect --format '{{.Config.Image}}' "$CID")"
test "$OLD_IMAGE" = "$LIVE_IMAGE" || exit 1
case "$OLD_IMAGE" in *@sha256:*) ;; *) exit 1 ;; esac
docker image inspect "$OLD_IMAGE" >/dev/null
BACKUP_DIR=/srv/0al/backups/normlab/2026-10-21-checkpoints
install -d -m 0700 "$BACKUP_DIR"
test ! -e "$BACKUP_DIR/volume.tgz" || exit 1
printf 'PLATFORM_NORMLAB_IMAGE=%s\n' "$OLD_IMAGE" > "$BACKUP_DIR/rollback.env"
chmod 0600 "$BACKUP_DIR/rollback.env"

next_compose stop normlab
docker run --rm --pull=never --network none --read-only --user 0:0 \
  --mount "type=volume,src=$DATA_VOLUME,dst=/var/lib/normlab,readonly" \
  --mount "type=bind,src=$BACKUP_DIR,dst=/backup" \
  --entrypoint sh "$OLD_IMAGE" \
  -ec 'umask 077; tar -czf /backup/volume.tgz -C /var/lib/normlab .; tar -tzf /backup/volume.tgz >/dev/null'
sha256sum "$BACKUP_DIR/volume.tgz" > "$BACKUP_DIR/volume.tgz.sha256"
```

File-level copying while the app is running is not a consistent SQLite/WAL/job
backup. Confirm the archive and checksum before recreating anything. If backup
fails, keep the old image/config and restart the old app using the rollback
function below; do not discard its live volume. Protect/copy the backup to the
existing off-host backup system as appropriate; no new storage is provisioned by
this package.

## 4. Recreate and verify

For an existing inference profile, app is stopped first. Updating only these
services uses the same image and their existing health dependencies:

```bash
next_compose up --detach --wait --wait-timeout 180 --no-build --pull never \
  "${SERVICES[@]}"
next_compose ps
```

Compose recreation preserves mounted volumes; it is not a backup guarantee. See
[Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/).
Do not use shared `down`, `--volumes` or `--remove-orphans`. Do not restart Caddy
or unrelated Platform services for this image-only update. Before reopening the
operator UI, verify:

- Inspected image digests for all selected services, original data volume and
  neighbors' health. Exactly one app owner, no new public helper port/network.
- `/normlab/health` 200; unauthenticated page and protected API 401; authenticated
  UI/bootstrap and static assets 200 under `/normlab/`. TLS failures are transport
  failures, not successful auth or HTTP responses.
- Existing drafts, revisions, journal and pending proposals are visible. Reading
  bootstrap/job/journal does not start provider inference.
- If gateway mode is already enabled, call authenticated internal `/v1/profile`
  using the existing token read inside the app process. Print only protocol,
  configured models and config digest; expect `normlab.hosted-stage/v1`. This
  profile call is free of provider inference; green health alone is insufficient.
- New in-flight/unknown state after restart stays paused until explicit user
  action. Never auto-repeat unknown attempts during deployment verification.

The free internal protocol check uses the existing app token without printing it:

```bash
next_compose exec -T normlab node --input-type=module - <<'JS'
import { readFileSync } from 'node:fs';
const base = process.env.NORMLAB_INFERENCE_GATEWAY_URL;
const file = process.env.NORMLAB_INFERENCE_TOKEN_FILE;
if (!base || !file) process.exit(1);
const token = readFileSync(file, 'utf8').replace(/\r?\n$/, '');
const response = await fetch(`${base}/v1/profile`, {
  method: 'POST', redirect: 'error', signal: AbortSignal.timeout(10000),
  headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  body: '{}',
});
if (!response.ok) { console.log({ httpStatus: response.status }); process.exit(1); }
const profile = await response.json();
if (profile.protocol !== 'normlab.hosted-stage/v1') process.exit(1);
console.log({ protocol: profile.protocol, classifier: profile.classifier,
  discoveryModel: profile.discoveryModel, classificationModel: profile.classificationModel,
  configDigest: profile.configDigest });
JS
```

Do not run `/v1/stage`, `/v1/extract` or browser Start/Continue against real
providers as an unapproved smoke. A live semantic acceptance run needs its own
explicit request/cost limits; a future genuine end-to-end failure probe is also
billable. [Local synthetic smoke](../../../docs/HOSTED_CHECKPOINT_JOBS.md) already
checked the UI flow; it does not prove remote provider availability.

## 5. Roll back without deleting state

Use the **original profile** and the captured digest, not an old tag from memory:

```bash
rollback_compose() (
  unset PLATFORM_NORMLAB_IMAGE
  docker compose --project-name "$PROJECT" \
    --env-file "$RUNTIME_ENV" --env-file "$BACKUP_DIR/rollback.env" \
    "${FILES[@]}" "$@"
)
rollback_compose config --quiet
rollback_compose up --detach --wait --wait-timeout 180 --no-build --pull never \
  "${SERVICES[@]}"
```

Recheck health/auth, mounted volume and neighbors. Rolling back an image does not
guarantee an arbitrarily old application can read new JSON revisions. If data
compatibility blocks rollback, preserve the current volume and restore the
verified pre-update backup into a **new volume** using the existing recovery
procedure; authorize switching that volume explicitly. Never restore over the
only live copy, erase signing identity or silently delete post-update edits.

## Preparation evidence and remaining gate

Image publication/lock, reference Compose rendering, live inventory, public HTTP
and source/browser tests are separate evidence. [validation.json](validation.json)
retains the original 2026-10-21 offline receipt and Platform reference hashes.
[live-preflight.json](live-preflight.json) adds the 2026-10-22 VPS snapshot and
image-only render comparison, successful public auth checks and the registry
authentication gate. Its inventory verification does not mean apply readiness.

**No backup, image layer pull, container recreation, API-key installation,
registry credential installation, automatic rollout or provider inference was
performed.** Next: review the concrete base-profile rollout, authorize registry
download, then recheck idleness/capacity and take the consistent backup before
apply. The running service and public SpecGraph.space application are unchanged.
