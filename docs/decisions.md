# Decisions

Closed decisions with their reasoning. A decision marked **Closed** is settled; reopen it only with new evidence about the environment, not with a fresh preference.

## 1. Git is the source of truth — Closed

Flows live in Git as normalized JSON. Every change is a commit, reviewable as a diff, revertable.

The alternative was a database-backed control plane (the *DAP Node-RED Management Platform* concept: FastAPI + Vue 3 + PostgreSQL + Jinja2 + SSH deploy). Rejected:

- a DB has no history a reviewer can read, and needs a UI before anyone can see what is deployed
- Jinja2 placeholders baked into the stored flow make the flow unopenable in the editor — no return path, so work drifts back to manual editing
- SSH file writes with no `rev` check silently overwrite hand edits
- a container restart on every flow deploy opens an MQTT ingest gap, daily

Harvested from that concept and kept: the manifest shape (`global_variables` + per-instance `variables` → `registry.yml`), a narrow Jinja2 render step for composite strings only, the `setup_server.sh` bootstrap idea, and `--dry-run`.

Its port-allocation logic is not needed: no instance publishes a port, nginx routes by path.

## 2. Admin API is the flow transport — Closed

`POST <admin_root>/flows` with the `rev` from a preceding `GET`. It is the only transport that deploys a flow without restarting the container and detects concurrent edits.

## 3. A `rev` conflict aborts the pipeline — Closed

`409` means the running flow diverged from Git — someone edited in the browser. That is information. Flattening it destroys the edit and teaches everyone that the pipeline eats their work.

No `--force`. Not as a flag, not as a fallback, not behind a confirmation prompt. Resolution is: pull the running flow, normalize it, commit or discard it deliberately, then deploy.

## 4. Palette changes go through the image, not the API — Closed

npm modules cannot be installed through the Admin API. Palette changes rebuild `apps/<app>/Dockerfile` and recreate the service. That restart is acceptable because palette changes are rare; a flow-deploy restart would not be, because flow changes are daily.

`functionExternalModules: true` is set but unused. It is the loophole that would let a function node pull its own npm dependency at runtime and make the baked image a false guarantee — so CI fails on any `"module":` declaration in a function node. Keeping usage at zero is what keeps the image the single palette source.

## 5. Exact image tags — Closed

`nodered/node-red:latest` with `restart: always` means each host silently runs whatever it last pulled. Every image reference is pinned to an exact tag, in `base/Dockerfile` and in `registry.yml`.

## 6. Flows in the repo stay editor-valid — Closed

No placeholders, no template syntax in a committed `flows.json`. Rendering happens in CI, on a copy. The moment a committed flow stops opening in the editor, the editor→Git return path dies and manual deployment comes back.

Node-RED's `${ENV}` substitution replaces a whole property value. Composite strings (`mqtt-${SITE}/events`) need the Jinja2 pass — which is exactly why it exists and exactly why it stays that narrow.

## 7. Secrets come from Jenkins credentials only — Closed

No secret value in the repo, in pipeline logs, or in tool output. The inventory script reports the *existence* of a `credentialSecret`, never its value; anything built on it preserves that property.

`credentialSecret` must be pinned to each instance's **existing** generated value — a new value re-encrypts and breaks every stored credential. Procedure: [`runbook.md`](runbook.md).

## 8. Split CI: GitLab builds, Jenkins deploys — Closed

Discovered in this repo rather than decided: `.gitlab-ci.yml` builds, scans and cosign-signs images to Harbor via `ci-cd-catalog` components; `Jenkinsfile` reaches the site hosts over SSH with per-host credentials. The reach differs, so the split follows it — validation and build in GitLab, deploy in Jenkins. See [`architecture.md`](architecture.md).

## 9. drift-check is read-only — Closed

It reports. It never writes, never reconciles, never "fixes" an instance. A reconciling drift checker is decision 3 reintroduced through the back door.

## 10. The flow deploy runs on the target host — Closed

Jenkins ships `deploy.py` over its existing SSH connection and runs it there; the script reaches the instance by container IP on `app_network`.

No instance publishes a port and the 8 site servers sit in separate subnets, so a central agent cannot reach a container directly. The host can. SSH carries the script; it never writes a flow file — that would be decision 2 abandoned for the transport it replaced.

## 11. The visibility layer is a static report — Closed

A read-only page rendered from `drift-check.py` output plus Git: which instances match Git, which drifted, which flow version and image tag each one runs. Generated in CI, published as a static page.

The pull toward a real web application is understandable — the current state is genuinely invisible. It is still the wrong trade. A read-only report answers every question that matters here with a JSON producer and an HTML template. A web application answers the same questions and adds a backend, a database, an auth layer and a deployment of its own, and then grows a deploy button — at which point deploys stop being reviewed commits and decision 1 is undone from inside the browser.

Deploys stay in the pipeline, where they are reviewed and recorded. The page shows state.

## 12. FlowFuse is a migration source, not a deploy target — Closed

The two FlowFuse-managed servers are exported once into `apps/`, brought up as plain containers, and then deployed like every other instance. FlowFuse gets no transport, no `registry.yml` entry, no pipeline stage.

Keeping it alongside would mean maintaining two control planes with two answers to "what is running", which is the problem this project exists to end. And FlowFuse owning the flows is decision 1's rejected shape — a database as source of truth, with the flow reachable only through its platform.

What the migration costs, and what it does not, depends on where the authoritative flow lives and whether the credential key can be exported. Both are inventory questions before they are design questions. See [`architecture.md`](architecture.md) and [`open-questions.md`](open-questions.md).

