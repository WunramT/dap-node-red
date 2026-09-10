# dap-node-red

Deployment for 16 Node-RED runtimes across 10 servers — 14 plain instances, 2 under FlowFuse awaiting migration. Git holds the flows, CI deploys them.

Two transports, both versioned:

- **flow logic** → Node-RED Admin API `POST <admin_root>/flows`, no container restart, daily
- **palette modules** → image rebuild plus a service-scoped compose recreate, rare

## Making a change

Everything you do day to day is one of two things: **changing a tab prod already
runs**, or **building a new one**. Both are worked out on the `*-test` instance —
a workbench, empty unless something is being tested (decision 15) — and both end
with a deploy of *both* instances.

The examples use `wfm`. Swap in your own instance pair and tab name; the tab name
is the label on the tab in the editor, in quotes.

### Way 1 — change a tab that prod already runs

The tab is copied onto the workbench, changed there, tried out, then moved back.
Prod keeps running the old version the whole time.

```bash
# 1. Is prod still what Git says it is? If not, capture first — see below.
python3 scripts/nr.py check wfm-prod

# 2. Bring the tab onto the workbench. It arrives DISABLED, so nothing starts by itself.
python3 scripts/nr.py promote wfm-prod wfm-test "Extruder abfrage" --copy
git commit -am "promote(wfm-test): bring Extruder abfrage onto the workbench" && git push

# 3. Change it locally. Every tab opens disabled — enable just this one, then press Deploy.
python3 scripts/nr.py edit wfm-test
python3 scripts/normalize.py --write apps/wfm-test/flows.json
git diff apps/wfm-test/flows.json
git commit -am "flows(wfm-test): ..." && git push
```

Now deploy `wfm-test` in Jenkins (see **Deploying**) and try the change on the
real instance. When it does what you want:

```bash
# 4. Move it back to prod. --move, so it stops on the workbench as it starts in prod.
python3 scripts/nr.py promote wfm-test wfm-prod "Extruder abfrage" --move
git commit -am "promote(wfm-prod): ship Extruder abfrage" && git push
```

Then deploy in Jenkins **`wfm-test` first, then `wfm-prod`** — that order is what
keeps the two from running the same tab at the same time.

### Way 2 — build a new tab

Same loop without the first promotion: there is nothing in prod to copy.

```bash
# 1. Build it on the workbench. Add a tab, press Deploy.
python3 scripts/nr.py edit wfm-test
python3 scripts/normalize.py --write apps/wfm-test/flows.json
git commit -am "flows(wfm-test): add Extruder abfrage" && git push
```

Deploy `wfm-test` in Jenkins and try it. When it works:

```bash
# 2. Move it into prod.
python3 scripts/nr.py promote wfm-test wfm-prod "Extruder abfrage" --move
git commit -am "promote(wfm-prod): ship Extruder abfrage" && git push
```

Deploy `wfm-test` first, then `wfm-prod`, as above.

### Deploying

Jenkins does the writing — two runs, and the second is pinned to what the first
showed you:

| | `INSTANCE` | `DRY_RUN` | `EXPECT_REV` |
|---|---|---|---|
| 1. look | `wfm-test` | `true` | empty |
| 2. write | `wfm-test` | `false` | the `rev` the dry run printed |

`EXPECT_REV` is what makes the safety net real: if anyone deployed in the browser
between your two runs, the write is refused instead of flattening their edit.
Without it the deploy overwrites whatever it finds, and says so.

### Four things worth knowing

- **`--copy` and `--move` are not interchangeable, and neither is the default.**
  `--copy` for prod → workbench, because prod has to keep running the tab.
  `--move` for workbench → prod, because a tab left enabled on the workbench
  runs alongside prod — two runtimes on the same PLC, the same topic, and the
  only symptom is data arriving twice.
- **Read what `promote` prints.** If the destination is missing a config node
  the tab needs, it is created with the *source's* values and named in the
  output. Point it at the right broker or database before deploying.
