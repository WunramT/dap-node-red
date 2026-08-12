# CLAUDE.md

Node-RED multi-instance deployment. Git holds the flows, CI deploys them, ~20 instances across ~8–10 site servers.

Read before working:

- [`docs/architecture.md`](docs/architecture.md) — the system: repo layout, the two transports, the deploy sequence, measured environment facts
- [`docs/decisions.md`](docs/decisions.md) — closed decisions and why. Check here before proposing a different approach
- [`docs/open-questions.md`](docs/open-questions.md) — what is still unknown and which command answers it
- [`docs/registry.md`](docs/registry.md) — `registry.yml` fields and validation rules
- [`docs/runbook.md`](docs/runbook.md) — backup gate, `credentialSecret` pinning, deploy, `409` recovery, drift check

## Constraints

These hold across every task in this repo. Each traces to a decision in `docs/decisions.md`.

1. **A `409` from `POST /flows` fails the pipeline.** Someone edited in the browser; the recovery is to capture that edit, not to overwrite it. There is no `--force` path — not a flag, not a fallback, not a prompt.
2. **A committed `flows.json` opens in the Node-RED editor unchanged.** Rendering happens in CI, on a copy. This is what keeps the editor→Git return path alive.
3. **Every image reference is an exact tag.** `latest` and other floating tags fail validation.
4. **Secrets come from Jenkins credentials, and stay there.** Report that a `credentialSecret` exists; never its value. This holds for repo content, pipeline logs and tool output alike.
5. **Compose calls name their service** — `docker compose up -d node-red-prod`. The shared `base_container/docker-compose.yml` also holds NATS.

## Working here

Flow deploys are daily and must not restart a container. Palette deploys are rare and may. Any design that restarts a container to change flow logic is the wrong design.

`docs/open-questions.md` questions 1–4 gate the scaffold: `deploy.py`, `schemas/registry.schema.json` and the repository layout each depend on an answer that is not in yet. Build `normalize.py` against the real sample flows first — it needs none of them, and it is the cheapest test of whether the whole approach produces reviewable diffs.

The repository still contains the company web-app template it was created from (`backend/`, `frontend/`, `.devcontainer/`, `setup_project.py`). It is unused by this architecture and its removal is open question 5 — awaiting an explicit go-ahead.
