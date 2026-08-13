# Open questions

What is still unknown, ranked by how much it blocks, with the command that closes it.

## Run this first

`scripts/collect-inventory.py` visits every site server over SSH. Read-only; it reports the existence of `credentialSecret`, `adminAuth` and any `FORGE_*` token, never their values.

```bash
pip install paramiko
# credentials go in hosts.local.json — gitignored, see the script's docstring
python3 scripts/collect-inventory.py
```

It writes `inventory/REPORT.md` (the answers), `registry.draft.yml` and `samples/*.flows.json`. It has already been run — `registry.yml` and the table at the bottom of this file carry its results. Re-run it after any change to a host.

## Blocking

### 1. The 11 real `flows.json` files, in the repo

`normalize.py` is the next thing to build and it cannot be tested without them. The collector already downloaded them to `samples/` on the machine that ran it — they just need to reach the repo:

```bash
git add samples/ && git commit -m "chore: add flow samples from the inventory" && git push
```

`flows.json` holds no credentials; those live in `flows_cred.json`, which the collector never downloads and `.gitignore` excludes. `samples/` is also in `.semgrepignore`, because broker hostnames and topic names read as secrets to the scanner.

11 files, not 13 — `slu-prod` and `slu-test` have no flow.

**Unblocks:** `normalize.py`, and with it the first real test of whether a 205-node flow diffs readably.

### 2. The FlowFuse credential key

Where the flow lives is settled: on disk, at `/opt/flowfuse-device/project/flows.json`, with `flows_cred.json` beside it on both device agents. Extraction is a file copy.

What is not settled is the key that decrypts `flows_cred.json`. It sits in the device-agent's own configuration rather than in `/data`, and it decides between two very different migrations — copy two files, or copy the flow and re-enter every credential by hand in the new instance.

```bash
ssh pod-svr-lin01 'sudo ls -la /opt/flowfuse-device/'
ssh pod-svr-lin01 'docker exec flowfuse-flow-fuse-1-1 sh -lc "ls -la /opt/flowfuse-device /opt/flowfuse-device/project"'
```

Look for the agent's config (`device.yml` or similar) and for a `credentialSecret` or `_credentialSecret` in `/opt/flowfuse-device/project/settings.js` or `.config.runtime.json`. Report whether one exists — not its value.

**Unblocks:** the migration procedure for two servers. It blocks nothing on the other eight — those go first regardless (see "Sequencing" in [`architecture.md`](architecture.md)).

### 3. Harbor project for Node-RED images

The existing pipeline pushes to `harbor.aks-infra.polipol-service.de` under `dap-api/` and `dap-ui/`. Node-RED images fit neither. Does a `dap-nodered` project exist, and which GitLab CI variable holds its push credential?

**Unblocks:** `base/Dockerfile`, `apps/*/Dockerfile`, and the 13 `image_tag` values that are `CHANGEME` in `registry.yml`.

### 4. Jenkins credentials for 13 instances

`registry.yml` names an `auth_credential_id` and a `credential_secret_id` per instance, and both are `CHANGEME`. They cannot be filled in before the backup gate runs, because `credential_secret_id` must hold each instance's **existing** generated key — see [`runbook.md`](runbook.md).

`wfm` is the exception in a way that needs a decision rather than a credential: its `adminAuth` is off, so there is nothing to authenticate against. Switching it on is the obvious fix and it is a change to a running instance, so it is your call.

**Unblocks:** `validate-registry.py` without `--draft`, and therefore any real deploy.

## Not blocking

### 5. Is `wag-prod`'s 15-node flow real production work?

`wag-svr-lin01` was rebuilt the week before the inventory. Its prod instance has 15 nodes and no palette modules; its test instance has 222 nodes and two. That pattern reads more like a prod instance not yet migrated back after the rebuild than like a small production application.

If prod is genuinely unmigrated, it is the ideal first target — nothing to lose. If it is live, the 15-node flow is still the easier of the two to bring under Git first.

## Answered

| Question | Answer | Recorded in |
|---|---|---|
| The two settings.js deviations? | Both normalized to what the others do — `wfm` gets `adminAuth`, `cho-prod` goes back to `level: "info"`. One settings.js in the repo | decision 13 |
| What is every instance's admin root? | Probed on all 13: 8 on `/node-red-prod` or `/node-red-test`, 5 on plain `/`. All in `registry.yml` | [`architecture.md`](architecture.md) |
| Which Node-RED versions are running? | Three — 4.0.5, 4.0.9, 5.0.1. Pin each instance to its current version first; converging is a separate upgrade | [`architecture.md`](architecture.md) |
| Are the settings.js files the same file? | Yes — one template plus env overrides is viable. The literal text differs by whitespace, comment state and settings.js vintage; the real config differences are three, listed below | [`architecture.md`](architecture.md) |
| Which instances share logic? | None. No two flows match, so every instance gets its own `apps/` directory | [`architecture.md`](architecture.md) |
| Where does the FlowFuse flow live? | On disk, `/opt/flowfuse-device/project/flows.json` — a file copy, not a platform export | [`architecture.md`](architecture.md) |
| How does the deploying agent reach the Admin API? | Jenkins ships `deploy.py` over SSH and runs it on the target host, reaching the container by IP on `app_network` | decision 10 |
| How many servers and instances? | 15 runtimes on 10 servers: 13 plain, 2 FlowFuse. 11 carry a real flow — `slu-prod` and `slu-test` are empty | [`architecture.md`](architecture.md) |
| `wag-svr-lin01` or `wag-svr-lin01n`? | `wag-svr-lin01`, rebuilt the week before the inventory — current baseline | [`architecture.md`](architecture.md) |
| Does this repo become the scaffold? | Yes; the template stack has been removed | [`architecture.md`](architecture.md) |
| Would a UI help? | Yes, as a static read-only drift report — not a control plane | decision 11 |
