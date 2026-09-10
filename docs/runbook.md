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

On `wfm-prod` additionally, uncomment the `adminAuth` block (and on the new `wfm-test`, set it up from the start). Generate the hash inside the container so the password never reaches the shell history — type it, then Ctrl-D:

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

**4. Verify.** Open the editor and confirm a stored credential still decrypts. On `wfm-prod`, confirm the login prompt appears and that `curl -s -o /dev/null -w '%{http_code}' http://<ip>:1880/flows` now returns `401` rather than `200`.

## A new instance's /data must belong to the container user

The compose services run as `1004:1004`, so the bind-mounted directory has to
be owned by that uid before the container starts — and setting a foreign owner
needs root:

```bash
sudo mkdir -p /home/administrator/Base_Container/<service>/data
sudo chown -R 1004:1004 /home/administrator/Base_Container/<service>/data
ls -ldn /home/administrator/Base_Container/<service>/data   # must read 1004 1004
```

Without it the runtime starts and serves reads, so it looks healthy, and then
dies the first time it writes. On `wfm-test` that was the token endpoint
persisting a session:

```
[warn] Flushing file /data/.sessions.json.$$$ to disk failed : EACCES
[red] Uncaught Exception:
```

`restart: always` brings it straight back, so the symptom at the other end is a
connection accepted and dropped without an HTTP response, not a permission
error. `Creating new flow file` on every start is the other tell: the flow file
cannot be written either, so no deploy would ever have persisted.

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

**Admin API logins.** Twelve, not fourteen: `slu-prod` and `slu-test` carry `app: null`, so the pipeline never deploys to them and never asks for their credential.

```
nodered-cho-prod-auth    nodered-jan-prod-auth    nodered-wag-prod-auth
nodered-cho-test-auth    nodered-jan-test-auth    nodered-wag-test-auth
nodered-gor-prod-auth    nodered-srem-prod-auth   nodered-wfm-prod-auth
nodered-gor-test-auth    nodered-srem-test-auth   nodered-wfm-test-auth
```

`nodered-wfm-prod-auth` cannot be created usefully yet: `wfm-prod` has `adminAuth` switched off. Jenkins fails on a credential id that does not exist — that is how the first fleet-wide run died — so switch `adminAuth` on first (decision 13), then create the credential with the same user and password. `wfm-test` is new, so its `adminAuth` is set up from the start and its credential can be created straight away.

The two FlowFuse servers need no credential at all yet, and neither does `pod-svr-lin01_pw` or `dpn-svr-iot_pw`. Those instances are not in `registry.yml` (decision 12), so the pipeline never resolves a credential for them. They enter after the migration, in this order: copy the flow, start the plain container, **unenroll the device**, retire the agent. Unenrolling last would let the agent overwrite the flow from the platform.

**Credential secrets.** Fourteen, created during the backup gate from the value each instance **already** has — except `wfm-test`, which is new, so its value is generated once rather than pinned. No script reads them today — they are the copy of the key that lives off the server, and the key itself stays in `settings.js` on the host. A freshly invented value re-encrypts every stored credential into garbage.

## Flow deploy

```
python3 scripts/deploy.py --instance <name> --dry-run              # prints the diff and the rev
python3 scripts/deploy.py --instance <name> --expect-rev <rev>     # writes only if it still holds
```

Sequence and the `rev` handshake: [`architecture.md`](architecture.md).

**Take the rev from the dry run into the deploy.** It is what makes the conflict abort reachable: a deploy without it reads the current rev and posts against it moments later, so a browser edit made before the run is inside that rev and gets flattened. With it, anything that changed the instance between the review and the write stops the write. In Jenkins the parameter is `EXPECT_REV`, and it belongs to one instance — a fleet run cannot pin it.

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
| `wfm-prod` | `http://wfm-svr-lin01:1880` |
| `wfm-test` | `http://wfm-svr-lin01:1881` |
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
$env:NODE_RED_BASE_URL_WFM_PROD  = "http://wfm-svr-lin01:1880"
$env:NODE_RED_BASE_URL_WFM_TEST  = "http://wfm-svr-lin01:1881"

python3 scripts/drift-check.py --all --json inventory/drift.json
```

`srem-prod`, `srem-test` and `slu-prod` publish no port and will report as unreachable from a workstation. That is accurate, not a fault: reaching them means running on the host, which is what the pipeline does.

**If every instance reports unreachable from a workstation, suspect a proxy first.** `urllib` honours `http_proxy` and `https_proxy`, so a corporate proxy takes the request for an internal host and usually closes it without an HTTP response — which reads as a connection reset rather than as a refusal. Put the site domain in `no_proxy`:

```powershell
$env:NO_PROXY = "polipol.intra,polipol-service.de,10.0.0.0/8,192.168.0.0/16"
```

A refused connection means the opposite: nothing is listening, so the instance or its port is the thing to check.

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

In VS Code the same actions are tasks — **Terminal → Run Task → Node-RED: …**. The dev container in `.devcontainer/` brings Python, the dependencies and access to Docker for the editor container.

Where each instance answers and the login for it go in a gitignored `nr.local.json`; copy `nr.local.example.json`. A password left out is asked for at the prompt and is not stored.

`nr.py deploy` is dry-run only, on purpose. A real deploy is a reviewed commit that Jenkins carries out; a local script that could write to production would make that path optional.

The commands underneath, if you want them directly:

Two routes. Which one is right depends on whether the instance may run the change while you make it.

### Route A — edit locally, then deploy

For a production flow, or a new flow. Nothing runs while you work.

```bash
python3 scripts/drift-check.py --instance wag-prod     # 1. confirm Git matches the instance
python3 scripts/nr.py edit wag-prod                     # 2. editor on http://localhost:1880
                                                        # 3. edit, press Deploy
