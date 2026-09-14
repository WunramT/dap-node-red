#!/usr/bin/env python3
"""Move plaintext secrets out of a flow and into the container's environment.

    python3 scripts/secrets-to-env.py apps/dpn-prod/flows.json            # report
    python3 scripts/secrets-to-env.py apps/dpn-prod/flows.json --write    # rewrite

Some nodes keep their password in `flows.json` rather than in the credential
store — `node-red-contrib-postgresql` is the one this estate hit — so the value
is committed, readable by anyone with the repository, and permanent in history.
Rotating is the only fix for what is already there; this is what stops it coming
back on the next commit.

Those fields are TypedInputs: a value plus a `<field>FieldType` sibling saying
how to read it. Setting the type to `env` makes the value an environment
variable NAME, so Git carries the name and the host carries the secret. Fields
with no such sibling cannot be switched and are reported instead of guessed at.

Values are never printed, not even truncated. Fields holding the same secret are
grouped under one variable, which is read off the values themselves rather than
assumed from the connection.

The variables belong in the host's compose file, next to that instance's other
host-side configuration — NOT in `registry.yml`, whose `variables` map is
committed. Same rule as `credentialSecret` in `settings.js`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import normalize, render  # noqa: E402

SECRET = re.compile(r"pass|pwd|secret|token|apikey|api_key", re.I)
# Already safe: the value is a variable name or a key into the credential store.
SAFE_TYPES = ("env", "cred")


def candidates(flows: list[dict]) -> list[tuple[dict, str]]:
    """Every node field that looks like a secret and holds something."""
    found = []
    for node in flows:
        if not isinstance(node, dict):
            continue
        for field, value in sorted(node.items()):
            if field.endswith("FieldType") or not SECRET.search(field):
                continue
            if isinstance(value, str) and value and node.get(f"{field}FieldType") not in SAFE_TYPES:
                found.append((node, field))
    return found


def variable_name(node: dict, field: str, taken: dict[str, str], value: str) -> str:
    """A readable, stable name — shared by fields holding the same secret.

    Identity comes from the value, not from the host and user, because two
    configs pointing at one database may still carry different logins and only
    the values know.
    """
    digest = hashlib.sha256(value.encode()).hexdigest()
    if digest in taken:
        return taken[digest]
    stem = re.sub(r"[^A-Za-z0-9]+", "_", node.get("name") or node.get("type") or "node").strip("_")
    name = f"{stem}_{field}".upper()
    if name in taken.values():
        name = f"{name}_{len([v for v in taken.values() if v.startswith(name)]) + 1}"
    taken[digest] = name
    return name


def plan(flows: list[dict]) -> tuple[list[dict], list[dict]]:
    """What can be switched to env, and what has to be handled by hand."""
    convertible, manual, taken = [], [], {}
    for node, field in candidates(flows):
        entry = {"id": node["id"], "type": node.get("type"), "name": node.get("name") or node["id"],
                 "field": field}
        if f"{field}FieldType" in node:
            entry["variable"] = variable_name(node, field, taken, node[field])
            convertible.append(entry)
        else:
            manual.append(entry)
    return convertible, manual


def apply(flows: list[dict], convertible: list[dict]) -> list[dict]:
    by_id = {n["id"]: n for n in flows if isinstance(n, dict)}
    for entry in convertible:
        node = by_id[entry["id"]]
        node[entry["field"]] = entry["variable"]
        node[f"{entry['field']}FieldType"] = "env"
    return flows


def report(convertible: list[dict], manual: list[dict], written: bool) -> str:
    lines = []
    if convertible:
        verb = "switched to env" if written else "can be switched to env"
        lines.append(f"{len(convertible)} field(s) {verb}:\n")
        width = max(len(e["name"]) for e in convertible)
        for e in convertible:
            lines.append(f"    {e['type']:<18} {e['name']:<{width}}  {e['field']:<10} -> ${e['variable']}")
        names = sorted({e["variable"] for e in convertible})
        lines.append(f"\n{len(names)} variable(s). They belong in that instance's service in the")
        lines.append("host's compose file, never in registry.yml, which is committed:\n")
        lines.append("    environment:")
        for name in names:
            lines.append(f"      - {name}=")
    else:
        lines.append("No field to switch.")
    if manual:
        lines.append(f"\n{len(manual)} field(s) carry no <field>FieldType, so they have no env form")
        lines.append("and are left alone. Move them into the node's credentials in the editor:\n")
        for e in manual:
            lines.append(f"    {e['type']:<18} {e['name']}  {e['field']}")
    if convertible or manual:
        lines.append("\nWhatever was committed is in history and stays there. Rotate every")
        lines.append("secret above; switching the field is what keeps the next one out.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("flow", type=Path)
    ap.add_argument("--write", action="store_true", help="rewrite the flow in place")
    args = ap.parse_args()

    flows = json.loads(args.flow.read_text(encoding="utf-8"))
    if not isinstance(flows, list):
        sys.exit(f"{args.flow}: a flows.json is a JSON array of nodes")

    convertible, manual = plan(flows)
    if args.write and convertible:
        args.flow.write_text(render(normalize(apply(flows, convertible))), encoding="utf-8")
    print(report(convertible, manual, args.write))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
