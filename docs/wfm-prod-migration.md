# Bringing `wfm-prod` onto the pipeline

`wfm-svr-lin01` carries **three** Node-RED runtimes:

| container | what it is | `adminAuth` | `httpAdminRoot` | reached by |
|---|---|---|---|---|
| `node-red` | the **old** instance. Runs the real flow: 19 nodes, OPC UA, MQTT | **off** — `GET /flows` answers `200` with no login | commented out, serves at `/` | `172.32.65.4:1880`, and nothing in nginx |
| `node-red-prod` | the **new** prod, still **empty** | on | `/node-red-prod` | `172.32.1.8:1880`, and `http://wfm-svr-lin01/node-red-prod` |
| `node-red-test` | the workbench, already on the pipeline | on | `/node-red-test` | `172.32.1.7:1880`, and `http://wfm-svr-lin01/node-red-test` |

So this is not an upgrade of one container. It is a **cutover**: the flow moves
from `node-red` to `node-red-prod`, the old container is retired, and the
naming matches the other nine hosts afterwards.

`registry.yml` still points `wfm-prod` at `compose_service: node-red` — the old
one — which is why the first Jenkins run reached a runtime with no `adminAuth`
and 404'd on the token call, while the same call through nginx succeeded
against the new one.

## The one thing that can go irreversibly wrong

**Git holds no credentials, and it must not.** `GET /flows` never returns them,
so `apps/wfm-prod/flows.json` has no `credentials` key anywhere — verified, the
count is zero. What the flow does contain is two things that only work *with*
credentials:

- an `OpcUa-Endpoint` with `login: true`
- a `tls-config` whose `ca`, `cert` and `key` are empty while `caname`,
  `certname` and `keyname` name `ca.crt`, `client.crt` and `client.key`. That
  shape means the PEM contents were uploaded into the node, so they live in
  `flows_cred.json` — and the `mqtt out` to `dpn-svr-iot:8883` needs them,
  with `verifyservercert: true`.

Deploying the flow to the empty `node-red-prod` therefore carries the logic and
**not** the client certificate or the OPC UA login. Both are in the old
container's `flows_cred.json`, encrypted with the key Node-RED generated for
*that* container and stored in its `/data/.config.runtime.json`. Copying one
without the other is worthless.

Phase B is where they move across. Skip it and the cutover looks successful and
publishes nothing.

## Phase A — read only

**A1 is done: `clean · 19 nodes`, 2026-09-10.** The old instance and Git agree,
which is what the rest of this document assumes. It was checked *before*
`registry.yml` was repointed, and that order is not incidental — `admin_root`
comes from the registry, so once it says `/node-red-prod` the old runtime,
which serves at `/`, can no longer be checked this way.

**A1. Is the old instance still what Git says?** It answers unauthenticated
today, which makes this the easy part:

```powershell
$env:NODE_RED_BASE_URL_WFM_PROD = "http://wfm-svr-lin01:1880"
python3 scripts/nr.py check wfm-prod
```

Use the **port**, not `http://wfm-svr-lin01/node-red-prod` — that path is the
new empty container. Expect the `clean` row with `19 nodes, rev …`. A diff here
is a browser edit that predates the project: capture and commit it, or discard
it deliberately (`runbook.md`, "On 409"). Everything below assumes Git is right.

**A2. Backup gate, on the old container's data.** `runbook.md`, "Backup gate".
This is the only copy of the credentials:

```bash
ssh wfm-svr-lin01
cd /home/administrator/Base_Container
sudo tar czf ~/wfm-prod-pre-cutover.tgz \
    node-red/data/flows.json node-red/data/flows_cred.json \
    node-red/data/.config.runtime.json node-red/data/settings.js \
    node-red/data/package.json
```

Pull the tarball off the box before anything else happens.

**A3. Read the old instance's generated key.** Phase B pins the new container
to it:

```bash
sudo cat /home/administrator/Base_Container/node-red/data/.config.runtime.json
```

Put the `_credentialSecret` value into the Jenkins credential
`nodered-wfm-prod-credsecret`. Never into a log, a commit, or a chat.

**A4. Learn what the new container actually is.** Four facts decide the rest,
and none of them are in this repository yet:

```bash
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}'
docker inspect node-red-prod --format 'image={{.Config.Image}}
compose={{index .Config.Labels "com.docker.compose.project.config_files"}}
mounts={{range .Mounts}}{{.Source}}->{{.Destination}} {{end}}
restart={{.HostConfig.RestartPolicy.Name}}'
docker inspect node-red --format 'compose={{index .Config.Labels "com.docker.compose.project.config_files"}} restart={{.HostConfig.RestartPolicy.Name}}'
docker exec node-red-prod grep -n 'credentialSecret' /data/settings.js
```

