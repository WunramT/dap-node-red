# CLAUDE.md

Node-RED multi-instance deployment. Git holds the flows, CI deploys them. 16 runtimes across 10 servers: 14 plain instances and 2 under FlowFuse, which are migrated to plain containers as part of this project. No two instances share a flow — every one is its own application.

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

Build `normalize.py` first, against the sample flows in `samples/`. It depends on none of the open questions, and it is the cheapest test of whether the whole approach produces reviewable diffs — if a 226-node flow does not diff readably, that is worth knowing before anything else is built.

The repository layout still depends on open question 1 (whether the 16 `settings.js` files are one file or several), so hold off on `schemas/registry.schema.json` until the discovery reports are in.

The `Jenkinsfile` is the one inherited from the project template — it deploys a FastAPI/Vue stack that no longer exists here. It stays because it holds the host map and per-host credential ids the new pipeline needs, and it is replaced rather than edited.
