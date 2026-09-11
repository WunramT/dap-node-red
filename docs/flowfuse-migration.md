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

## What still has to be measured

- **`tcp in`: server or client.** Twenty nodes across two ports, ten each, named
  after machines (`D300L320116-a`). Ten listeners on one port cannot coexist, so
  they are almost certainly outbound client connections — but "almost certainly"
  decides whether the new container publishes two ports or none, so it gets
  measured, not assumed.
- **`axios` and `ajv` at runtime.** Node-RED installs a function node's external
  modules into the userDir with npm, and a baked image behind a firewall cannot.
  The agent's project carries an `.npmrc`, so an internal registry probably
  exists. Which of the three fixes applies — reachable registry, pre-populated
  `/data/externalModules`, or baked and resolvable — depends on what that file
  says.
- **nginx on both hosts.** Each runs one on `:80`, and `dpn`'s inbound paths have
  to keep working unchanged. That config decides `admin_root`.
- **Names.** Proposed `pod-prod` and `dpn-prod`, each with an empty `-test` twin
  as a workbench, matching the rest of the estate.

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
