# Go-Live-Plan

Von hier bis zu dem Punkt, an dem das Team die Pipeline live sieht und nutzt. Stand: 2026-09-08.

Ausgangslage in einem Satz: Alle Bausteine (Registry, Normalizer, `apps/`, `deploy.py`, `drift-check.py`, Jenkinsfile) sind gebaut und für **eine** Instanz (`wag-prod`) dry-run-verifiziert — aber noch nie hat ein echtes `POST /flows` stattgefunden, und nur für `wag-prod` sind die Jenkins-Credentials nachweislich vorhanden. Hintergrund und Begründungen: [`architecture.md`](architecture.md), [`decisions.md`](decisions.md), [`open-questions.md`](open-questions.md), [`runbook.md`](runbook.md).

Reihenfolge ist absichtlich: erst sehen, dann auf dem sichersten Kandidaten schreiben, dann erst in der Breite ausrollen. Kein Schritt überspringt den davor.

---

## Phase 0 — Bestandsaufnahme über die ganze Flotte (kein Risiko)

Rein lesend. Ziel: wissen, welche der 15 Instanzen aktuell mit Git übereinstimmen, bevor irgendwo geschrieben wird.

- [ ] `drift-check.py --all --json inventory/drift.json` **über Jenkins** laufen lassen, nicht von der Workstation — `srem-prod`, `srem-test` und `slu-prod` haben keinen veröffentlichten Port und sind nur vom Host aus erreichbar (`runbook.md`, "Reaching an instance from a workstation"). Ein neuer, kleiner Jenkins-Job (analog zum Deploy-Job, aber ohne Schreibpfad) ist dafür der richtige Ort.
- [ ] Ergebnis pro Instanz festhalten: `clean` / `drifted` / `unreachable` / `no-app`.
- [ ] Für jede `drifted`-Instanz: Diff sichten (`--show-diff`). Entscheiden pro Instanz — committen oder bewusst verwerfen (`runbook.md`, "On 409"). Diese Instanzen **nicht automatisiert anfassen**, bevor das entschieden ist.
- [ ] Für jede `unreachable`-Instanz: Ursache klären (Credential fehlt? Host nicht erreichbar? `admin_root` falsch?).

**Ergebnis dieser Phase:** eine Tabelle, die zeigt, wo ein späterer erster Deploy ein risikoloses No-Op wäre (`clean`) und wo vorher noch etwas zu tun ist.

---

## Phase 1 — Den Schreibpfad einmal echt beweisen (ein Kandidat: `wag-prod`)

Bisher hat kein reales `POST /flows` stattgefunden — auch die letzten Jenkins-Läufe waren No-Ops, weil `wag-prod` bereits sauber war. Das ist der wichtigste noch offene Beweis im ganzen Projekt.

- [ ] **Backup-Gate für `wag-prod`** durchführen (`runbook.md`, "Backup gate"): `flows.json`, `flows_cred.json`, `.config.runtime.json`, `settings.js`, `package.json` vom Host tar-en und herunterladen. Ohne dieses Backup nichts automatisiert anfassen.
- [ ] **`credentialSecret` pinnen**, falls noch nicht geschehen: generierten Wert aus `.config.runtime.json` lesen, als Jenkins-Credential ablegen (`nodered-wag-prod-credsecret`), in `settings.js` eintragen — **denselben** Wert, nie einen neuen.
- [ ] Einen **trivialen, harmlosen Diff** in `apps/wag-prod/flows.json` erzeugen (z. B. einen deaktivierten Kommentar-Node verschieben oder umbenennen) und committen. Zweck: den Diff bewusst von `0` verschieden machen, damit der reale `POST`-Pfad überhaupt durchlaufen wird.
- [ ] Jenkins-Job mit `DRY_RUN=false` gegen `wag-prod` laufen lassen. Erwartetes Ergebnis: `deployed (200)`, kein Container-Neustart, Flow-Editor zeigt die Änderung.
- [ ] Danach: im Editor jemanden testweise etwas ändern lassen, **ohne** zu committen, und den Job erneut mit `DRY_RUN=false` laufen lassen. Erwartetes Ergebnis: `409 CONFLICT`, Abbruch, keine Überschreibung. Das ist der eigentliche Sicherheitsbeweis (Entscheidung 3) — der gehört einmal wirklich gesehen, bevor Kolleg:innen sich darauf verlassen.

**Ergebnis dieser Phase:** der komplette Schreibpfad (POST, `rev`-Handshake, 409-Abbruch) ist live bewiesen, nicht nur getestet.

---

## Phase 2 — Auf die restlichen `clean`-Instanzen ausrollen

