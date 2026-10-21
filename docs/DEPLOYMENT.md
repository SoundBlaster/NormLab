# Local deployment with Docker Compose

For the prepared existing-VPS update, pinned image and backup/rollback sequence,
see [2026-10-21 checkpoints demo update](../deploy/releases/2026-10-21-checkpoints/README.md).
That package does not apply a production change or activate provider inference.

For the opt-in VPS provider adapters, exact secret paths, network boundaries and
activation gates, see [Hosted inference](HOSTED_INFERENCE.md). The production
entrypoint defaults to inference disabled; the ordinary local Compose profile
does not mount provider keys or start the gateway/egress services.

## Protected reverse-proxy route

The image can be built for a URL prefix such as `/normlab/`:

```sh
docker build --build-arg VITE_BASE_PATH=/normlab/ -t normlab:staging .
```

Configure the public proxy to strip `/normlab` from upstream request paths and
forward the remaining requests to the NormLab container on port `4317`. It must
preserve the incoming `Host` and `Origin` headers. The container must remain on
the private Compose network; do not publish its port on the host.

Enable the single-operator Basic Auth boundary in the NormLab service:

```text
NORMLAB_OPERATOR_AUTH_ENABLED=true
NORMLAB_OPERATOR_AUTH_USERNAME=operator
NORMLAB_OPERATOR_AUTH_PASSWORD=<injected runtime secret>
NORMLAB_PUBLIC_ORIGIN=https://specgraph.space
```

For file-backed secrets, set `NORMLAB_OPERATOR_AUTH_PASSWORD_FILE` to a
readable server-side path instead of setting the password environment variable.
When both are present, the file takes precedence.

Set the password in the host's runtime secret store, not in Git or the browser
bundle. When authentication is enabled, the server refuses to start without an
HTTPS public origin and both credentials. It protects static pages and every
API route; `/health` returns only `{ "ok": true }` for container health checks.
POST requests also require the exact configured Origin. This is a bounded
single-operator staging boundary, not multi-user account management.

`NORMLAB_VITE_BASE_PATH` configures the local Compose build and defaults to `/`.
For the staging image, use `/normlab/` as the build argument. The reverse proxy
must strip the route prefix before forwarding, so the Node server continues to
see its existing root-level `/api/...` endpoints.

Compose runs the production UI and API with the exact Lean toolchain from `lean-toolchain`. It publishes the service only on host loopback and stores SQLite state and the local receipt signing key in the named `normlab_normlab-data` volume by default. Containerized Lean checks default to a bounded 1024 MiB memory budget because the exhaustive A/B proof exceeds the native verifier's default 512 MiB limit on Linux ARM64. Override with `NORMLAB_LEAN_MEMORY_MB` from 512 to 4096 if needed; invalid values fall back to 512 MiB.

## Start

Requirements: Docker Desktop or another Docker Engine with the Compose plugin.

```sh
docker compose up --build -d
docker compose ps
```

Open <http://127.0.0.1:4317>. The initial build downloads the pinned Lean toolchain and can take several minutes. To use another local port, set the same port for the host and container with `NORMLAB_PORT=4318 docker compose up --build -d`; open <http://127.0.0.1:4318>.

The service has no default login and is intended for one local researcher. The published port is bound to `127.0.0.1`; do not change that binding when using untrusted networks. The `HOST=0.0.0.0` setting is needed inside the container, while Compose limits access on the host. Do not place real case data or personally identifying information in this synthetic research demo.

## Stop and retain data

```sh
docker compose stop
docker compose start
```

Or remove the container and network while retaining the named data volume:

```sh
docker compose down
docker compose up -d
```

`docker compose down -v` deletes the SQLite database and receipt signing key. Use it only when intentionally resetting the local installation. Losing the key changes issuer identity; keep a protected backup if signed local history must remain verifiable.

## Backup and restore

SQLite runs in WAL mode. Stop the service before making a file-level copy so the database and its WAL are captured consistently. The archive includes both signing keys; protect it as secret material.

```sh
mkdir -p backups
docker compose stop
docker run --rm --user 0:0 \
  -v normlab_normlab-data:/data:ro \
  -v "$PWD/backups:/backup" \
  --entrypoint sh normlab-normlab \
  -c 'tar -czf /backup/normlab-data.tar.gz -C /data .'
docker compose start
```

Restore into a new volume first, then run it side by side for verification. This leaves the existing installation intact:

```sh
docker volume create normlab-restore
docker run --rm --user 0:0 \
  -v normlab-restore:/data \
  -v "$PWD/backups/normlab-data.tar.gz:/backup/normlab-data.tar.gz:ro" \
  --entrypoint sh normlab-normlab \
  -c 'tar -xzf /backup/normlab-data.tar.gz -C /data'
NORMLAB_DATA_VOLUME=normlab-restore NORMLAB_PORT=4320 \
  docker compose -p normlab-restore up -d
```

Open <http://127.0.0.1:4320> and check the imported history:

```sh
curl --fail http://127.0.0.1:4320/api/reform/imports
NORMLAB_DATA_VOLUME=normlab-restore NORMLAB_PORT=4320 \
  docker compose -p normlab-restore exec -T normlab \
  node --input-type=module -e 'import {DatabaseSync} from "node:sqlite"; const db=new DatabaseSync("/var/lib/normlab/normlab.sqlite",{readOnly:true}); console.log(db.prepare("PRAGMA integrity_check").get()); console.log(db.prepare("PRAGMA foreign_key_check").all()); db.close();'
```

After verification, remove only the temporary restore copy:

```sh
NORMLAB_DATA_VOLUME=normlab-restore NORMLAB_PORT=4320 \
  docker compose -p normlab-restore down
docker volume rm normlab-restore
```

Keep the backup archive until verification succeeds. Legacy and A/B/C tables now have separate versioned entries in `normlab_schema_migrations`; migration 1 safely adopts the existing unversioned schema and is idempotent. The generic migration engine's forward upgrade, atomic rollback, retry and idempotence are covered with synthetic versions in [`tests/database-migrations.test.ts`](../tests/database-migrations.test.ts). The application has no later schema version yet, so this does not prove a future application-specific schema upgrade; add migration-specific data-preservation and rollback coverage with that migration.

Inspect logs with `docker compose logs --follow normlab`. `docker compose ps` reports the HTTP health check. Compose is a single-user local deployment, not a hardened multi-user or internet-facing production service.
