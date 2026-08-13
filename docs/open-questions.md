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

### 1. Are the 16 `settings.js` files the same file?

The expectation is yes, differing only in `httpAdminRoot` and `dns_search`. Worth verifying rather than assuming, because four things plausibly differ and one of them is invisible:

- **`httpAdminRoot`** — different by design, one per instance
- **`dns_search`** — different per site
- **`adminAuth` bcrypt hash** — different if the sites do not share one admin password
- **`credentialSecret`** — currently unset everywhere; once pinned (see [`runbook.md`](runbook.md)) it is necessarily different per instance
- **the scaffold itself** — this is the invisible one. Node-RED generates `settings.js` from the image default on first run, and the instances run `nodered/node-red:latest`. Instances first started months apart were seeded from different image versions, so their `settings.js` can differ in options, defaults and comment blocks that nobody ever edited. Two files can be "unmodified" and still not match.

The collector groups the files by hash, after masking the secret values and the fields that are per-instance by nature, and reports:

- **one group** → one template plus env overrides, one file in the repo, and the four fields above become per-instance values
- **several groups** → it writes the diffs between group representatives straight into the report, so what actually differs is visible without a second pass

**Unblocks:** repository layout. This is the difference between one file and sixteen.

### 2. The real `flows.json` files, in the repo

`normalize.py` is worth nothing until it has been run against the 226-node flow. The collector downloads every instance's flow into `samples/` — commit them. They hold no credentials; those live in `flows_cred.json`, which is never downloaded and is gitignored.

**Unblocks:** the first build task, and the cheapest possible test of whether normalized diffs are human-readable at all.

### 3. Where does the authoritative flow live on the two FlowFuse servers?

Those instances become plain containers as part of this project (decision 12), so their flows have to come out of FlowFuse once. Everything about how depends on one fact: whether `/data/flows.json` is the real flow, a cache, or absent because FlowFuse keeps it in its platform.

`collect-inventory.py` answers it — it reports the storage module in `settings.js`, every `flows*.json` on disk, the `FORGE_*` environment with token values masked, and the palette FlowFuse installed. Read the **FlowFuse instances** section of `inventory/REPORT.md`.

Two follow-ups that the report scopes rather than answers:

- **Can the credential key be exported?** FlowFuse encrypts credentials with a key it manages. If that key cannot travel, every credential in a migrated flow is re-entered once by hand in the new instance. That is a per-instance manual step, and it is much better planned than discovered during a cutover.
- **What does the export path look like?** Whether it is a UI export per instance or a platform API call decides whether the migration is a documented manual procedure or a script. Not worth designing before the report says where the flow is.

**Unblocks:** the migration procedure for two of the servers. It blocks nothing on the other six — those go first regardless (see "Sequencing" in [`architecture.md`](architecture.md)).

### 4. Harbor project for Node-RED images

The existing pipeline pushes to `harbor.aks-infra.polipol-service.de` under `dap-api/` and `dap-ui/`. Node-RED images fit neither. Does a `dap-nodered` project exist, and which GitLab CI variable holds its push credential?

**Unblocks:** `base/Dockerfile`, `apps/*/Dockerfile`, and the `image_tag` values in `registry.yml`.

## Not blocking

### 5. Is `node-red-prod`'s 15-node flow real production work?

`wag-svr-lin01` was rebuilt the week before the inventory. Its prod instance has 15 nodes and no palette modules; its test instance has 226 nodes and two. That pattern reads more like a prod instance not yet migrated back after the rebuild than like a small production application.

If prod is genuinely unmigrated, it is the ideal first target — nothing to lose. If it is live, the 15-node flow is still the easier of the two to bring under Git first.

### 6. Which instances actually share logic?

Determines how many shared `apps/` directories exist and, later, how many subflow npm packages get written. The scaffold works with zero shared apps; this only affects how much deduplication is available.

## Answered

| Question | Answer | Recorded in |
|---|---|---|
| How does the deploying agent reach the Admin API? | Jenkins ships `deploy.py` over SSH and runs it on the target host, reaching the container by IP on `app_network` | decision 10 |
| How many servers and instances? | 8 servers × dev/prod = 16 instances | [`architecture.md`](architecture.md) |
| `wag-svr-lin01` or `wag-svr-lin01n`? | `wag-svr-lin01`, rebuilt the week before the inventory — current baseline | [`architecture.md`](architecture.md) |
| Does this repo become the scaffold? | Yes; the template stack has been removed | [`architecture.md`](architecture.md) |
| Would a UI help? | Yes, as a static read-only drift report — not a control plane | decision 11 |
