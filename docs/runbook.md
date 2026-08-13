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

## The one settings.js edit

Every change to `settings.js` restarts the container. Three changes are pending — the `credentialSecret` pin, and on two instances a deviation to normalize — so they are made in one edit and one restart per instance, after the backup gate.

**1. Read the generated key.** It is the only copy.

```bash
ssh <host> "sudo cat /path/to/<instance>/data/.config.runtime.json"
```

Store the `_credentialSecret` value in a Jenkins credential and record the id as `credential_secret_id` in `registry.yml`. Never echo it into a log, a pipeline output, or a commit.

**2. Edit `settings.js`.** For every instance:

```js
credentialSecret: "<the value from step 1>",
```

Pinning to the **existing** value means no re-encryption. A new value makes every stored credential unreadable.

On `cho-prod` additionally, bringing it back to what the other twelve do (decision 13):

```js
level: "info",     // was "trace"
```

On `wfm` additionally, uncomment the `adminAuth` block. Generate the hash inside the container so the password never reaches the shell history — type it, then Ctrl-D:

```bash
ssh wfm-svr-lin01
docker exec -i node-red node -e 'const b=require("bcryptjs");let d="";process.stdin.on("data",c=>d+=c).on("end",()=>console.log(b.hashSync(d.trim(),8)))'
```

If `bcryptjs` does not resolve in that image, `docker exec -it node-red npx node-red-admin hash-pw` does the same and prompts for the password. Put the username and password into a Jenkins credential and record the id as `auth_credential_id`.

**3. Restart, service-scoped.**

```bash
docker compose -f <compose_file> up -d <compose_service>
```

The compose file and service name differ per host; both are in `registry.yml`.

**4. Verify.** Open the editor and confirm a stored credential still decrypts. On `wfm`, confirm the login prompt appears and that `curl -s -o /dev/null -w '%{http_code}' http://<ip>:1880/flows` now returns `401` rather than `200`.

## Compose split

The compose file differs per host — `code/node-red/`, `energy/`, `Base_Container/`, `base_container/` — and the inventory's neighbour probe found no non-Node-RED service in any of those projects. If that holds, the split is already done and there is no work here.

It contradicts the earlier report that NATS shares `wag`'s file, so confirm before believing it:

```bash
ssh <host> "docker compose -f <compose_file> config --services"
```

Either way, every compose call names its service — `docker compose up -d <compose_service>`. That costs nothing and holds whichever answer comes back.

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
python3 scripts/drift-check.py --all
python3 scripts/drift-check.py --instance gor-prod --show-diff
python3 scripts/drift-check.py --all --json inventory/drift.json --fail-on-drift
```

Read-only: `GET /flows`, normalize, diff against Git, report. It never writes to an instance and offers no flag that would.

Exit 0 when clean, 1 when an instance is unreachable, and 3 only with `--fail-on-drift` — for a scheduled check that should go red. Without the flag drift is reported and the exit stays 0, because drift is information, not a failure.

An unreachable instance does not stop the sweep; it is one row in the report. `--json` writes the full report, diffs included, which is what the visibility page renders (decision 11).
