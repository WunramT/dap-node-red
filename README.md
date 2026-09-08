# dap-node-red

Deployment for 16 Node-RED runtimes across 10 servers — 14 plain instances, 2 under FlowFuse awaiting migration. Git holds the flows, CI deploys them.

Two transports, both versioned:

- **flow logic** → Node-RED Admin API `POST <admin_root>/flows`, no container restart, daily
- **palette modules** → image rebuild plus a service-scoped compose recreate, rare

## Documentation

| Document | Covers |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | repo layout, the two transports, deploy sequence, measured environment facts |
| [`docs/decisions.md`](docs/decisions.md) | closed decisions and their reasoning |
| [`docs/registry.md`](docs/registry.md) | `registry.yml` fields and validation rules |
| [`docs/runbook.md`](docs/runbook.md) | backup gate, `credentialSecret` pinning, deploy, `409` recovery, drift check |
| [`docs/open-questions.md`](docs/open-questions.md) | what is still unknown, and the command that answers it |
| [`docs/go-live-plan.md`](docs/go-live-plan.md) | the remaining steps to a live, team-visible pipeline |

## Status

| | |
|---|---|
| `registry.yml` + schema + validator | done — validates clean, no placeholders left |
| `normalize.py` + tests | done — validated against all 11 captured flows |
| `apps/*/flows.json` | done — 12 apps, normalized |
| `apps/*/package.json` + `Dockerfile` | done — 12 apps, palette versions as installed |
| `deploy.py` + tests | done — dry-run verified against 10 live instances |
| `drift-check.py` + tests | done — read-only sweep, JSON report |
| `Jenkinsfile` | replaced — deploy-only, dry-run verified; palette path still untested |

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

The `Jenkinsfile` is the deploy-only pipeline that replaced the inherited one. It carries the host map and the per-host credential ids from the template, and it reads `registry.yml` rather than repeating what runs where.
