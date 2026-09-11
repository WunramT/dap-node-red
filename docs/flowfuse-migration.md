# FlowFuse migration

Working document for the two device-agent instances. Measured 2026-09-11.
Delete it once both are cut over, as `wfm-prod-migration.md` was — the parts
that generalize belong in [`runbook.md`](runbook.md).

Direction and order are settled (decision 12, [`architecture.md`](architecture.md)):
copy the flow, stand up the plain container, **unenroll the device**, retire the
agent. The credential key comes across in `device.yml`.

## The two are not the same job

| | `pod-svr-lin01` | `dpn-svr-iot` |
|---|---|---|
| nodes / types / tabs | 154 / 25 / 2 | 852 / 41 / 11 |
| Node-RED | 4.0.8 pinned | `latest`, resolved to 4.0.9 |
| what it talks to | Modbus + TCP to machines, MQTT out | Postgres, MSSQL, MQTT, HTTP APIs on its own host |
| inbound | 20 `tcp in` on ports 50002/50003 | `/dashboard`, `/node_red_api/sap_import_finished`, `/update_tableau_workbooks` |
| function external modules | none | `axios` (6), `ajv` (1) |
| risk if it runs twice | **9 `modbus-write` nodes — it writes to machines** | duplicate rows and mails |

`pod` is the one to do first: fewer nodes, a pinned version, and its palette is
four modules. `dpn` is eleven concerns in one runtime and needs decisions before
it moves.

## Palette, taken from the flow rather than the package.json

FlowFuse installs more than the flow uses. What the image bakes:

- **pod**: `node-red-contrib-modbus`, `node-red-contrib-mssql-plus`,
  `node-red-contrib-postgresql`, `node-red-contrib-buffer-parser`.
  Dropped: `queue-gate` (unused), `@flowfuse/nr-assistant`,
  `@flowfuse/nr-project-nodes` (both unused).
- **dpn**: `@flowfuse/node-red-dashboard`, `node-red-contrib-postgresql`,
  `node-red-contrib-mssql-plus`, `node-red-contrib-queue-gate`,
  `node-red-contrib-google-sheets`, `node-red-node-email`, plus `axios` and
  `ajv` for the function nodes. Dropped: `modbus` and `google-translate`
  (unused), both `@flowfuse/*` platform modules.

Neither flow uses a `project link` node, so nothing routes through FlowFuse's
broker and nothing has to be rebuilt on NATS or MQTT before the cutover. That
was the blocking question; it is answered.

## Networking: nothing to publish but 1880

`pod`'s twenty `tcp in` nodes are all in **client** mode, connecting out to
`zund-cut01`…`zund-cut10` on 50002 and 50003. So the container publishes none of
them; what it needs is name resolution for the ten cutters, which is the
`dns_search` field the registry already carries.

Both agents publish `1880` on their host today, and both hosts' nginx is the
stock configuration — `location /` over `/usr/share/nginx/html`, no `proxy_pass`
in `conf.d`. So the new container takes the same shape: **publish 1880,
`admin_root: ""`**, and `dpn`'s inbound paths (`/dashboard`,
`/node_red_api/sap_import_finished`, `/update_tableau_workbooks`) answer at the
same host and port as before, with no nginx change on either host. The agent
serves its own editor at `/device-editor` with FlowFuse's auth; ours is
`adminAuth` at the root, from a Jenkins credential like every other instance.

## What still has to be measured

- **`axios` and `ajv` in a baked image.** Seven of `dpn`'s function nodes declare
  external modules. Node-RED installs those into the userDir with npm at
  runtime, which a baked image behind a firewall cannot do, and whether modules
  already present in the image satisfy it is not worth guessing. Measure it on
  the workbench before the window: `nr.py edit dpn-test --baked`, a function node
  that requires `axios`, Deploy, read the log.
- **Names.** Proposed `pod-prod` and `dpn-prod`, each with an empty `-test` twin
  as a workbench, matching the rest of the estate.

**The agent's `.npmrc` is not repo content.** It carries a registry credential
for `registry.flowfuse.com`, scoped to `@flowfuse-nodes` — a scope none of the
modules we keep belong to. It is not copied, not committed, and not needed:
`@flowfuse/node-red-dashboard` is a different scope and resolves from the public
registry, which the first CI build confirms.

## Cutover, per instance

1. `docker cp` `flows.json`, `flows_cred.json` and `package.json` out of the
   running agent. Normalize the flow, commit it as `apps/<app>/`.
2. Registry entry, image built by CI, exact tag.
3. **Window.** Stop the agent first — for `pod` this is not about duplicate data,
   it is about two runtimes writing Modbus to the same machines.
4. Stand up the plain container with the `device.yml` key in **both**
   `settings.js` and `/data/.config.runtime.json` (runbook, "Moving an instance
   to a new container").
5. Verify: a stored credential decrypts, inbound paths answer, `nr.py check`
   clean.
6. **Unenroll the device** in FlowFuse, then remove the agent service from its
   compose file. Not just stop it: `restart: always` outlives a stop, and
   `image: latest` with only `device.yml` mounted means one `docker compose pull`
   after the unenroll leaves nothing to recover from.
