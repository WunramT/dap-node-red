# Open questions

What is still unknown, ranked by how much it blocks, with the command that closes it.

## Run this first

`scripts/collect-inventory.py` visits every site server over SSH and answers questions 1 to 3 in one pass. Read-only; it reports the existence of `credentialSecret`, `adminAuth` and any `FORGE_*` token, never their values.

```bash
pip install paramiko
# credentials go in hosts.local.json — gitignored, see the script's docstring
python3 scripts/collect-inventory.py
```

It writes `inventory/REPORT.md` (the answers), `registry.draft.yml` (16 pre-filled entries) and `samples/*.flows.json` (the real flows, which unblock `normalize.py`).

## Blocking

### 1. The real admin root of every instance

The one field `deploy.py` cannot get wrong, and the first inventory pass got it wrong on five instances: the parser matched Node-RED's commented-out template lines, so `//httpAdminRoot: '/admin'` was reported as a configured `/admin`. Those five answered `404`.

The collector now establishes it empirically — it tries each candidate root as `<root>/flows` and takes whichever answers `401` or `200`. Re-run it and read the **Admin API probe** table; the `registry.yml` draft uses the probed value and marks anything unresolved.

**Unblocks:** every `admin_root` in `registry.yml`, and therefore `deploy.py`.

### 2. The real `flows.json` files, in the repo

`normalize.py` is worth nothing until it has been run against the 226-node flow. The collector downloads every instance's flow into `samples/` — commit them. They hold no credentials; those live in `flows_cred.json`, which is never downloaded and is gitignored.

**Unblocks:** the first build task, and the cheapest possible test of whether normalized diffs are human-readable at all.

### 3. The FlowFuse credential key

Where the flow lives is settled: on disk, at `/opt/flowfuse-device/project/flows.json`, with `flows_cred.json` beside it on both device agents. Extraction is a file copy.

What is not settled is the key that decrypts `flows_cred.json`. It sits in the device-agent's own configuration rather than in `/data`, and it decides between two very different migrations — copy two files, or copy the flow and re-enter every credential by hand in the new instance.

```bash
ssh pod-svr-lin01 'sudo ls -la /opt/flowfuse-device/'
ssh pod-svr-lin01 'docker exec flowfuse-flow-fuse-1-1 sh -lc "ls -la /opt/flowfuse-device /opt/flowfuse-device/project"'
```

Look for the agent's config (`device.yml` or similar) and for a `credentialSecret` or `_credentialSecret` in `/opt/flowfuse-device/project/settings.js` or `.config.runtime.json`. Report whether one exists — not its value.

**Unblocks:** the migration procedure for two servers. It blocks nothing on the other eight — those go first regardless (see "Sequencing" in [`architecture.md`](architecture.md)).

### 4. Harbor project for Node-RED images

The existing pipeline pushes to `harbor.aks-infra.polipol-service.de` under `dap-api/` and `dap-ui/`. Node-RED images fit neither. Does a `dap-nodered` project exist, and which GitLab CI variable holds its push credential?

**Unblocks:** `base/Dockerfile`, `apps/*/Dockerfile`, and the `image_tag` values in `registry.yml`.

## Not blocking

### 5. Is `node-red-prod`'s 15-node flow real production work?

`wag-svr-lin01` was rebuilt the week before the inventory. Its prod instance has 15 nodes and no palette modules; its test instance has 226 nodes and two. That pattern reads more like a prod instance not yet migrated back after the rebuild than like a small production application.

If prod is genuinely unmigrated, it is the ideal first target — nothing to lose. If it is live, the 15-node flow is still the easier of the two to bring under Git first.

### 6. Three settings.js differences to reconcile

The diffs showed every difference across the 13 plain instances. Most are noise — indentation, whether `httpAdminRoot` is commented out, and comment blocks that Node-RED rewrote between versions (`wag` was rebuilt recently and has `telemetry` and `globalFunctionTimeout` blocks the others lack). Three are real:

1. **`cho-svr-lin01/node-red-prod` logs at `level: "trace"`** while every other instance logs at `info`. Reads like debugging left switched on in production.
2. **`wfm-svr-lin01/node-red` has `adminAuth` commented out entirely.** Its editor and Admin API are open to anyone who can reach the container — and it publishes port 1880 on the host. Worth deciding on before the pipeline gains write access to it.
3. **Node-RED versions differ**, because every instance runs `nodered/node-red:latest` and was first started on a different date. Pinning (decision 5) settles this, but the pin has to be chosen against the oldest instance still in use.

None of these block the scaffold. All three want a decision before the first deploy.

## Answered

| Question | Answer | Recorded in |
|---|---|---|
| Are the settings.js files the same file? | Yes — one template plus env overrides is viable. The literal text differs by whitespace, comment state and settings.js vintage; the real config differences are three, listed below | [`architecture.md`](architecture.md) |
| Which instances share logic? | None. No two flows match, so every instance gets its own `apps/` directory | [`architecture.md`](architecture.md) |
| Where does the FlowFuse flow live? | On disk, `/opt/flowfuse-device/project/flows.json` — a file copy, not a platform export | [`architecture.md`](architecture.md) |
| How does the deploying agent reach the Admin API? | Jenkins ships `deploy.py` over SSH and runs it on the target host, reaching the container by IP on `app_network` | decision 10 |
| How many servers and instances? | 8 servers × dev/prod = 16 instances | [`architecture.md`](architecture.md) |
| `wag-svr-lin01` or `wag-svr-lin01n`? | `wag-svr-lin01`, rebuilt the week before the inventory — current baseline | [`architecture.md`](architecture.md) |
| Does this repo become the scaffold? | Yes; the template stack has been removed | [`architecture.md`](architecture.md) |
| Would a UI help? | Yes, as a static read-only drift report — not a control plane | decision 11 |
