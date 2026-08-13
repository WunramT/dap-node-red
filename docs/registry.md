# registry.yml

The instance inventory. One entry per running Node-RED instance, plus values shared by all of them. It is the only place that knows which app runs where.

Validated in GitLab CI against `schemas/registry.schema.json`. CI fails on: duplicate `name`, an `app` that has no `apps/<name>/` directory, a missing credential id, an unpinned `image_tag`, or any unknown key.

## Shape

```yaml
global_variables:
  MQTT_BROKER_HOST: mqtt.example.local

instances:
  - name: wag-node-red-prod
    host: wag-svr-lin01
    app: null
    admin_root: /node-red-prod
    auth_credential_id: nodered-wag-prod-auth
    credential_secret_id: nodered-wag-prod-credsecret
    dns_search: [rah.polipol.intra, wag.polipol.intra]
    image_tag: harbor.aks-infra.polipol-service.de/dap-nodered/node-red-base:5.0.1-1
    variables:
      MACHINE_ID: M001
```

## Fields

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | unique instance key; also the compose service name and the `--instance` argument |
| `host` | yes | server the instance runs on; must appear in the Jenkins host map |
| `app` | yes | directory under `apps/`, or `null` for a standalone instance whose flow is not shared |
| `admin_root` | yes | value of `httpAdminRoot`, e.g. `/node-red-prod`. The API base path — the flows endpoint is `<base><admin_root>/flows` |
| `auth_credential_id` | yes | Jenkins credential holding the `adminAuth` user/password used for `POST <admin_root>/auth/token` |
| `credential_secret_id` | yes | Jenkins credential holding this instance's pinned `credentialSecret` |
| `dns_search` | no | DNS search domains for the container |
| `image_tag` | yes | exact Harbor tag. A `latest`, `main` or otherwise floating tag fails validation |
| `variables` | no | per-instance env vars, merged over `global_variables` |

`app: null` is normal, not a gap. Most instances are one-offs; only instances that genuinely share logic point at the same `apps/` directory. The schema does not model app→{dev,prod} pairs, because the measured `wag-svr-lin01` pair is two unrelated applications.

## Variable resolution

`global_variables`, then `variables` on top. The merged map becomes the container's environment and the substitution source for the flow render.

Two substitution mechanisms, deliberately different in scope:

- **Node-RED `${ENV}`** — replaces a whole property value. Used wherever it suffices.
- **Jinja2 in CI** — for composite strings only (`mqtt-${SITE}/events`), applied to a copy during deploy. The committed flow keeps its literal value so it still opens in the editor.

## Base URL

`host` and `admin_root` are enough. There is no `admin_base_url` field, because `deploy.py` runs on the target host and reaches the instance by container IP on `app_network` — the base is resolved at runtime from the compose service name, not stored per instance (decision 10).

## Scope

Up to 16 entries: 8 site servers, each with a dev and a prod instance. The host names come from the map in the `Jenkinsfile`; `collect-inventory.py` confirms the instance names per host and writes a pre-filled draft.

Instances still running under FlowFuse are **not** entries yet. They join the registry once they have been migrated to plain containers (decision 12); until then the draft carries them as a comment, so the file records that they exist without claiming the pipeline can deploy them.
