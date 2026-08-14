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

## Jenkins credentials

Three sets, all **Global** scope. The id must match `registry.yml` exactly; it is case-sensitive.

| Id | Kind | Holds |
|---|---|---|
| `<host>_pw` | Username with password | the SSH login for that server |
| `nodered-<instance>-auth` | Username with password | that instance's `adminAuth` user and password |
| `nodered-<instance>-credsecret` | **Secret text** | that instance's `credentialSecret` — one value, no username |

**Host logins.** Ten, one per server. Eight already exist from the inherited pipeline; `wfm-svr-lin01_pw` and `dpn-svr-iot_pw` are new, because those two hosts were missing from the old map.

**Admin API logins.** Eleven, not thirteen: `slu-prod` and `slu-test` carry `app: null`, so the pipeline never deploys to them and never asks for their credential.

```
nodered-cho-prod-auth    nodered-jan-prod-auth    nodered-wag-prod-auth
nodered-cho-test-auth    nodered-jan-test-auth    nodered-wag-test-auth
nodered-gor-prod-auth    nodered-srem-prod-auth   nodered-wfm-auth
nodered-gor-test-auth    nodered-srem-test-auth
```

`nodered-wfm-auth` cannot be created usefully yet: `wfm` has `adminAuth` switched off. Jenkins fails on a credential id that does not exist, so switch `adminAuth` on first (decision 13), then create the credential with the same user and password.

The two FlowFuse servers need no credential at all yet, and neither does `pod-svr-lin01_pw` or `dpn-svr-iot_pw`. Those instances are not in `registry.yml` (decision 12), so the pipeline never resolves a credential for them. They enter after the migration, in this order: copy the flow, start the plain container, **unenroll the device**, retire the agent. Unenrolling last would let the agent overwrite the flow from the platform.

**Credential secrets.** Thirteen, created during the backup gate from the value each instance **already** has. No script reads them today — they are the copy of the key that lives off the server, and the key itself stays in `settings.js` on the host. A freshly invented value re-encrypts every stored credential into garbage.

## Flow deploy

```
python3 scripts/deploy.py --instance <name> --dry-run   # prints the normalized diff, exits 0
python3 scripts/deploy.py --instance <name>
```

Sequence and the `rev` handshake: [`architecture.md`](architecture.md).

### Reaching an instance from a workstation

The pipeline runs `deploy.py` on the target host, where every instance is at `http://<container-ip>:1880` and the script finds it through Docker. From a workstation there is no single answer, which is why decision 10 exists — but during bring-up it is useful, so set `NODE_RED_BASE_URL` to the **host only**. The script appends `admin_root` from `registry.yml`; passing the URL you have open in the browser doubles it.

| Instance | From a workstation |
|---|---|
| `wag-prod`, `wag-test` | `http://wag-svr-lin01` — nginx routes the admin root |
| `cho-prod` | `http://cho-svr-lin01:1880` |
| `cho-test` | `http://cho-svr-lin01:1881` |
| `gor-prod` | `http://gor-svr-lin01:1881` |
| `gor-test` | `http://gor-svr-lin01:1880` |
| `jan-prod` | `http://jan-svr-lin01:1880` |
| `jan-test` | `http://jan-svr-lin01:1881` |
| `slu-test` | `http://slu-svr-lin02:1882` |
| `wfm` | `http://wfm-svr-lin01:1880` |
| `srem-prod`, `srem-test`, `slu-prod` | no published port — run on the host |

On `gor` and `jan` the prod and test ports are the reverse of what the names suggest. The table is a snapshot; `collect-inventory.py` re-derives it, and only the host-side path is what the pipeline depends on.

To sweep several instances in one run, set the base per instance — `NODE_RED_BASE_URL_<INSTANCE>`, with `-` as `_` and upper-cased. A plain `NODE_RED_BASE_URL` still applies to anything without its own override:

```powershell
$env:NODE_RED_BASE_URL_WAG_PROD  = "http://wag-svr-lin01"
$env:NODE_RED_BASE_URL_WAG_TEST  = "http://wag-svr-lin01"
$env:NODE_RED_BASE_URL_CHO_PROD  = "http://cho-svr-lin01:1880"
$env:NODE_RED_BASE_URL_CHO_TEST  = "http://cho-svr-lin01:1881"
$env:NODE_RED_BASE_URL_GOR_PROD  = "http://gor-svr-lin01:1881"
$env:NODE_RED_BASE_URL_GOR_TEST  = "http://gor-svr-lin01:1880"
$env:NODE_RED_BASE_URL_JAN_PROD  = "http://jan-svr-lin01:1880"
$env:NODE_RED_BASE_URL_JAN_TEST  = "http://jan-svr-lin01:1881"
$env:NODE_RED_BASE_URL_WFM       = "http://wfm-svr-lin01:1880"

python3 scripts/drift-check.py --all --json inventory/drift.json
```

