#!/usr/bin/env python3
"""Tests for promote.py. Run: python3 scripts/test_promote.py

Promotion decides what of a workbench reaches production and what of production
keeps running, so the cases that matter are the ones where it must NOT act: a
config node the destination already has, a subflow other tabs there use, and a
source that has to keep serving.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "promote.py"
A, B = ROOT / "apps" / "wfm-prod" / "flows.json", ROOT / "apps" / "wfm-test" / "flows.json"
FAILED = []


def check(label, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}{'  ' + detail if detail and not condition else ''}")
    if not condition:
        FAILED.append(label)


def run(*args):
    out = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
    return out.returncode, out.stdout + out.stderr


def flows(path):
    return json.loads(path.read_text(encoding="utf-8"))


def ids(path):
    return {n["id"] for n in flows(path)}


def tab_of(path, label):
    return next((n for n in flows(path) if n.get("type") == "tab" and n.get("label") == label), None)


print("promote.py")
keep_a, keep_b = A.read_bytes(), B.read_bytes()
try:
    # --- the direction that must not touch the source ---------------------
    code, out = run("--from", "wfm-prod", "--to", "wfm-test", "--tab", "Extruder abfrage", "--copy")
    check("copy succeeds", code == 0, out)
    check("the tab arrives in the destination", tab_of(B, "Extruder abfrage") is not None)
    check("and prod keeps it — it is still running there", tab_of(A, "Extruder abfrage") is not None)
    check("prod is otherwise untouched", flows(A) == json.loads(keep_a.decode()))

    moved = tab_of(B, "Extruder abfrage")
    check("it arrives disabled on the workbench", moved.get("disabled") is True,
          str(moved.get("disabled")))
    check("and says so", "arrives DISABLED" in out, out)
    on_tab = [n for n in flows(B) if n.get("z") == moved["id"]]
    check("its nodes come along", len(on_tab) == 6, str(len(on_tab)))
    check("so do the config nodes it names",
          {"893b283917e01492", "a01e8aa09521f824"} <= ids(B))
    check("the workbench's own tab is left alone", tab_of(B, "Pipeline-Test") is not None)

    # --- a destination config node is never overwritten --------------------
    b = flows(B)
    for node in b:
        if node["id"] == "893b283917e01492":
            node["broker"] = "mosquitto-test"          # the workbench's own broker
    B.write_text(json.dumps(b, indent=2) + "\n", encoding="utf-8")

    code, out = run("--from", "wfm-prod", "--to", "wfm-test", "--tab", "Extruder abfrage", "--copy")
    broker = next(n for n in flows(B) if n["id"] == "893b283917e01492")
    check("a second promotion keeps the destination's broker",
          broker.get("broker") == "mosquitto-test", broker.get("broker"))
    check("and says so", "keeps wfm-test's own config node" in out, out)
    check("the tab is replaced, not duplicated",
          len([n for n in flows(B) if n.get("type") == "tab" and n.get("label") == "Extruder abfrage"]) == 1)

    # --- shipping back clears the workbench -------------------------------
    code, out = run("--from", "wfm-test", "--to", "wfm-prod", "--tab", "Extruder abfrage", "--move")
    check("move succeeds", code == 0, out)
    check("the workbench loses the tab", tab_of(B, "Extruder abfrage") is None)
    check("and its nodes with it",
          not [n for n in flows(B) if n.get("z") == moved["id"]])
    check("the workbench keeps its config node for next time", "893b283917e01492" in ids(B))
    shipped = tab_of(A, "Extruder abfrage")
    check("prod has it", shipped is not None)
    check("and it arrives enabled there", shipped.get("disabled") is False,
          str(shipped.get("disabled")))
    check("deploy order is spelled out", "Deploy wfm-test first" in out, out)

    # --- guard rails ------------------------------------------------------
    code, out = run("--from", "wfm-test", "--to", "wfm-test", "--tab", "Pipeline-Test", "--copy")
    check("refuses the same app twice", code != 0 and "same app" in out)

    code, out = run("--from", "wfm-prod", "--to", "wfm-test", "--tab", "no-such-tab", "--copy")
    check("names the tabs it does have", code != 0 and "Present:" in out, out)

    code, out = run("--from", "wfm-prod", "--to", "wfm-test", "--tab", "Flow 1")
    check("refuses without --copy or --move", code != 0 and "--copy --move" in out, out)
finally:
    A.write_bytes(keep_a)
    B.write_bytes(keep_b)

print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
sys.exit(1 if FAILED else 0)
