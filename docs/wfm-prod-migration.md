# Bringing `wfm-prod` onto the pipeline

`wfm-svr-lin01` ran one Node-RED before this project: the `node-red` service in
`/home/administrator/Base_Container/docker-compose.yml`, on a floating
`nodered/node-red:latest`, with `adminAuth` switched off. It is now
`wfm-prod` in `registry.yml`, and `wfm-test` was added beside it as the
workbench. This is the sequence that puts the old instance under the pipeline
and then proves both change loops against it.

It is also the pattern for the other eleven — the phases are the same
everywhere, only the numbers below change.

## What the instance is

Measured, not assumed. If any of this no longer matches, stop and re-inventory
rather than working around it.

| | |
|---|---|
| host / service | `wfm-svr-lin01` / `node-red`, publishes `1880` |
| flow in Git | `apps/wfm-prod/flows.json`, **19 nodes**, 2 tabs |
| tab `Extruder abfrage` | `inject` every **5 s**, `once: true` → OPC UA read → `function` → **`mqtt out` to `dpn-svr-iot:8883`** |
| tab `Flow 1` | manual `inject` → OPC UA browse and read → `debug` only, no outward write |
| config nodes | 3 × `OpcUa-Endpoint` (one with `login: true`), `mqtt-broker`, `tls-config` |
| `adminAuth` | **off** — `//adminAuth: {` is still commented out, and `GET /flows` on the container answers `200` unauthenticated. Anyone who reaches the host on 1880 can read and write the flow |
| `httpAdminRoot` | commented out, so the runtime serves at `/`. `admin_root: ""`. nginx serves it as `http://wfm-svr-lin01/node-red-prod` and strips that prefix |
| `credentialSecret` | unset, so Node-RED generated one; the only copy is `/data/.config.runtime.json` |
| target image | `harbor.aks-infra.polipol-service.de/dap-node-red/wfm-prod:4.0.9-1` — same Node-RED version it already runs, with `node-red-contrib-opcua ~0.2.339` baked in |

Two consequences worth reading twice:

- **One OPC UA endpoint has a stored login.** It lives in `flows_cred.json`,
  encrypted with the generated key. Pin that exact key or the credential is
  gone, and Node-RED reports it as one line in the log rather than as a failure.
- **`Extruder abfrage` publishes every 5 seconds.** It is the tab that must
  never run in two places at once, which is why the change test below uses
  `Flow 1` instead.

## Phase A — read only

Nothing here changes the instance.

**A1. Does the running flow still match Git?** `wfm-prod` was never reached in
the fleet dry run — the Jenkins credential did not exist yet — so this is the
first look. It works from a workstation today precisely because `adminAuth` is
still off:

```powershell
$env:NODE_RED_BASE_URL_WFM_PROD = "http://wfm-svr-lin01:1880"
python3 scripts/nr.py check wfm-prod
```

Expect the `clean` row with `19 nodes, rev …`. Anything else is a browser edit that predates this
project: capture and commit it before going on, or discard it deliberately
(`runbook.md`, "On 409"). Do not continue with an unexplained diff — the whole
migration assumes Git is right.

**A2. Backup gate.** `runbook.md`, "Backup gate". From the host, plain file
copies against the bind mount, then pull the tarball off the box:

```bash
ssh wfm-svr-lin01
cd /home/administrator/Base_Container
sudo tar czf ~/wfm-prod-pre-pipeline.tgz \
    node-red/data/flows.json node-red/data/flows_cred.json \
    node-red/data/.config.runtime.json node-red/data/settings.js \
    node-red/data/package.json
```

**A3. Read the generated key.** It is the only copy, and step B2 pins it:

```bash
sudo cat /home/administrator/Base_Container/node-red/data/.config.runtime.json
```

Put the `_credentialSecret` value into the Jenkins credential
`nodered-wfm-prod-credsecret`. Never into a log, a commit, or a chat.

## Phase B — one edit, one restart

`settings.js` and the image change together, because each of them restarts the
container and there is no reason to do that twice. Expect an ingest gap for the
length of the restart.

**B1. Generate the admin password hash** inside the container, so it never
reaches the shell history — type the password, then Ctrl-D:

```bash
docker exec -i node-red node -e 'const b=require("bcryptjs");let d="";process.stdin.on("data",c=>d+=c).on("end",()=>console.log(b.hashSync(d.trim(),8)))'
```