`srem-prod`, `srem-test` and `slu-prod` publish no port and will report as unreachable from a workstation. That is accurate, not a fault: reaching them means running on the host, which is what the pipeline does.

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

## Changing a flow

`scripts/nr.py` wraps everything below. It reads the instance list from `registry.yml`, so it cannot list an instance that does not exist or miss one that does.

```bash
python3 scripts/nr.py            # pick an instance, pick an action
python3 scripts/nr.py status     # every instance: does it still match Git?
python3 scripts/nr.py edit wag-prod
```

In VS Code the same actions are tasks — **Terminal → Run Task → Node-RED: …**. The dev container in `.devcontainer/` brings Python and the dependencies.

The editor is a second container, so the dev container needs to reach a container engine. `nr.py` probes for `docker compose`, `podman compose` and the standalone binaries; if none answers it prints the command to run from a host terminal instead. It also translates the workspace path — VS Code reports it as `c:\Users\...`, which podman under WSL cannot open, and the same directory is at `/mnt/c/Users/...` there.

Where each instance answers and the login for it go in a gitignored `nr.local.json`; copy `nr.local.example.json`. A password left out is asked for at the prompt and is not stored.

`nr.py deploy` is dry-run only, on purpose. A real deploy is a reviewed commit that Jenkins carries out; a local script that could write to production would make that path optional.

The commands underneath, if you want them directly:

Two routes. Which one is right depends on whether the instance may run the change while you make it.

### Route A — edit locally, then deploy

For a production flow, or a new flow. Nothing runs while you work.

```bash
python3 scripts/drift-check.py --instance wag-prod     # 1. confirm Git matches the instance
APP=wag-prod docker compose -f compose/editor.yml up    # 2. editor on http://localhost:1880
                                                        # 3. edit, press Deploy
python3 scripts/normalize.py --write apps/wag-prod/flows.json
git diff apps/wag-prod/flows.json                       # 4. review — it should be small
git commit -am "flows(wag-prod): ..." && git push        # 5.
```

Then in Jenkins: `INSTANCE=wag-prod`, `DRY_RUN=true` to see the diff the pipeline sees, then `DRY_RUN=false`.

Step 1 is not optional. If the instance has drifted, your local edit is against a stale base and the deploy will hit a `409`.

**The editor container cannot double your data.** That is the obvious hazard — a production flow with MQTT and Postgres nodes, opened in a second runtime that reaches the same broker, writes every row twice. `compose/editor.yml` blocks it three ways: no credentials (`flows_cred.json` never leaves its host), no name resolution (DNS points at a black hole), and safe mode so the flow loads without starting. The comments in that file explain the one residual case — a node with a literal IP against an anonymous broker.

### Route B — edit in the browser, then capture

For a test instance, or when the change has to run to be judged. The edit is live immediately, which is the point.

```bash
python3 scripts/capture.py --instance wag-test --dry-run   # see what would come back
python3 scripts/capture.py --instance wag-test             # write it into apps/wag-test/
git diff && git commit -am "flows(wag-test): ..." && git push
```

`capture.py` writes to the repository and never to an instance. It is also the recovery from a `409`.

### Adding a new flow to an instance that has one

There is no separate procedure. A flow file holds every tab of that instance, so a new flow is a new tab inside `apps/<app>/flows.json`. Use route A: add the tab in the local editor, deploy the whole file.

### Which route for which instance

| | Route |
|---|---|
| `*-prod` | A — the instance must not run a half-finished change |
| `*-test` | B is usually faster; A also works |
| a brand-new app | A — there is nothing running to conflict with |

Note that `*-prod` and `*-test` on one host are **different applications**, not two stages of one. You cannot develop on test and promote to prod. That is why route A exists.

## Drift check

```
python3 scripts/drift-check.py --all
python3 scripts/drift-check.py --instance gor-prod --show-diff
python3 scripts/drift-check.py --all --json inventory/drift.json --fail-on-drift
```

Read-only: `GET /flows`, normalize, diff against Git, report. It never writes to an instance and offers no flag that would.

Exit 0 when clean, 1 when an instance is unreachable, and 3 only with `--fail-on-drift` — for a scheduled check that should go red. Without the flag drift is reported and the exit stays 0, because drift is information, not a failure.

An unreachable instance does not stop the sweep; it is one row in the report. `--json` writes the full report, diffs included, which is what the visibility page renders (decision 11).