- **A `409` is not a failure to work around.** It means someone edited in the
  browser. Get that edit into Git and then deploy again — there is no `--force`:
  ```bash
  python3 scripts/nr.py capture wfm-test
  git commit -am "flows(wfm-test): capture browser edit" && git push
  ```
- **New palette modules are the other transport.** Editing
  `apps/<app>/package.json` needs an image rebuild and restarts the container:
  [`docs/runbook.md`](docs/runbook.md), "Palette change".

The long version of all of this, including the local editor and what it can and
cannot reach: [`docs/runbook.md`](docs/runbook.md), "Changing a flow".

## Documentation

| Document | Covers |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | repo layout, the two transports, deploy sequence, measured environment facts |
| [`docs/decisions.md`](docs/decisions.md) | closed decisions and their reasoning |
| [`docs/registry.md`](docs/registry.md) | `registry.yml` fields and validation rules |
| [`docs/runbook.md`](docs/runbook.md) | backup gate, `credentialSecret` pinning, deploy, `409` recovery, drift check |
| [`docs/open-questions.md`](docs/open-questions.md) | what is still unknown, and the command that answers it |
| [`docs/go-live-plan.md`](docs/go-live-plan.md) | the remaining steps to a live, team-visible pipeline |
| [`docs/wfm-prod-migration.md`](docs/wfm-prod-migration.md) | putting an instance that predates the pipeline under it, `wfm-prod` as the pattern |

## Status

| | |
|---|---|
| `registry.yml` + schema + validator | done — validates clean, no placeholders left |
| `normalize.py` + tests | done — validated against all 11 captured flows |
| `apps/*/flows.json` | done — 12 apps, normalized |
| `apps/*/package.json` + `Dockerfile` | done — 12 apps, palette versions as installed |
| `deploy.py` + tests | done — dry-run verified against 10 live instances |
| `promote.py` + tests | done — one tab and its dependencies, either direction |
| `drift-check.py` + tests | done — read-only sweep, JSON report |
| `capture.py` | done — the instance-to-Git return path |
| `compose/editor.yml` | done — local editor, every tab disabled on arrival |
| Image build jobs | done — 12 build + sign jobs, generated from `registry.yml`, three at a time |
| `Jenkinsfile` | done — deploy-only, first run green against `wag-prod` |

Day to day, one entry point:

```bash
python3 scripts/nr.py            # pick an instance, pick an action
python3 scripts/nr.py status     # which instances still match Git
```

`.devcontainer/` brings Python, the dependencies and Docker access for the local
editor, so the commands above work the same inside VS Code.

## What each piece does

`nr.py` is the front door; everything below it can also be called directly.

| Action | What it does, and when |
|---|---|
| `nr.py` | The one entry point: asks which instance and which action, so the instance list lives only in `registry.yml`. Start here. |
| `nr.py status` | Table of every instance and whether it still matches Git — the morning check, and what tells you if someone edited in a browser. |
| `nr.py check <inst>` | The same question for one instance, with the diff. Run it before every promotion and before every deploy. |
| `nr.py edit <inst>` | Starts a local Node-RED on a copy of that app with **every tab disabled**, so you enable the one you work on, and on exit carries the flow — and any module you installed through Manage palette — back into `apps/`. The way to change a flow without touching a running instance; add `--baked` when the flow uses palette nodes, `--isolated` when it must not reach anything. |
| `nr.py capture <inst>` | Reads the running flow back into `apps/` so it can be committed. The recovery from a browser edit, and the only path from an instance back into Git. |
| `nr.py deploy <inst>` | Dry run only, on purpose — shows what a deploy would change. A real deploy is a reviewed commit that Jenkins carries out. |
| `nr.py promote <a> <b> <tab>` | Moves one tab and its dependencies between two apps: `--copy` prod → workbench (arrives disabled), `--move` workbench → prod (arrives enabled). The two change loops are built out of this. |

