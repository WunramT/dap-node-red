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

### 1. The FlowFuse credential key

Where the flow lives is settled: on disk, at `/opt/flowfuse-device/project/flows.json`, with `flows_cred.json` beside it on both device agents. Extraction is a file copy.

What is not settled is the key that decrypts `flows_cred.json`. It sits in the device-agent's own configuration rather than in `/data`, and it decides between two very different migrations — copy two files, or copy the flow and re-enter every credential by hand in the new instance.

```bash
ssh pod-svr-lin01 'sudo ls -la /opt/flowfuse-device/'
ssh pod-svr-lin01 'docker exec flowfuse-flow-fuse-1-1 sh -lc "ls -la /opt/flowfuse-device /opt/flowfuse-device/project"'
```

Look for the agent's config (`device.yml` or similar) and for a `credentialSecret` or `_credentialSecret` in `/opt/flowfuse-device/project/settings.js` or `.config.runtime.json`. Report whether one exists — not its value.

**Unblocks:** the migration procedure for two servers. It blocks nothing on the other eight — those go first regardless (see "Sequencing" in [`architecture.md`](architecture.md)).

### 2. Jenkins credentials for 13 instances

`registry.yml` now **names** 26 credentials — `nodered-<instance>-auth` and `nodered-<instance>-credsecret`. Naming them is not the same as having them: the ids validate, and a deploy fails at runtime until the credentials exist in Jenkins.

`credential_secret_id` in particular cannot be created before the backup gate, because it must hold each instance's **existing** generated key. Creating it from a fresh value re-encrypts every stored credential into garbage. Order matters here — [`runbook.md`](runbook.md).

`wfm` needs a decision before a credential: its `adminAuth` is off, so there is nothing to authenticate against yet.

**Unblocks:** any real deploy.

### 3. What are `slu-prod` and `slu-test` for?

Both are **running** containers with `adminAuth` on, reachable, and answering `401` — they are not stopped. They are empty: no `flows.json`, no `flows_cred.json`, and `/data` untouched since July 2025.

So there is nothing to deploy to them, and starting them changes nothing. To bring them into the pipeline, three things are needed, in this order:

1. **A flow.** Someone builds it, or copies one from elsewhere. This is the actual question — what are these two instances for?
2. `apps/slu-prod/` and `apps/slu-test/`, each with `flows.json`, `package.json` and a `Dockerfile`. `scaffold-apps.py` writes them once a flow exists in `samples/`.
3. `app: slu-prod` in `registry.yml` in place of `null`, and `nodered-slu-prod-auth` in Jenkins.

The pipeline needs no change. They are also the safest possible first true deploy — an empty instance has nothing to lose.

**Unblocks:** nothing. Two instances stay idle until someone decides what they do.

## Not blocking

### 4. Is `wag-prod`'s 15-node flow real production work?

`wag-svr-lin01` was rebuilt the week before the inventory. Its prod instance has 15 nodes and no palette modules; its test instance has 222 nodes and two. That pattern reads more like a prod instance not yet migrated back after the rebuild than like a small production application.

If prod is genuinely unmigrated, it is the ideal first target — nothing to lose. If it is live, the 15-node flow is still the easier of the two to bring under Git first.

## Answered

| Question | Answer | Recorded in |
|---|---|---|
| The palette versions? | Collected from the running instances; all 11 apps carry a `package.json` and a `Dockerfile` | `apps/` |
| Harbor project for the images? | `dap-node-red` exists. Tags are `<registry>/dap-node-red/<app>:<node-red-version>-<palette build>`, filled in for all 13 | `registry.yml` |
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
