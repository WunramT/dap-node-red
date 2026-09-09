#!/usr/bin/env python3
"""Tests for the editor session in nr.py. Run: python3 scripts/test_nr.py

The session is a copy of an app's flow with every tab disabled, and on exit it
is merged back. That merge is the part worth testing: it decides what of a local
session reaches the repository, and getting it wrong either loses an edit or
deploys a disabled tab to an instance.
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import nr  # noqa: E402

APP = "wfm-test"
LIVE = ROOT / "apps" / APP / "flows.json"
FAILED = []


def check(label, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}{'  ' + detail if detail and not condition else ''}")
    if not condition:
        FAILED.append(label)


def tabs(flows):
    return {n["id"]: n for n in flows if n.get("type") == "tab"}


def staged_flows():
    return json.loads((nr.SESSION / APP / "flows.json").read_text(encoding="utf-8"))


def write_staged(flows):
    (nr.SESSION / APP / "flows.json").write_text(json.dumps(flows, indent=2) + "\n", encoding="utf-8")


print("nr.py editor session")
original_bytes = LIVE.read_bytes()
try:
    # --- staging ----------------------------------------------------------
    data, was, labels = nr.stage_session(APP)
    check("session directory is not the app directory", data == f".editor-session/{APP}", data)
    check("the app file is untouched by staging", LIVE.read_bytes() == original_bytes)

    original = json.loads(original_bytes.decode("utf-8"))
    check("every tab arrives disabled",
          all(t["disabled"] for t in tabs(staged_flows()).values()) and len(labels) == len(tabs(original)))
    check("nothing else is dropped", len(staged_flows()) == len(original))

    # --- merge with no changes -------------------------------------------
    nr.merge_session(APP, was)
    check("an untouched session leaves the app file byte-identical",
          LIVE.read_bytes() == original_bytes)

    # --- a tab enabled locally, and a node edited ------------------------
    nr.stage_session(APP)
    flows = staged_flows()
    tab_id = next(iter(tabs(flows)))
    tabs(flows)[tab_id]["disabled"] = False              # what you do to work on it
    for node in flows:
        if node.get("type") == "debug":
            node["name"] = "Ergebnis, umbenannt"
    write_staged(flows)
    nr.merge_session(APP, was)

    merged = json.loads(LIVE.read_text(encoding="utf-8"))
    check("the tab's disabled state comes back from Git",
          tabs(merged)[tab_id]["disabled"] == was[tab_id], str(tabs(merged)[tab_id]["disabled"]))
    check("the edit inside the tab survives",
          any(n.get("name") == "Ergebnis, umbenannt" for n in merged))

    # --- a tab added locally ---------------------------------------------
    nr.stage_session(APP)
    flows = staged_flows()
    flows.append({"id": "aaaa1111bbbb2222", "type": "tab", "label": "Neu", "disabled": False, "info": ""})
    write_staged(flows)
    added = nr.merge_session(APP, was)

    merged = tabs(json.loads(LIVE.read_text(encoding="utf-8")))
    check("a new tab is kept", "aaaa1111bbbb2222" in merged)
    check("and keeps its own enabled state", merged.get("aaaa1111bbbb2222", {}).get("disabled") is False)
    check("and is reported to the caller", added == ["Neu"], str(added))

    # --- a tab deleted locally -------------------------------------------
    nr.stage_session(APP)
    flows = [n for n in staged_flows() if n.get("id") != "aaaa1111bbbb2222"]
    write_staged(flows)
    nr.merge_session(APP, was)
    check("a deleted tab stays deleted",
          "aaaa1111bbbb2222" not in tabs(json.loads(LIVE.read_text(encoding="utf-8"))))

    # --- a tab that Git says is disabled ---------------------------------
    nr.stage_session(APP)
    flows = staged_flows()
    tabs(flows)[tab_id]["disabled"] = False
    write_staged(flows)
    nr.merge_session(APP, {tab_id: True})
    check("a tab Git has disabled stays disabled",
          tabs(json.loads(LIVE.read_text(encoding="utf-8")))[tab_id]["disabled"] is True)
    # --- the mount did not land ------------------------------------------
    nr.stage_session(APP)
    write_staged([])                                     # what an empty /data yields
    before = LIVE.read_bytes()
    try:
        nr.merge_session(APP, was)
        check("an empty session is refused, not copied back", False, "no SystemExit")
    except SystemExit as exc:
        check("an empty session is refused, not copied back", "no tabs" in str(exc))
    check("and the app file is untouched by the refusal", LIVE.read_bytes() == before)
finally:
    LIVE.write_bytes(original_bytes)
    shutil.rmtree(nr.SESSION, ignore_errors=True)

print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
sys.exit(1 if FAILED else 0)
