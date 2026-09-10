# Go-live plan

From here to the point where the team sees the pipeline live and uses it. As of 2026-09-08.

Where we stand, in one sentence: every building block (registry, normalizer, `apps/`, `deploy.py`, `drift-check.py`, Jenkinsfile) is built and dry-run-verified for **one** instance (`wag-prod`) — but no real `POST /flows` has ever happened, and only for `wag-prod` are the Jenkins credentials demonstrably in place. Background and reasoning: [`architecture.md`](architecture.md), [`decisions.md`](decisions.md), [`open-questions.md`](open-questions.md), [`runbook.md`](runbook.md).

The order is deliberate: look first, then write on the safest candidate, then roll out in breadth. No step skips the one before it.

---

## Phase 0 — Take stock of the whole fleet (no risk)

Read-only. The goal: know which of the 16 instances currently match Git, before anything is written anywhere.

**Done on 2026-09-08** (fleet dry run via Jenkins): 8 clean (`cho-prod`, `cho-test`, `gor-prod`, `gor-test`, `jan-prod`, `jan-test`, `srem-prod`, `wag-prod`), 2 drifted (`srem-test` 1008 lines, `wag-test` 37 lines), `wfm-prod` never reached (the Jenkins credential was missing).

- [ ] Run `drift-check.py --all --json inventory/drift.json` **through Jenkins**, not from a workstation — `srem-prod`, `srem-test` and `slu-prod` publish no port and are only reachable from their host (`runbook.md`, "Reaching an instance from a workstation"). A new, small Jenkins job (like the deploy job, but without the write path) is the right place for it.
- [ ] Record the result per instance: `clean` / `drifted` / `unreachable` / `no-app`.
- [ ] For every `drifted` instance: review the diff (`--show-diff`). Decide per instance — commit it or discard it deliberately (`runbook.md`, "On 409"). Do **not** touch these instances through automation before that decision is made.
- [ ] For every `unreachable` instance: find the cause (missing credential? host not reachable? wrong `admin_root`?).

**Result of this phase:** a table showing where a later first deploy would be a risk-free no-op (`clean`) and where something has to happen first.

---

## Phase 1 — Prove the write path once, for real (candidate: `wfm-test`)

No real `POST /flows` has happened yet — the Jenkins runs were no-ops, because the instances checked were already clean. This is the most important proof still outstanding in the whole project.

`wfm-test` is the right place for it: a new, empty instance on real infrastructure, with a starter flow in Git that touches no foreign system. So the first real deploy genuinely writes something there — and can break nothing. `wag-prod` stays the second candidate once the path is proven.

- [ ] Add `node-red-test` as a second service in `/home/administrator/Base_Container/docker-compose.yml` on `wfm-svr-lin01`: its own bind mount `./node-red-test/data`, port `1881`, otherwise identical to `node-red` (user, TZ, dns_search, dns).
- [ ] Set the data directory to `1004:1004` **with `sudo`** and verify with `ls -ldn`. Without that the instance starts, reads cleanly and dies on the first write — see `runbook.md`, "A new instance's /data must belong to the container user".
- [ ] Set `adminAuth` and `credentialSecret` in its `settings.js` from the start — on a new instance there is nothing to pin, the value is generated once and put into a Jenkins credential.
- [ ] Create the Jenkins credentials `nodered-wfm-test-auth` and `nodered-wfm-test-credsecret`.
- [ ] Dry run: `INSTANCE=wfm-test`, `DRY_RUN=true` → expect a diff covering the 4 nodes of the starter flow (the instance is empty, Git is not). Note the `rev` it prints.
- [ ] **Real deploy:** `DRY_RUN=false`, `EXPECT_REV=<the rev from the dry run>` → expect `deployed (200)`. The flow is then in the editor and the inject node can be triggered by hand.
- [ ] **The `409` proof:** change something in the editor, do **not** commit it, then run the job again with `DRY_RUN=false` and the `EXPECT_REV` from *before* that change → expect the conflict abort, exit 2, nothing overwritten. Taking the rev from the dry run into the deploy is what makes this reachable: without it the deploy reads the current rev and posts against it moments later, so the browser edit sits inside that rev and gets flattened (`runbook.md`, "Flow deploy"). This is the safety proof (decision 3), and it deserves to be seen once for real before colleagues rely on it.

