#!/usr/bin/env python3
"""One entry point for the day-to-day work. Pick an instance, pick an action.

    python3 scripts/nr.py                      # menu
    python3 scripts/nr.py status               # every instance, one table
    python3 scripts/nr.py check    wag-prod
    python3 scripts/nr.py edit     wag-prod
    python3 scripts/nr.py capture  wag-prod
    python3 scripts/nr.py deploy   wag-prod    # dry run; it never deploys for real

This exists so the instance list lives in exactly one place. A menu with the
thirteen names typed into it would be a second copy of `registry.yml`, and the
copy would go stale the first time an instance is added.

Where each instance answers from a workstation, and the login for it, come from
a gitignored `nr.local.json`. Copy `nr.local.example.json` and fill it in. A
password left out is asked for at the prompt and is not stored.

`deploy` is deliberately dry-run only. A real deploy is a reviewed commit that
Jenkins carries out — a local script that can write to production would make
that reviewable path optional.
"""

from __future__ import annotations

import getpass
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "nr.local.json"
PY = sys.executable

ACTIONS = {
    "status":  "every instance at once: does it still match Git?",
    "check":   "one instance: does it still match Git?",
    "edit":    "start the local editor on this app (isolated, no live nodes)",
    "capture": "read the running flow back into apps/, to commit it",
    "deploy":  "show what a deploy would change; never deploys for real",
}


def instances() -> list[dict]:
    sys.path.insert(0, str(ROOT / "scripts"))
    from deploy import load_instances
    return load_instances()


def local_config() -> dict:
    """Read nr.local.json, tolerating the // header the example file carries.

    Without this the example file is a trap: copying it as instructed produces
    a file that json.loads rejects.
    """
    if not LOCAL.exists():
        return {}
    text = "\n".join(line for line in LOCAL.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("//"))
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        sys.exit(f"{LOCAL.name} is not valid JSON: {exc}")


def build_env(inst: dict, cfg: dict, need_password: bool) -> dict:
    """The base URL and login for one instance, as deploy.py expects them."""
    env = dict(os.environ)
    entry = cfg.get(inst["name"], {})

    url = entry.get("url")
    if not url:
        sys.exit(f"{inst['name']}: no url in nr.local.json.\n"
                 f"  Copy nr.local.example.json and fill it in — the table in\n"
                 f"  docs/runbook.md lists where each instance answers.")
    env[f"NODE_RED_BASE_URL_{re.sub(r'[^A-Za-z0-9]', '_', inst['name']).upper()}"] = url

    if need_password:
        stem = re.sub(r"[^A-Za-z0-9]", "_", inst["auth_credential_id"]).upper()
        user = entry.get("user")
        password = entry.get("password") or (
            getpass.getpass(f"password for {inst['name']} ({user or 'admin'}): ")
            if user else None)
        if user and password:
            env[f"{stem}_USR"], env[f"{stem}_PSW"] = user, password
    return env


def compose_command() -> list[str] | None:
    """Whatever can run a compose file here — docker or podman, plugin or not.

    The dev container may be provisioned by either, and by podman more often
    than not on Windows, where VS Code drives it through WSL.
    """
    for candidate in (["docker", "compose"], ["podman", "compose"],
                      ["docker-compose"], ["podman-compose"]):
        probe = subprocess.run([*candidate, "version"],
                               capture_output=True, text=True)
        if probe.returncode == 0:
            return candidate
    return None


def host_path(path: str) -> str:
    """A path the container engine can resolve.

    VS Code sets LOCAL_WORKSPACE_FOLDER to the path as the *editor* sees it. On
    Windows that is `c:\\Users\\...`, which podman running under WSL cannot open —
    WSL sees the same directory at /mnt/c/Users/... So translate, and leave a
    POSIX path alone.
    """
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", path)
    if not m:
        return path
    drive, rest = m.group(1).lower(), m.group(2).replace("\\", "/")
    return f"/mnt/{drive}/{rest}"