Für jede Instanz, die in Phase 0 als `clean` gemeldet wurde (voraussichtlich der Großteil der 11 mit echtem Flow):

- [ ] Backup-Gate durchführen (wie in Phase 1).
- [ ] `credentialSecret` pinnen.
- [ ] Bei `wfm` zusätzlich: `adminAuth` aktivieren (aktuell offen, `runbook.md` Schritt 2) — das ist die einzige Instanz mit einer echten Sicherheitslücke, sollte vorgezogen werden statt bis zum Schluss zu warten.
- [ ] Bei `cho-prod` zusätzlich: `level: "info"` statt `"trace"` (Entscheidung 13).
- [ ] Jenkins-Credential für `auth_credential_id` und `credential_secret_id` anlegen, sofern noch nicht vorhanden — Phase 0 sollte über `unreachable` bereits zeigen, wo das fehlt.
- [ ] Einmal `DRY_RUN=true` je Instanz zur Kontrolle, dann `DRY_RUN=false`.

Instanzen mit Drift aus Phase 0 laufen **nicht** automatisch mit — die sind erst nach der bewussten Commit/Verwerfen-Entscheidung an der Reihe.

---

## Phase 3 — Sichtbarkeit für alle (die Drift-Seite)

Bisher existiert `drift-check.py` nur als CLI-Tool. Für den Team-Alltag fehlt noch die in `decisions.md` (Entscheidung 11) vorgesehene statische Übersichtsseite.

- [ ] CI-Stufe ergänzen, die `drift-check.py --all --json` regelmäßig laufen lässt (z. B. täglich, geplanter Jenkins-Job) und das JSON in eine einfache statische HTML-Seite rendert.
- [ ] Seite veröffentlichen (GitLab Pages o. ä.) — schreibgeschützt, ohne Deploy-Button (bewusst, siehe Entscheidung 11).
- [ ] Zeigt pro Instanz: Git-Status (clean/drifted), Flow-Version, Image-Tag, letzter Deploy-Zeitpunkt.

**Das ist der Punkt, an dem man es dem Team zeigen kann**, ohne dass jemand eine CLI bedienen muss: eine Seite, ein Blick, klarer Status pro Instanz.

---

## Phase 4 — Palette-Pfad einmal testen

Bisher nur der Flow-Deploy-Pfad (kein Restart) real getestet. Der zweite Transport — Image-Rebuild + Neustart — ist noch komplett unbewiesen.

- [ ] Auf einer Test-Instanz (z. B. `wag-test`) eine harmlose Änderung an `apps/wag-test/package.json` vornehmen, committen.
- [ ] Prüfen, dass GitLab CI ein neues Image baut und signiert.
- [ ] `image_tag` in `registry.yml` auf den neuen Tag setzen.
- [ ] Jenkins-Job mit `DEPLOY_PALETTE=true`, `DRY_RUN=false` laufen lassen — bewusst außerhalb der Kernarbeitszeit, weil das den Container neu startet (Ingest-Lücke erwartet, siehe `architecture.md`).

---

## Danach: die zwei Dinge, die weiterhin offen bleiben

Diese blockieren **nicht** das "live zeigen" — sie betreffen nur die 2 FlowFuse-Instanzen bzw. 2 leere Instanzen, nicht die 11 bereits fertigen Apps:

- **FlowFuse-Migration** (`pod-svr-lin01`, `dpn-svr-iot`): blockiert auf dem Credential-Key für `flows_cred.json` (offene Frage 1). Eigenes Vorhaben, nach Phase 2.
- **`slu-prod` / `slu-test`**: leer, keine Entscheidung, wofür sie genutzt werden. Kein `apps/`-Verzeichnis, bis das geklärt ist.

---

## Kurz zusammengefasst

| Phase | Was | Risiko | Ergebnis |
|---|---|---|---|
| 0 | Drift-Check über alle 15 Instanzen | keins (lesend) | Weiß, wo was ansteht |
| 1 | Backup + Secret-Pin + erster echter Deploy auf `wag-prod` | gering, ein Kandidat, abgesichert | Schreibpfad + 409-Fall live bewiesen |
| 2 | Rollout auf alle `clean`-Instanzen | gering, Muster wiederholt sich | Alle 11 Apps laufen über die Pipeline |
| 3 | Statische Drift-Seite | keins | Zeigbar fürs ganze Team, ohne CLI |
| 4 | Palette-Pfad einmal testen | mittel (Neustart) | Zweiter Transport bewiesen |

**"Live" im Sinne von "kann dem Team gezeigt und genutzt werden"** ist realistisch nach Phase 3 erreicht: reale Deploys laufen für alle fertigen Instanzen über die Pipeline, und es gibt eine Seite, die jeder ohne Vorwissen lesen kann.
