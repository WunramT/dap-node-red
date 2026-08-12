# Open questions

What is still unknown, ranked by how much it blocks, with the command that closes it. Nothing in `scripts/` beyond `discover-gaps.sh` gets written until questions 1–4 are answered — a schema or a deploy script built on a guess has to be unbuilt.

## Run this first

On each Node-RED host. Read-only; reports the existence of `credentialSecret` and `adminAuth`, never their values.

```bash
scp scripts/discover-gaps.sh <host>:/tmp/ && ssh <host> 'bash /tmp/discover-gaps.sh' > inventory/<host>.txt
```

It answers questions 2, 3 and 4 in one pass, and half of question 1.

## Blocking

### 1. How is the Admin API reachable from the deploying agent?

`deploy.py` cannot be designed without this. No instance publishes a port, so nginx is the only external entry, and the Jenkins pipeline currently reaches hosts by SSH (`sshCommand remote: REMOTE`), not by HTTP.

Three possible transports, in descending order of preference:

- **a. Direct HTTPS** from the Jenkins agent to a per-site nginx URL. Cleanest — `deploy.py` runs on the agent.
- **b. HTTP over the SSH hop**: Jenkins runs `curl` on the host against the container on `app_network`. Keeps the Admin API, the `rev` handshake and the no-restart property intact; SSH is only a tunnel, never a file-write path.
- **c. Neither** — then the transport question reopens, and it is worth solving properly rather than falling back to SSH file writes (see decision 1).

`discover-gaps.sh` reports the host→container leg. The agent→nginx leg needs a probe from the Jenkins agent itself:

```bash
# On the Jenkins agent, for one instance, expect 401 (reachable, adminAuth active):
curl -s -o /dev/null -w '%{http_code}\n' https://<node-red-url>/node-red-prod/flows
```

The unknown inside that command is `<node-red-url>`. The web apps route as `https://iot.polipol-service.pl/app/<4-char-site-prefix>`; whether Node-RED sits behind the same central nginx, behind a per-site nginx, or is not exposed at all is exactly what the nginx section of `discover-gaps.sh` looks for.

**Unblocks:** `deploy.py`, and whether `registry.yml` needs an `admin_base_url` field (see [`registry.md`](registry.md)).

### 2. The real instance list

The predecessor handoff says ~10 servers / ~20 instances. The `Jenkinsfile` host map holds 8. One of the two is stale.

```bash
for h in cho-svr-lin01 pod-svr-lin01 jan-svr-lin01 srem-svr-lin01 \
         wag-svr-lin01 foi-svr-lnx01 gor-svr-lin01 slu-svr-lin02; do
  ssh "$h" 'hostname -f; docker ps -a --format "{{.Names}}" | grep -i node.\\?red'
done
```

If that yields fewer than 20 instances, there are hosts missing from the Jenkins map — name them.

**Unblocks:** the `instances:` list in `registry.yml`, and the Jenkins host map for the new pipeline.

### 3. Are the ~20 `settings.js` files identical apart from `httpAdminRoot` and `dns_search`?

`discover-gaps.sh` prints a `sha256` prefix per file. Group the hashes:

- **all equal (after allowing for those two fields)** → one template plus env overrides, one file in the repo
- **mixed** → each difference has to be reconciled deliberately, and the repo layout grows a per-instance settings directory

**Unblocks:** repository layout. This is the difference between one file and twenty.

### 4. `wag-svr-lin01` or `wag-svr-lin01n`?

The inventory ran against `wag-svr-lin01`. The migration target was recorded as `wag-svr-lin01n`. The `Jenkinsfile` host map contains `wag-svr-lin01`, which means either the migration has not happened or Jenkins is pointing at the old box.

```bash
ssh wag-svr-lin01 'hostname -f'
ssh wag-svr-lin01n 'hostname -f'   # if this resolves, both boxes exist
```

**Unblocks:** whether the whole measured baseline describes a host that is being decommissioned.

## Blocking soon

### 5. Does this repository become the scaffold, or does a new one?

This repo currently holds the unmodified company web-app template — FastAPI, Vue 3, Postgres, Alembic, ~100 files, none of it used by the target architecture. Two options:

- **Gut it in place.** Keeps the repo name, the Git history, the `ci-cd-catalog` wiring in `.gitlab-ci.yml`, and the Jenkins host map. Deleting `backend/`, `frontend/`, `.devcontainer/`, `docker-compose.dev.yml`, `setup_project.py` is one commit and fully revertable in Git — but it is a large, one-way-feeling change that needs an explicit go-ahead.
- **New repo.** Leaves this one as a template instance and starts clean, at the cost of re-establishing the CI wiring.

Recommendation: gut it in place. The name is right, and the two genuinely reusable pieces both live here.

### 6. Both real `flows.json` files, in the repo

`normalize.py` is worth nothing until it has been run against the 226-node flow. Copy both in — `flows.json` holds no credentials (those live in `flows_cred.json`, which stays out):

```bash
mkdir -p samples
scp wag-svr-lin01:/path/to/node-red-prod/data/flows.json samples/wag-prod.flows.json
scp wag-svr-lin01:/path/to/node-red-test/data/flows.json samples/wag-test.flows.json
```

The `data_mount` line in the `discover-gaps.sh` report gives the real paths.

**Unblocks:** the first build task, and the cheapest possible test of whether normalized diffs are human-readable at all.

### 7. Harbor project for Node-RED images

The existing pipeline pushes to `harbor.aks-infra.polipol-service.de` under `dap-api/` and `dap-ui/`. Node-RED images fit neither. Does a `dap-nodered` project exist, and which GitLab CI variable holds its push credential?

**Unblocks:** `base/Dockerfile`, `apps/*/Dockerfile`, and the `image_tag` values in `registry.yml`.

## Not blocking

### 8. Is `node-red-prod`'s 15-node flow real production work?

Decides which pair is the first migration target — a 15-node flow with no palette modules is a good first subject, an abandoned one is not worth the effort.

### 9. Which instances actually share logic?

Determines how many shared `apps/` directories exist and, later, how many subflow npm packages get written. The scaffold works with zero shared apps; this only affects how much deduplication is available.
