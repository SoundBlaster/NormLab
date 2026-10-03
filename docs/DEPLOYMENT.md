# Local deployment with Docker Compose

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

Keep the backup archive until verification succeeds. Legacy and A/B/C tables now have separate versioned entries in `normlab_schema_migrations`; migration 1 safely adopts the existing unversioned schema and is idempotent. This does not claim upgrade coverage for a future schema version until that migration and its rollback/recovery path are tested.

Inspect logs with `docker compose logs --follow normlab`. `docker compose ps` reports the HTTP health check. Compose is a single-user local deployment, not a hardened multi-user or internet-facing production service.