| Script | What it does, and when |
|---|---|
| `deploy.py` | Posts one app's flow to its instance through the Admin API, against a `rev` — with `--expect-rev` it refuses when the instance moved since the diff was reviewed. What Jenkins runs; never run it by hand against production. |
| `drift-check.py` | Compares every instance against Git and reports `clean` / `drifted` / `unreachable` / `no-app`, writing JSON with `--json`. Read-only by construction, so it is safe at any time — and it has no flag that writes. |
| `capture.py` | Fetches a running flow, normalizes it and writes it into `apps/<app>/`. The return path: after a browser edit, or on a `409`. |
| `promote.py` | Copies or moves a tab between two `apps/` directories with its config nodes and subflows, never overwriting the destination's own. Called through `nr.py promote`, which translates instance names to app directories. |
| `normalize.py` | Sorts and canonicalizes a `flows.json` so a two-line change diffs as two lines — `--check` in CI, `--write` after every editor session. Run it before every commit of a flow. |
| `validate-registry.py` | Checks `registry.yml` against the schema plus the rules a schema cannot express, such as "no floating image tags". Runs in CI on every push; run it yourself after editing the registry. |
| `collect-inventory.py` | Reads every host over SSH and reports what is actually deployed — versions, palettes, `admin_root`, whether `adminAuth` and `credentialSecret` exist, never their values. Run it when the estate changed under you, or to re-derive a fact this repo asserts. |
| `scaffold-apps.py` | Built the twelve `apps/` directories once out of `samples/`, and now leaves existing apps alone. Only for a new app, or with `--force` when you mean to discard local work. |
| `gen-image-pipeline.py` | Regenerates `apps/build-image-pipeline.yml` from `registry.yml` — one build-and-sign job per app, three running at a time. Run it after adding or removing an instance. |
| `test_normalize.py`, `test_deploy.py`, `test_nr.py`, `test_promote.py` | The four suites: normalizer properties, the deploy against a stub Admin API, the editor session round-trip, and the promotion rules. All four run in CI; run them before pushing anything under `scripts/`. |

| Not a script | What it is, and when it matters |
|---|---|
| `registry.yml` + `schemas/registry.schema.json` | The single source of truth for what runs where — host, compose service, `admin_root`, image tag, credential ids. Every tool reads it; nothing hard-codes an instance. |
| `apps/<app>/flows.json` | The flow, as Git holds it. This is what gets deployed, and it opens unchanged in the editor. |
| `apps/<app>/package.json` + `Dockerfile` | That app's palette, and the image built from it. Editing the first is the palette path: rebuild, then a restart. |
| `compose/editor.yml` | The local editor container `nr.py edit` starts, pinned to the instance's Node-RED version. Read it if you need to know what the editor can reach. |
| `Jenkinsfile` | The deploy pipeline: reads the registry, carries `deploy.py` and the flow to the target host over SSH, and runs it there. `INSTANCE`, `DRY_RUN`, `EXPECT_REV`, `DEPLOY_PALETTE`. |
| `.gitlab-ci.yml` | Validation and image builds: registry against the schema, every committed flow normalized, the four test suites, then build and sign. Nothing here deploys. |
| `samples/` | The flows as first captured, untouched since. The reference for "what did this look like before the project". |

The individual commands:
```bash
pip install -r scripts/requirements.txt

python3 scripts/validate-registry.py              # registry against the schema
python3 scripts/test_normalize.py                 # normalizer properties
python3 scripts/normalize.py --check apps/*/flows.json
python3 scripts/scaffold-apps.py                  # samples/ -> apps/
python3 scripts/test_deploy.py                    # deploy against a stub Admin API
python3 scripts/deploy.py --instance wag-prod --dry-run
python3 scripts/drift-check.py --all --json inventory/drift.json

# Re-inventory the hosts (read-only; credentials in a gitignored hosts.local.json)
python3 scripts/collect-inventory.py
```

`collect-inventory.py` reports the existence of `credentialSecret`, `adminAuth` and any
FlowFuse token, never their values.