Put the username and that password into the Jenkins credential
`nodered-wfm-prod-auth`.

**B2. Edit `/home/administrator/Base_Container/node-red/data/settings.js`:**

```js
credentialSecret: "<the value from A3>",   // pin the existing key, do not invent one
adminAuth: {
    type: "credentials",
    users: [{ username: "<user>", password: "<hash from B1>", permissions: "*" }]
},
```

A *new* `credentialSecret` value makes the stored OPC UA login unreadable. Pin
the existing one.

**B2a. Decide the proxy path, and change it in the same edit.** nginx on this
host has

```nginx
location /node-red-prod {
    set $upstream http://node-red-prod:1880;
    #rewrite ^/node-red-prod/(.*)$ /$1 break;
```

Two things are wrong with that for this instance. The upstream name is
`node-red-prod`, and the container here is called `node-red` — the pair
`node-red-prod` / `node-red-test` is the naming on the other hosts, and this
block was written for them. And with the rewrite commented out, nginx passes
`/node-red-prod/...` through unchanged, to a runtime whose `httpAdminRoot` is
commented out and which therefore serves at `/`. Whatever answers on that path
today is not this container: it answered `401`, and this container answers
`200` without a login.

**So resolve the name before anything else** — a wrong upstream that reaches
*some* Node-RED is worse than one that reaches none:

```bash
docker exec <nginx-container> getent hosts node-red-prod node-red node-red-test
```

Docker's embedded resolver forwards what it cannot answer to the host's DNS,
and this host carries `dns_search: rah.polipol.intra, wag.polipol.intra`. A
name that is not a local container can therefore resolve to a Node-RED on a
different server — one that does serve `/node-red-prod` and does have
`adminAuth`, which is exactly what a `401` looks like.

Then pick one of two end states, and move `settings.js` and `registry.yml`
together:

| | `settings.js` | nginx | `admin_root` |
|---|---|---|---|
| **A: serve the path** (recommended) | uncomment `httpAdminRoot: '/node-red-prod'` | upstream `node-red`, rewrite stays off | `/node-red-prod` |
| B: strip it at the proxy | leave the root at `/` | upstream `node-red`, uncomment the rewrite | `""` |

A is what the other eight instances already do, what `wfm-test` does, and what
Node-RED itself recommends: the editor builds its asset and websocket URLs from
`httpAdminRoot`, so a prefix stripped by the proxy leaves the browser asking
for `/` and the editor half-loads. B works for the API and is the fragile one.

Either way the two values are one change: `admin_root` is what the runtime
serves, so flipping `settings.js` without `registry.yml` — or the reverse —
gives every Jenkins run a `404`. `registry.yml` currently holds `""`, which is
what the runtime serves *today*.

**B3. Switch the service to the exact tag** in
`/home/administrator/Base_Container/docker-compose.yml`, replacing the floating
`nodered/node-red:latest` on the `node-red` service only:

```yaml
    image: harbor.aks-infra.polipol-service.de/dap-node-red/wfm-prod:4.0.9-1
```

**B4. Pull and recreate, service-scoped:**

```bash
docker login harbor.aks-infra.polipol-service.de
docker compose -f /home/administrator/Base_Container/docker-compose.yml pull node-red
docker compose -f /home/administrator/Base_Container/docker-compose.yml up -d node-red
```

Naming the service matters: the same compose file holds NATS and the new
`node-red-test`.

**B5. Verify, in this order:**

```bash
docker logs node-red --tail 40                      # no "Failed to decrypt credentials"
curl -s -o /dev/null -w '%{http_code}\n' http://<container-ip>:1880/flows   # expect 401, was 200
docker exec node-red sh -c 'ls -d /data/node_modules/* 2>/dev/null'         # what /data still carries
```

Then in the editor: the login prompt appears, **19 nodes across 2 tabs** are
there, and the OPC UA endpoint with the stored login still connects. A silently
emptied credential is the one failure mode of this phase.

If `/data/node_modules` holds its own copy of `node-red-contrib-opcua`, that
copy wins over the baked one — the user directory takes precedence. Same
version is harmless; a different version means the image is not the palette
truth for this instance. Move it aside only with the backup from A2 in hand.

## Phase C — the pipeline's first look at prod