def run(argv: list[str], env: dict | None = None) -> int:
    print(f"\n$ {' '.join(argv)}\n")
    return subprocess.run(argv, cwd=ROOT, env=env).returncode


def act(action: str, inst: dict | None, cfg: dict) -> int:
    if action == "status":
        env = dict(os.environ)
        for i in instances():
            if not i.get("app"):
                continue
            entry = cfg.get(i["name"], {})
            if entry.get("url"):
                env.update(build_env(i, cfg, need_password=bool(entry.get("password"))))
        return run([PY, "scripts/drift-check.py", "--all"], env)

    assert inst is not None
    if action == "edit":
        if not inst.get("app"):
            sys.exit(f"{inst['name']} has no app — there is no flow to edit. "
                     f"See open question 3 in docs/open-questions.md.")
        print(f"\nEditor for {inst['name']} -> apps/{inst['app']}/\n"
              f"Open http://localhost:1880 once it starts. Press Deploy to write\n"
              f"apps/{inst['app']}/flows.json. Stop it with Ctrl-C.\n"
              f"No credentials, no name resolution, safe mode — see compose/editor.yml.\n")
        # Inside a dev container the container engine is the host's, so the
        # bind mount must name a path that engine can resolve. Outside one,
        # LOCAL_WORKSPACE_FOLDER is unset and the compose file falls back to
        # its own relative path.
        env = {**os.environ, "APP": inst["app"]}
        workspace = os.environ.get("LOCAL_WORKSPACE_FOLDER")
        if workspace:
            env["REPO_ROOT"] = host_path(workspace)

        compose = compose_command()
        if not compose:
            print(f"No container engine is reachable from here.\n\n"
                  f"Run the editor from a host terminal instead:\n\n"
                  f"    cd {host_path(workspace) if workspace else '<repo>'}\n"
                  f"    APP={inst['app']} docker compose -f compose/editor.yml up\n\n"
                  f"Then open http://localhost:1880.", file=sys.stderr)
            return 1
        return run([*compose, "-f", "compose/editor.yml", "up"], env)

    env = build_env(inst, cfg, need_password=True)
    script = {"check": "drift-check.py", "capture": "capture.py", "deploy": "deploy.py"}[action]
    args = [PY, f"scripts/{script}", "--instance", inst["name"]]
    if action == "check":
        args.append("--show-diff")
    if action in ("capture", "deploy"):
        args.append("--dry-run")
    code = run(args, env)

    if action == "capture" and code == 0:
        if input("\nwrite it into apps/ for real? [y/N] ").strip().lower() == "y":
            code = run([PY, "scripts/capture.py", "--instance", inst["name"]], env)
    return code


def choose(prompt: str, options: list[tuple[str, str]]) -> str:
    print(f"\n{prompt}")
    for n, (key, label) in enumerate(options, 1):
        print(f"  {n:2}  {key:<12} {label}")
    while True:
        raw = input("\n> ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        if raw in {k for k, _ in options}:
            return raw
        print("Pick a number from the list, or type the name.")


def main() -> int:
    cfg = local_config()
    all_instances = instances()
    argv = sys.argv[1:]

    action = argv[0] if argv else None
    if action and action not in ACTIONS:
        sys.exit(f"unknown action '{action}'. One of: {', '.join(ACTIONS)}")
    if not action:
        action = choose("What do you want to do?", list(ACTIONS.items()))

    if action == "status":
        return act(action, None, cfg)

    name = argv[1] if len(argv) > 1 else None
    if not name:
        options = [
            (i["name"], f"{i['host']:<16} {'app: ' + i['app'] if i.get('app') else 'no app — empty'}"
                        f"{'' if cfg.get(i['name'], {}).get('url') else '   [no url in nr.local.json]'}")
            for i in all_instances
        ]
        name = choose("Which instance?", options)

    inst = next((i for i in all_instances if i["name"] == name), None)
    if not inst:
        sys.exit(f"no instance named {name} in registry.yml")
    return act(action, inst, cfg)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(130)