Measured on 2026-09-10:

| | |
|---|---|
| image | `harbor.aks-infra.polipol-service.de/dap-node-red/wfm-prod:4.0.9-1` — **already the pinned tag**, so phase B has no image work |
| compose file | `/home/administrator/Base_Container/docker-compose.yml` — the same file as the old container and as `node-red-test`, so `compose_file` in `registry.yml` does not change |
| data directory | `/home/administrator/Base_Container/node-red-prod/data` |
| `credentialSecret` | set explicitly in its `settings.js`, its own value. Phase B replaces it with the old instance's key |
| restart policy | `always` — **on both containers**, which is the phase D trap |

Two more things that same `docker ps` showed, and neither belongs on this host:

- **A stray container** running `dap-node-red/wfm-test:4.0.9-1` under a
  generated name, up 20 hours, from a bare `docker run` during the image test.
  It has no bind mount, so its `/data` is a fresh volume and its flow is empty
  — harmless today, and a Node-RED runtime nobody tracks, on a host that is
  being brought under exactly the opposite regime. Remove it:
  `docker rm -f <name>`.
- **`restart: always` on the old `node-red`.** `docker compose stop` survives a
  daemon restart, because an explicit stop is recorded — but any
  `docker compose up -d` on this file, for NATS or for the sdcs stack, starts
  it again. And that file holds all of them. So the service has to leave the
  compose file, not just be stopped.

## Phase B — carry the secrets across, then pin the image

One restart of `node-red-prod`. Nothing here touches the old container, so the
flow keeps running while you work.

**B1. Stop the new container** so nothing is holding its files:

```bash
docker compose -f /home/administrator/Base_Container/docker-compose.yml stop node-red-prod
```

**B2. Copy the credential file into the new data directory:**

```bash
sudo cp /home/administrator/Base_Container/node-red/data/flows_cred.json \
        /home/administrator/Base_Container/node-red-prod/data/flows_cred.json
sudo chown 1004:1004 /home/administrator/Base_Container/node-red-prod/data/flows_cred.json
```