**Phase B is not optional for this instance, and not for the reason it looks
like.** The Jenkins credential `nodered-wfm-prod-auth` already exists, so
`deploy.py` finds a login in its environment and calls `POST /auth/token` on
every run — and while `adminAuth` is commented out, Node-RED does not serve
that route, so every run 404s no matter what `admin_root` says. The instance
cannot be deployed until its `adminAuth` is on. Decision 13 asked for that
anyway; this only fixes the order.

Jenkins, `INSTANCE=wfm-prod`, `DRY_RUN=true`, `EXPECT_REV` empty.

Expect `already up to date (19 nodes)`. This one run proves four things at
once: the host map reaches `wfm-svr-lin01`, both Jenkins credentials resolve,
`admin_root: ""` is right for this instance, and the token call works now that
`adminAuth` is on.

`admin_root` for this instance is `""`, and the browser URL is the reason to
double-check that rather than to change it: nginx on `wfm-svr-lin01` serves the
editor as `http://wfm-svr-lin01/node-red-prod` and strips that prefix before
the container sees it. The deploy talks to the container. Setting `admin_root`
to `/node-red-prod` because the browser and a workstation `curl` use it makes
every call 404 — `runbook.md`, "Flow deploy", has the no-password probe that
settles it.

Do not run `DRY_RUN=false` yet. There is nothing to write, and the write path
gets proven by the two tests below, where there is something to see.

## Phase D — test 1: change a tab prod already runs

Use **`Flow 1`**, not `Extruder abfrage`: `Flow 1` reads OPC UA and writes to
`debug`, so running it briefly in two places costs nothing. `Extruder abfrage`
publishes to `dpn-svr-iot:8883` every 5 seconds, and two publishers on one
topic is exactly the fault the promotion rules exist to prevent.

```bash
python3 scripts/nr.py check wfm-prod                                    # 1. still clean
python3 scripts/nr.py promote wfm-prod wfm-test "Flow 1" --copy         # 2. arrives DISABLED
git commit -am "promote(wfm-test): bring Flow 1 onto the workbench" && git push
python3 scripts/nr.py edit wfm-test                                     # 3. enable Flow 1, change it
python3 scripts/normalize.py --write apps/wfm-test/flows.json
git diff apps/wfm-test/flows.json
git commit -am "flows(wfm-test): ..." && git push
```

`promote` will report the `OpcUa-Endpoint` config nodes it had to create on the
workbench, carrying prod's endpoint addresses. Reading the same server twice is
tolerable, so they can stay as they are — but read the report rather than
assuming that.

Deploy `wfm-test` (two runs, `EXPECT_REV` from the dry run), try the change,
then:

```bash
python3 scripts/nr.py promote wfm-test wfm-prod "Flow 1" --move
git commit -am "promote(wfm-prod): ship the changed Flow 1" && git push
```

Deploy **`wfm-test` first, then `wfm-prod`** — each with its own two runs and
its own `EXPECT_REV`. After the prod deploy: still 19 nodes, and the change is
in the editor.

## Phase E — test 2: a new tab

No first promotion — there is nothing in prod to copy.

```bash
python3 scripts/nr.py edit wfm-test          # add a tab; keep it read-only or self-contained
python3 scripts/normalize.py --write apps/wfm-test/flows.json
git commit -am "flows(wfm-test): add <tab>" && git push
```

Deploy `wfm-test`, try it, then:

```bash
python3 scripts/nr.py promote wfm-test wfm-prod "<tab>" --move
git commit -am "promote(wfm-prod): ship <tab>" && git push
```

Deploy `wfm-test`, then `wfm-prod`. Prod ends at **19 + 1 tab node + the nodes
on it** — count before and after, because a count that moves by more than the
tab is the tell that the promotion brought something along.

## If it goes wrong

The restart is the only irreversible-feeling step, and it is not irreversible:

```bash
docker compose -f /home/administrator/Base_Container/docker-compose.yml stop node-red
sudo tar xzf ~/wfm-prod-pre-pipeline.tgz -C /home/administrator/Base_Container
# put the image line back to what it was, then:
docker compose -f /home/administrator/Base_Container/docker-compose.yml up -d node-red
```

A failed deploy needs no rollback at all: `deploy.py` either writes the whole
flow or writes nothing, and with `EXPECT_REV` it refuses rather than writing
over something it was not shown.
