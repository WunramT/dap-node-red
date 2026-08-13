# dap-node-red

Deployment for ~16 Node-RED instances (8 site servers × dev/prod). Git holds the flows, CI deploys them.

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

Documentation and host discovery only. The scaffold — `normalize.py`, `deploy.py`, `registry.yml`, the app images — is not built yet.

Collect the facts the scaffold needs:

```bash
pip install paramiko
# credentials go in hosts.local.json — gitignored, see the script's docstring
python3 scripts/collect-inventory.py
```

Read-only. It writes `inventory/REPORT.md`, a `registry.yml` draft and the real flows into
`samples/`, and reports the existence of `credentialSecret`, `adminAuth` and any FlowFuse
token, never their values.

The `Jenkinsfile` is still the one inherited from the project template. It holds the host and credential map the new deployment pipeline needs, so it stays until that pipeline replaces it.