The ownership is not optional — a file the container user cannot read fails the
same way an absent one does, and a directory it cannot write kills the runtime
on the first save (`runbook.md`, "A new instance's /data must belong to the
container user").

**B3. Two places hold a key, and both have to name the old one.**

- `settings.js` → `credentialSecret`: the key to use **from now on**.
- `/data/.config.runtime.json` → `_credentialSecret`: the key the
  `flows_cred.json` **on disk is actually encrypted with**. Node-RED writes it
  there itself when it generates one.

When the two differ, Node-RED reads with the runtime one and re-encrypts with
the settings one — that is how changing a `credentialSecret` is meant to work.
Which means setting only `settings.js` leaves it decrypting the file we copied
in B2 with a key that never encrypted it, and the result is the binary rubbish
in the diagnosis below.

The new container generated a key of its own on first start, so it has both.
Point both at the old instance's key, with the container stopped:

```bash
sudo python3 - <<'EOF'
import hashlib, json, pathlib, re
OLD = pathlib.Path('/home/administrator/Base_Container/node-red/data')
NEW = pathlib.Path('/home/administrator/Base_Container/node-red-prod/data')
fp = lambda v: hashlib.sha256(v.encode()).hexdigest()[:8]

key = json.loads((OLD / '.config.runtime.json').read_text())['_credentialSecret']

s = (NEW / 'settings.js').read_text()
s, n = re.subn(r'(credentialSecret:\s*")[^"]*(")', lambda m: m.group(1) + key + m.group(2), s, count=1)
assert n == 1, 'no active credentialSecret line in the new settings.js'
(NEW / 'settings.js').write_text(s)

rt_path = NEW / '.config.runtime.json'
rt = json.loads(rt_path.read_text()) if rt_path.exists() else {}
had = rt.get('_credentialSecret')
rt['_credentialSecret'] = key
rt_path.write_text(json.dumps(rt))

print('settings.js  ->', fp(key))
print('runtime json ->', fp(key), '(was ' + (fp(had) if had else 'absent') + ')')
EOF
sudo chown 1004:1004 /home/administrator/Base_Container/node-red-prod/data/.config.runtime.json
```

Both printed fingerprints have to equal the old instance's — the same eight
characters the diagnosis below computes. The key itself never reaches a screen,
a shell history or `ps`, which is why this is a script and not a paste: 64 hex
characters are unverifiable by eye, and the first attempt at this step failed
exactly there.

Setting both to the same value also means no re-encryption happens, so
`flows_cred.json` stays byte-for-byte the file B2 copied. The Jenkins
credential `nodered-wfm-prod-credsecret` holds that same key.

A mismatch does not error at startup. It logs one warning and carries on with
no credentials at all.

**B4. The image is already the pinned tag** — `wfm-prod:4.0.9-1`, which is the
`image_tag` `registry.yml` holds. Nothing to change, and no Harbor login
needed.

**B5. Start it and read the log:**

```bash
docker compose -f /home/administrator/Base_Container/docker-compose.yml up -d node-red-prod
docker logs node-red-prod --tail 40      # no "Failed to decrypt credentials"
```

What to look for is a fresh startup banner — `Welcome to Node-RED`,
`Node-RED version: v4.0.9`, `Settings file : /data/settings.js`, ending in
`Started flows` — and **no** `Error loading credentials` or `Failed to decrypt
credentials`. That line is the whole test of B2 and B3: a wrong key does not
fail the start, it logs once and carries on with nothing.

If the log ends at `Stopping flows` with nothing after it, the container is
still down — the `up -d` did not run, or `settings.js` has a syntax error from
the edit in B3, which shows as a container that exits instead of starting.
`docker ps --filter name=node-red-prod` says which.

The instance is still empty at this point, so the credentials it now holds
belong to no node yet. That is expected: the deploy in phase D brings the nodes
that claim them, matched by node id — which is why nothing in this repository
ever rewrites an id.

**Do not press Deploy in the empty editor between B5 and phase D.** Node-RED
drops credentials that belong to no node when it *saves*, so deploying an empty
flow is the one action that would discard what B2 just carried over. Keep the
window short and let the pipeline be the thing that writes.

### If the log says `Error loading credentials`

```
[warn] Error loading credentials: SyntaxError: Unexpected token '\ufffd', ... is not valid JSON
```

Binary rubbish where JSON should be means the decryption ran with the wrong
key: AES-CTR with a key that does not match produces random bytes, and the
JSON parse is what notices. It is not a corrupt file and not a Node-RED bug.

**Stop the container first.** With the credentials unreadable, Node-RED holds
none in memory, and the next thing that *saves* writes `flows_cred.json` back
out — encrypted with the wrong key, over the copy that B2 just made. The
original still exists in the old instance's `/data` and in the A2 tarball, so
this is recoverable, but only until it happens twice.

```bash
docker compose -f /home/administrator/Base_Container/docker-compose.yml stop node-red-prod
```

Then check the two things that can be wrong, without printing either secret.
A short SHA-256 prefix is enough to compare keys and reveals nothing:

```bash
# 1. did the copy survive, or has it already been rewritten?
sudo md5sum /home/administrator/Base_Container/node-red/data/flows_cred.json \
            /home/administrator/Base_Container/node-red-prod/data/flows_cred.json

# 2. which key does each side use?
docker exec node-red-prod node -e 'const s=require("/data/settings.js");const h=require("crypto").createHash("sha256").update(String(s.credentialSecret)).digest("hex");console.log("new settings.js:",h.slice(0,8),"len",String(s.credentialSecret).length)'
docker exec node-red node -e 'const s=require("/data/settings.js");console.log("old settings.js:",s.credentialSecret?require("crypto").createHash("sha256").update(String(s.credentialSecret)).digest("hex").slice(0,8):"unset")'
docker exec node-red node -e 'const c=require("/data/.config.runtime.json");console.log("old generated :",c._credentialSecret?require("crypto").createHash("sha256").update(String(c._credentialSecret)).digest("hex").slice(0,8)+" len "+c._credentialSecret.length:"absent")'
```

The new instance's prefix has to equal whichever of the old two is the real
one. **`settings.js` wins over the generated key**: if the old instance has an
active `credentialSecret`, that is what encrypted the file and
`.config.runtime.json` is a leftover. The generated key only applies when
`settings.js` leaves it unset — which is the case on this instance, but is
worth confirming rather than assuming.

If the md5 sums differ, re-copy the file from the old instance before starting
again (B2), because the one in place may already be the wrongly re-encrypted
version.

## Phase C — repoint the registry and look

`registry.yml`, the `wfm-prod` entry:

```yaml
    compose_service: node-red-prod          # was: node-red
    admin_root: "/node-red-prod"            # the new runtime's httpAdminRoot
    # compose_file and image_tag already match the new container
```

Both values move together. `admin_root` is what the runtime serves, and the new
one really does serve `/node-red-prod` — unlike the old one, which is why the
value is `""` until this step.

**Between this change and phase D, `DRY_RUN=false` on `wfm-prod` is the one
thing not to do.** The registry now points at the empty container while the old
one still runs the flow, so a real deploy would start a second publisher on
`dpn-svr-iot:8883` instead of replacing the first. The dry run is safe, and is
the whole point of this phase.

**Done, 2026-09-10: `362 changed lines`.** Which is the 19 nodes against an
empty instance, and it took four attempts at phase B to get there — the two
key locations were the last of them.

Then Jenkins: `INSTANCE=wfm-prod`, `DRY_RUN=true`, `EXPECT_REV` empty.

Expect a **large diff** — `-[]` against 19 nodes — because the target is empty
and Git is not. That is the opposite of the "already up to date" a normal prod
dry run gives, and here it is the right answer. Note the `rev` it prints.

This run also proves the credential `nodered-wfm-prod-auth` matches the new
instance's `adminAuth`. The token call that succeeded through nginx was against
this container, so it should — but a dry run is where you find out for free.

## Phase D — the cutover

Both runtimes hold the same publishing flow the moment the deploy lands, and
`Extruder abfrage` injects **every 5 seconds** into `mqtt out` on
`dpn-svr-iot:8883`. Two publishers on one topic is the failure this whole
project is arranged to prevent, so the old one stops **first**:

```bash
# 1. take the old instance out, and make sure it stays out
docker compose -f /home/administrator/Base_Container/docker-compose.yml stop node-red
#    if A4 showed restart=always, set it to "no" in the compose file now — a
#    reboot would otherwise bring back a second publisher
```

```
# 2. Jenkins: INSTANCE=wfm-prod, DRY_RUN=false, EXPECT_REV=<the rev from phase C>
```

Expect `deployed (200)`. The ingest gap is the time between the two steps —
keep it short, and pick the hour deliberately if the data matters.

**3. Verify, in the new editor** at `http://wfm-svr-lin01/node-red-prod`:

- **19 nodes across 2 tabs.** A different count means the deploy did not carry
  what Git holds.
- the `mqtt out` node shows **connected**. If it does not, `flows_cred.json` or
  the `credentialSecret` did not come across — that is phase B, not a node
  problem.
- the OPC UA endpoint with the stored login connects.
- data arrives at the far end of the MQTT topic again, at the rate it did
  before.

If the MQTT node stays disconnected: start the old container again, and the
estate is back where it was. That is why phase D stops it rather than deleting
it.

## Phase E — retire the old container

Only after phase D has run long enough to trust it — a shift, a day, whatever
the data tells you.

1. Remove the `node-red` service from
   `/home/administrator/Base_Container/docker-compose.yml`.
2. Leave `node-red/data/` on disk, and keep the tarball from A2 somewhere that
   is backed up. It is the only copy of the pre-cutover credentials.
3. `collect-inventory.py` then sees two Node-RED containers on this host
   instead of three, and `architecture.md`'s note about "one server whose
   single instance became a pair" stops being true — it becomes a normal host.

## Phase F — test the change loop

Use **`Flow 1`**, not `Extruder abfrage`: `Flow 1` reads OPC UA and writes to
`debug`, so running it briefly in two places costs nothing, while
`Extruder abfrage` would publish twice.

```bash
python3 scripts/nr.py check wfm-prod                                    # 1. still clean
python3 scripts/nr.py promote wfm-prod wfm-test "Flow 1" --copy         # 2. arrives DISABLED
git commit -am "promote(wfm-test): bring Flow 1 onto the workbench" && git push
python3 scripts/nr.py edit wfm-test                                     # 3. enable Flow 1, change it
python3 scripts/normalize.py --write apps/wfm-test/flows.json
git diff apps/wfm-test/flows.json
git commit -am "flows(wfm-test): ..." && git push
```

`promote` reports the `OpcUa-Endpoint` config nodes it had to create on the
workbench, carrying prod's endpoint addresses. Reading the same server twice is
tolerable — but read the report rather than assuming that.

Deploy `wfm-test` (dry run, then the deploy with its `EXPECT_REV`), try the
change, then:

```bash
python3 scripts/nr.py promote wfm-test wfm-prod "Flow 1" --move
git commit -am "promote(wfm-prod): ship the changed Flow 1" && git push
```

Deploy **`wfm-test` first, then `wfm-prod`**, each with its own two runs. After
the prod deploy: still 19 nodes, and the change is in the editor.

## Phase G — test a new tab

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

Nothing before phase D changes the running instance, and phase D is a stop, not
a delete:

```bash
docker compose -f /home/administrator/Base_Container/docker-compose.yml up -d node-red
docker compose -f /home/administrator/Base_Container/docker-compose.yml stop node-red-prod
# registry.yml back to compose_service: node-red, admin_root: ""
```

The old container comes back with its own `/data`, which the cutover only read.
If that directory is ever itself in doubt, the tarball from A2 restores it:

```bash
sudo tar xzf ~/wfm-prod-pre-cutover.tgz -C /home/administrator/Base_Container
```

A failed deploy needs no rollback at all: `deploy.py` writes the whole flow or
nothing, and with `EXPECT_REV` it refuses rather than writing over something it
was not shown.
