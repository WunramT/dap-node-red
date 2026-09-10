#!/usr/bin/env python3
"""Report which instances still match Git. Read-only.

    python3 scripts/drift-check.py --instance gor-prod
    python3 scripts/drift-check.py --all --json inventory/drift.json

It reads. It never writes to an instance, never reconciles, never "fixes" one.
A drift checker that repairs what it finds is decision 3 through the back door:
the browser edit it would flatten is the thing worth keeping.

Same reach constraint as deploy.py — it runs on the target host and finds each
instance through Docker. To sweep from a workstation instead, override the base
per instance, because there is no single answer from outside: some instances sit
behind nginx, some publish a port, some neither.

    NODE_RED_BASE_URL_GOR_PROD=http://gor-svr-lin01:1881

The table in docs/runbook.md lists them.

A difference between an instance and Git has two causes that deserve different
answers, so they get different names:

    behind    the running flow matches an earlier commit of this file. Somebody
              changed the flow in Git and has not deployed it yet — the normal
              state while work is in progress, and it needs a deploy, not a
              decision.
    drifted   the running flow matches no commit. It was edited in the browser,
              which is the case decision 3 exists for: capture it, do not
              overwrite it.

Telling them apart needs the repository, so it only happens where the checkout
is. On a site host, or anywhere git cannot answer, both collapse back to
`drifted` and nothing is claimed that was not checked.

Exit codes: 0 clean or behind, 1 unreachable or unauthorized, 3 drift found.
Drift is only an error where a schedule wants to go red for it, so 3 requires
--fail-on-drift; a pending deploy never does, because nobody bypassed anything.
"""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy import (  # noqa: E402
    ROOT, base_url_for, env_credentials, get_token, load_instances, request, resolve_base,
)
from normalize import normalize, render  # noqa: E402


def committed_versions(app: str, limit: int = 20) -> list[tuple[str, str]]:
    """This flow file as of each recent commit, normalized, newest first.

    Only for telling a pending deploy from a browser edit. Without a repository
    — on a site host — this is empty and the caller says nothing about which of
    the two it is.
    """
    log = subprocess.run(["git", "log", f"-n{limit}", "--format=%H", "--",
                          f"apps/{app}/flows.json"],
                         cwd=ROOT, capture_output=True, text=True)
    if log.returncode != 0:
        return []

    versions = []
    for sha in log.stdout.split():
        blob = subprocess.run(["git", "show", f"{sha}:apps/{app}/flows.json"],
                              cwd=ROOT, capture_output=True, text=True)
        if blob.returncode != 0:
            continue
        try:
            versions.append((sha, render(normalize(json.loads(blob.stdout)))))
        except (json.JSONDecodeError, ValueError):
            continue        # a commit where the file was not yet valid
    return versions


def inspect(inst: dict) -> dict:
    """One instance's state. Never raises for an unreachable instance —
    a sweep that stops at the first dead host reports nothing about the rest."""
    name, app = inst["name"], inst.get("app")
    result = {"instance": name, "host": inst["host"], "app": app,
              "image_tag": inst.get("image_tag")}

    if not app:
        return {**result, "state": "no-app"}

    admin_root = inst.get("admin_root") or ""
    try:
        base = resolve_base(base_url_for(inst), admin_root)
        creds = env_credentials(inst["auth_credential_id"])
        token = get_token(base, admin_root, *creds) if creds else None
        _, payload = request(f"{base}{admin_root}/flows", token=token)
    except SystemExit as exc:
        return {**result, "state": "unreachable", "detail": str(exc).splitlines()[0]}
    except Exception as exc:  # noqa: BLE001 — one bad host must not end the sweep
        # The docstring promises this function never raises for an unreachable
        # instance. SystemExit alone did not keep that promise: anything the
        # network layer raises unwrapped took the whole run down with it.
        return {**result, "state": "unreachable",
                "detail": f"{type(exc).__name__}: {exc}"}

    running = (payload or {}).get("flows", [])
    rev = (payload or {}).get("rev")
    committed = json.loads((ROOT / "apps" / app / "flows.json").read_text(encoding="utf-8"))

    before, after = render(normalize(running)), render(normalize(committed))
    if before == after:
        return {**result, "state": "clean", "rev": rev, "nodes": len(running)}

    diff = [line for line in difflib.unified_diff(
        before.splitlines(), after.splitlines(),
        fromfile=f"running/{name}", tofile=f"git/apps/{app}", lineterm="", n=3)]

    # Does what is running match something that was committed? Then Git moved on
    # and the instance did not: a deploy is pending, nobody edited anything.
    state, detail = "drifted", None
    for sha, version in committed_versions(app):
        if version == before:
            state = "behind"
            detail = f"running commit {sha[:8]}, Git has moved on — a deploy is pending"
            break

    return {
        **result, "state": state, "rev": rev,
        **({"detail": detail} if detail else {}),
        "nodes_running": len(running), "nodes_git": len(committed),
        "changed_lines": sum(1 for line in diff
                             if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))),
        "diff": diff,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    target = ap.add_mutually_exclusive_group(required=True)
    target.add_argument("--instance")
    target.add_argument("--all", action="store_true")
    ap.add_argument("--json", type=Path, help="write the full report, diffs included")
    ap.add_argument("--show-diff", action="store_true", help="print the diff for each drifted instance")
    ap.add_argument("--fail-on-drift", action="store_true",
                    help="exit 3 when anything drifted; for a scheduled check that should go red")
    args = ap.parse_args()

    instances = load_instances()
    if args.instance:
        chosen = [i for i in instances if i.get("name") == args.instance]
        if not chosen:
            raise SystemExit(f"no instance named {args.instance} in registry.yml")
    else:
        chosen = instances

    results = [inspect(i) for i in chosen]

    width = max(len(r["instance"]) for r in results)
    print(f"{'instance':<{width}}  {'state':<11}  detail")
    print("-" * (width + 40))
    for r in results:
        drift_detail = (f"{r.get('changed_lines')} changed lines "
                        f"({r.get('nodes_running')} nodes running, {r.get('nodes_git')} in Git)")
        detail = {
            "clean": lambda: f"{r.get('nodes')} nodes, rev {r.get('rev')}",
            "drifted": lambda: drift_detail,
            "behind": lambda: f"{r.get('detail')} — {drift_detail}",
            "unreachable": lambda: r.get("detail", ""),
            "no-app": lambda: "no flow of its own",
        }[r["state"]]()
        print(f"{r['instance']:<{width}}  {r['state']:<11}  {detail}")

    if args.show_diff:
        for r in results:
            if r["state"] in ("drifted", "behind"):
                print(f"\n{'=' * 70}\n{r['instance']}\n{'=' * 70}")
                print("\n".join(r["diff"]))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.json}")

    counts = {state: sum(1 for r in results if r["state"] == state)
              for state in ("clean", "behind", "drifted", "unreachable", "no-app")}
    print(f"\n{counts['clean']} clean, {counts['behind']} behind, {counts['drifted']} drifted, "
          f"{counts['unreachable']} unreachable, {counts['no-app']} without an app")

    if counts["behind"]:
        print("\n'behind' is work in progress, not a problem: Git holds a newer flow than the\n"
              "instance runs. Deploy it.")
    if counts["drifted"]:
        print("\nDrift is not a failure to repair — it is a browser edit that is not in Git.\n"
              "Capture it: docs/runbook.md, 'On 409'.")
    if counts["unreachable"]:
        return 1
    return 3 if (counts["drifted"] and args.fail_on_drift) else 0


if __name__ == "__main__":
    sys.exit(main())