**Result of this phase:** the complete write path (POST, `rev` handshake, conflict abort) is proven live, not just tested.

---

## Phase 2 — Roll out to the remaining `clean` instances

For every instance reported `clean` in phase 0 (8 of the 10 checked), plus `wag-prod` as the first real prod deploy:

- [ ] Run the backup gate (as in phase 1).
- [ ] Pin `credentialSecret`.
- [ ] For `wfm-prod` additionally: turn on `adminAuth` (currently open, `runbook.md` step 2) — it is the one instance with a real security hole, and should be pulled forward rather than left until last.
- [ ] `wfm-test` is new and therefore the actual first candidate: empty instance, real deploy from Git, no production risk. Only then `wfm-prod`.
- [ ] For `cho-prod` additionally: `level: "info"` instead of `"trace"` (decision 13).
- [ ] Create the Jenkins credentials for `auth_credential_id` and `credential_secret_id` where they are still missing — phase 0 should already show that through `unreachable`.
- [ ] One `DRY_RUN=true` per instance as a check, then `DRY_RUN=false`.

Instances that drifted in phase 0 do **not** come along automatically — their turn comes after the deliberate commit-or-discard decision.

---

## Phase 3 — Visibility for everyone (the drift page)

So far `drift-check.py` exists only as a CLI tool. For everyday team use, the static overview page foreseen in `decisions.md` (decision 11) is still missing.

- [ ] Add a CI stage that runs `drift-check.py --all --json` regularly (e.g. daily, a scheduled Jenkins job) and renders the JSON into a simple static HTML page.
- [ ] Publish the page (GitLab Pages or similar) — read-only, no deploy button (deliberately, see decision 11).
- [ ] Shows per instance: Git status (clean/drifted), flow version, image tag, last deploy time.

**This is the point where it can be shown to the team**, without anyone having to operate a CLI: one page, one glance, a clear status per instance.

---

## Phase 4 — Test the palette path once

Only the flow deploy path (no restart) has been tested for real so far. The second transport — image rebuild plus restart — is still entirely unproven.

- [ ] On a test instance (e.g. `wag-test`), make a harmless change to `apps/wag-test/package.json` and commit it.
- [ ] Check that GitLab CI builds and signs a new image.
- [ ] Set `image_tag` in `registry.yml` to the new tag.
- [ ] Run the Jenkins job with `DEPLOY_PALETTE=true`, `DRY_RUN=false` — deliberately outside core hours, because it restarts the container (an ingest gap is expected, see `architecture.md`).

---

## After that: the two things that stay open

These do **not** block "showing it live" — they concern only the 2 FlowFuse instances and 2 empty instances, not the 12 apps already finished:

- **FlowFuse migration** (`pod-svr-lin01`, `dpn-svr-iot`): blocked on the credential key for `flows_cred.json` (open question 1). Its own undertaking, after phase 2.
- **`slu-prod` / `slu-test`**: empty, no decision on what they are for. No `apps/` directory until that is settled.

---

## In short

| Phase | What | Risk | Result |
|---|---|---|---|
| 0 | Drift check across all 16 instances | none (read-only) | **done** — 8 clean, 2 drifted, 1 blocked |
| 1 | Set up `wfm-test`, first real deploy to it | none (new, empty instance) | write path + `409` case proven live |
| 2 | Roll out to all `clean` instances, `wag-prod` first | low, the pattern repeats | all 12 apps run through the pipeline |
| 3 | Static drift page | none | showable to the whole team, without a CLI |
| 4 | Test the palette path once | medium (restart) | second transport proven |

**"Live" in the sense of "can be shown to and used by the team"** is realistically reached after phase 3: real deploys run through the pipeline for every finished instance, and there is a page anyone can read without prior knowledge.
