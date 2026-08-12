# Runbook

Operational procedures. Constraints and reasoning: [`decisions.md`](decisions.md).

## Backup gate — before any automation touches a container

`credentialSecret` is unset on every inventoried instance, so Node-RED generated a random key and stored the only copy in `/data/.config.runtime.json`. `flows_cred.json` is worthless without it. Losing that file loses every stored credential, irreversibly.

Run from the **host**, against the bind mount, with plain file copies. Not `docker exec` — the point is to capture the files independently of a running container.

Per instance, tar together:

- `flows.json`
- `flows_cred.json`
- `.config.runtime.json`
- `settings.js`
- `package.json`

Then pull the tarballs off the box before anything else happens.

## Pinning credentialSecret

Only after the backup gate, and only to the **existing** generated value. Same key means no re-encryption; a new key means every stored credential is unreadable.

1. Read the generated key from `/data/.config.runtime.json` on the host.
2. Store it in a Jenkins credential; record the id as `credential_secret_id` in `registry.yml`.
3. Set `credentialSecret` explicitly in `settings.js` to that value.
4. Restart the instance, service-scoped.
5. Open the editor and confirm a stored credential still decrypts.

Never echo the value into a log, a pipeline output, or a commit.

## Compose split (~1h)

The Node-RED services currently live in `/home/administrator/base_container/docker-compose.yml` alongside NATS and others. Move them into their own compose project so image-tag pinning and recreates cannot touch a neighbouring service.

Until that lands, every compose call names its service: `docker compose up -d node-red-prod`. A bare `docker compose up -d` recreates NATS.

## Flow deploy

```
python scripts/deploy.py --instance <name> --dry-run   # prints the normalized diff, exits 0
python scripts/deploy.py --instance <name>
```

Sequence and the `rev` handshake: [`architecture.md`](architecture.md).

**On `409`:** the running flow diverged from Git. Someone edited in the browser. Recover the edit rather than discarding it:

1. `GET <admin_root>/flows` and save the running flow.
2. Run it through `scripts/normalize.py`.
3. Diff against the committed `flows.json`.
4. Commit it, or discard it deliberately.
5. Deploy again.

## Palette change

1. Edit `apps/<app>/package.json`.
2. Commit — GitLab CI builds and signs a new image.
3. Update `image_tag` in `registry.yml` to the new exact tag.
4. Jenkins recreates that one service. This restarts the container; the ingest gap is expected here.

## Local editor container

A Node-RED container mounting `apps/<app>/` as `/data`. The editor writes into the working tree, so the manual copy step from browser to repo disappears.

Build this early — it pays off before any pipeline exists, and it is what makes editor-valid committed flows (decision 6) practically true rather than aspirational.

## Drift check

```
python scripts/drift-check.py
```

Read-only sweep across all instances: `GET /flows`, normalize, diff against Git, report. It never writes.