python3 scripts/normalize.py --write apps/wag-prod/flows.json
git diff apps/wag-prod/flows.json                       # 4. review — it should be small
git commit -am "flows(wag-prod): ..." && git push        # 5.
```

Then in Jenkins: `INSTANCE=wag-prod`, `DRY_RUN=true` to see the diff the pipeline sees, then `DRY_RUN=false`.

Step 1 is not optional. If the instance has drifted, your local edit is against a stale base and the deploy will hit a `409`.

Prefer `nr.py edit` over the bare compose call: it pins the editor to the Node-RED version that instance runs, which a plain `APP=... docker compose up` does not, and it finds the container engine — podman on a workstation, Docker on a server, or whatever `CONTAINER_ENGINE` names. A 5.x editor writes fields into the flow that a 4.0.x runtime does not know, in a file whose whole purpose is to deploy unchanged. For a flow that uses palette nodes, add `--baked` so the editor runs that app's own image and those nodes open as themselves instead of as "unknown" — that pulls from Harbor and needs a login there.

**The editor arrives with every tab disabled.** That is the protection, and it
replaces one that did not hold: most nodes here carry no credentials and several
address their target by literal IP, so "it cannot authenticate" and "it cannot
resolve" protect nothing, and safe mode ends at the first Deploy — which is how
the editor saves your work. So `nr.py edit` stages the flow into
`.editor-session/<app>/` with the tabs switched off and mounts that, never
`apps/<app>/`. Enable the tab you are working on, or add one; only that runs,
and it runs for real against real systems, which is the deliberate act rather
than the accident. On Ctrl-C the flow is copied back with each existing tab's
disabled state restored from Git, so local switching never reaches a commit.

For a flow you do not know, `--isolated` puts the editor on a network with no
gateway: nothing outside the container is reachable, Deploy or no Deploy.

**The editor container cannot double your data.** That is the obvious hazard — a production flow with MQTT and OPC UA nodes, opened in a second runtime that reaches the same broker, acts twice. The disabled tabs are what stop it, with safe mode covering the window before the first Deploy and `--isolated` available when even that is too much. What remains: a config node may open a connection while its own nodes are disabled — a connect without traffic — and an exec node runs inside the container. `compose/editor.yml` spells this out, including how to verify the isolated mode in your own engine, because some compose providers ignore the flag.

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

### Promoting a change between a workbench and prod

A `*-test` instance is a workbench, empty by default (decision 15). These are
the two loops, and both end with a deploy of **both** instances.

**Changing a tab that prod already runs**

```bash
python3 scripts/nr.py check wfm-prod                                  # 1. is prod still Git's?
python3 scripts/nr.py promote wfm-prod wfm-test "Extruder abfrage" --copy
git commit -am "promote(wfm-test): bring Extruder abfrage onto the workbench"
python3 scripts/nr.py edit wfm-test                                   # 2. build it
git commit -am "flows(wfm-test): ..."                                 #    then deploy wfm-test
                                                                      # 3. try it on the instance
python3 scripts/nr.py promote wfm-test wfm-prod "Extruder abfrage" --move
git commit -am "promote(wfm-prod): ship Extruder abfrage"
                                                                      # 4. deploy wfm-test, then wfm-prod
```

Step 1 is not decoration: promoting from a prod that has drifted puts a stale
tab on the workbench, and the browser edit it hides surfaces as a `409` at the
end instead of as a `capture` at the start.

**A tab that does not exist yet** skips the first promotion — build it on the
workbench, deploy there, then `--move` it to prod.

**`--copy` and `--move` are not interchangeable, and there is no default.**
`--copy` for prod → workbench, because prod has to keep running the tab while
you change it. `--move` for workbench → prod, because a tab left enabled on the
workbench runs alongside prod: two runtimes on the same PLC and the same topic,
and the only symptom is data arriving twice.

**The arriving state follows the direction.** A `--copy` lands **disabled** on
the workbench, so nothing starts by itself and becomes a second publisher on a
live topic; enable it there when you want it to run. A `--move` lands
**enabled** in prod, because that is where it is meant to run — and if prod had
that tab disabled before, the report says so, since re-enabling it silently
would be a change nobody asked for.

Enabling on the workbench is a change to that instance, so it shows up as
drift until someone captures it. That is correct: the workbench's own state is
its own business, and the tab you ship is the one you validated.

**Deploy order for a `--move`: the source first.** The tab stops on the
workbench before it starts in prod, so the two never overlap. For a changed tab
prod serves the old version until the new one lands.

**Read the report.** Where the destination lacks a config node the tab needs, it
is created with the *source's* values and named in the output. That is the one
manual gate in the loop: set it for its own instance before deploying, or the
workbench publishes into prod's broker. An existing config node is never
overwritten, which is how each side keeps its own broker across promotions.

**The workbench must not write outward.** Reading an OPC UA server twice is
tolerable; publishing twice is not. Repoint the workbench's `mqtt out` target —
in `apps/<app>-test/flows.json`, where it stays, because promotion leaves
destination config nodes alone.

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
