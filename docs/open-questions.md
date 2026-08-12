# Open questions

What is still unknown, ranked by how much it blocks, with the command that closes it.

## Run this first

On each of the 8 site servers. Read-only; reports the existence of `credentialSecret` and `adminAuth`, never their values.

```bash
mkdir -p inventory
for h in cho-svr-lin01 pod-svr-lin01 jan-svr-lin01 srem-svr-lin01 \
         wag-svr-lin01 foi-svr-lnx01 gor-svr-lin01 slu-svr-lin02; do
  scp scripts/discover-gaps.sh "$h:/tmp/" && ssh "$h" 'bash /tmp/discover-gaps.sh' > "inventory/$h.txt"
done
```

It produces the instance names, admin roots, image tags, palette modules and `settings.js` hashes that `registry.yml` needs, and answers question 1 below.

## Blocking

### 1. Are the 16 `settings.js` files the same file?

The expectation is yes, differing only in `httpAdminRoot` and `dns_search`. Worth verifying rather than assuming, because four things plausibly differ and one of them is invisible:

- **`httpAdminRoot`** — different by design, one per instance
- **`dns_search`** — different per site
- **`adminAuth` bcrypt hash** — different if the sites do not share one admin password
- **`credentialSecret`** — currently unset everywhere; once pinned (see [`runbook.md`](runbook.md)) it is necessarily different per instance
- **the scaffold itself** — this is the invisible one. Node-RED generates `settings.js` from the image default on first run, and the instances run `nodered/node-red:latest`. Instances first started months apart were seeded from different image versions, so their `settings.js` can differ in options, defaults and comment blocks that nobody ever edited. Two files can be "unmodified" and still not match.

`discover-gaps.sh` prints a `sha256` prefix per file. Group the hashes:

- **one group** → one template plus env overrides, one file in the repo, and the four fields above become per-instance values
- **several groups** → diff a representative from each and reconcile deliberately; the repo grows a per-instance settings directory

**Unblocks:** repository layout. This is the difference between one file and sixteen.

### 2. Both real `flows.json` files, in the repo

`normalize.py` is worth nothing until it has been run against the 226-node flow. Copy both in — `flows.json` holds no credentials, those live in `flows_cred.json`, which stays out and is gitignored:

```bash
mkdir -p samples
scp wag-svr-lin01:<data_mount>/flows.json samples/wag-prod.flows.json
scp wag-svr-lin01:<data_mount>/flows.json samples/wag-test.flows.json
```

The `data_mount` line in each instance's `discover-gaps.sh` section gives the real paths.

**Unblocks:** the first build task, and the cheapest possible test of whether normalized diffs are human-readable at all.

### 3. Harbor project for Node-RED images

The existing pipeline pushes to `harbor.aks-infra.polipol-service.de` under `dap-api/` and `dap-ui/`. Node-RED images fit neither. Does a `dap-nodered` project exist, and which GitLab CI variable holds its push credential?

**Unblocks:** `base/Dockerfile`, `apps/*/Dockerfile`, and the `image_tag` values in `registry.yml`.

## Not blocking

### 4. Is `node-red-prod`'s 15-node flow real production work?

`wag-svr-lin01` was rebuilt the week before the inventory. Its prod instance has 15 nodes and no palette modules; its test instance has 226 nodes and two. That pattern reads more like a prod instance not yet migrated back after the rebuild than like a small production application.

If prod is genuinely unmigrated, it is the ideal first target — nothing to lose. If it is live, the 15-node flow is still the easier of the two to bring under Git first.

### 5. Which instances actually share logic?

Determines how many shared `apps/` directories exist and, later, how many subflow npm packages get written. The scaffold works with zero shared apps; this only affects how much deduplication is available.

## Answered

| Question | Answer | Recorded in |
|---|---|---|
| How does the deploying agent reach the Admin API? | Jenkins ships `deploy.py` over SSH and runs it on the target host, reaching the container by IP on `app_network` | decision 10 |
| How many servers and instances? | 8 servers × dev/prod = 16 instances | [`architecture.md`](architecture.md) |
| `wag-svr-lin01` or `wag-svr-lin01n`? | `wag-svr-lin01`, rebuilt the week before the inventory — current baseline | [`architecture.md`](architecture.md) |
| Does this repo become the scaffold? | Yes; the template stack has been removed | [`architecture.md`](architecture.md) |
| Would a UI help? | Yes, as a static read-only drift report — not a control plane | decision 11 |
