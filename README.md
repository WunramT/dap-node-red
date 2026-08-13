# dap-node-red

Deployment for 15 Node-RED runtimes across 10 servers — 13 plain instances, 2 under FlowFuse awaiting migration. Git holds the flows, CI deploys them.

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

## Status

| | |
|---|---|
| `registry.yml` + schema + validator | done — values measured, image tags and credential ids pending |
| `normalize.py` + tests | done — validated against all 11 real flows |
| `apps/*/flows.json` | done — 11 apps, normalized |
| `apps/*/package.json` + `Dockerfile` | done — 11 apps, palette versions as installed |
| `deploy.py` + tests | done — pending a run against a real instance |
| `drift-check.py` | not built |
| `Jenkinsfile` | still the template's; holds the host map the new pipeline needs |

```bash
pip install -r scripts/requirements.txt

python3 scripts/validate-registry.py --draft      # registry against the schema
python3 scripts/test_normalize.py                 # normalizer properties
python3 scripts/normalize.py --check apps/*/flows.json
python3 scripts/scaffold-apps.py                  # samples/ -> apps/
python3 scripts/test_deploy.py                    # deploy against a stub Admin API
python3 scripts/deploy.py --instance wag-prod --dry-run

# Re-inventory the hosts (read-only; credentials in a gitignored hosts.local.json)
python3 scripts/collect-inventory.py
```

`collect-inventory.py` reports the existence of `credentialSecret`, `adminAuth` and any
FlowFuse token, never their values.

The `Jenkinsfile` is still the one inherited from the project template. It holds the host and credential map the new deployment pipeline needs, so it stays until that pipeline replaces it.
