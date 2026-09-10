#!/usr/bin/env python3
"""One entry point for the day-to-day work. Pick an instance, pick an action.

    python3 scripts/nr.py                      # menu
    python3 scripts/nr.py status               # every instance, one table
    python3 scripts/nr.py check    wag-prod
    python3 scripts/nr.py edit     wag-prod
    python3 scripts/nr.py edit     gor-prod --baked      # editor with that app's palette
    python3 scripts/nr.py edit     srem-test --isolated  # editor with no way out
    python3 scripts/nr.py capture  wag-prod
    python3 scripts/nr.py deploy   wag-prod    # dry run; it never deploys for real
    python3 scripts/nr.py promote  wfm-prod wfm-test "Extruder abfrage" --copy
    python3 scripts/nr.py promote  wfm-test wfm-prod "Extruder abfrage" --move

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
import hashlib
import json
import os
import re
import shutil
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
    "promote": "move one tab between two instances' apps, with its dependencies",
}


def instances() -> list[dict]:
    sys.path.insert(0, str(ROOT / "scripts"))
    from deploy import load_instances
    return load_instances()


def registry_source() -> str:
    """Which file the list came from, for an error message that can be acted on."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import deploy
    return deploy.LOADED_FROM.name if deploy.LOADED_FROM else "the registry"


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


def run(argv: list[str], env: dict | None = None) -> int:
    print(f"\n$ {' '.join(argv)}\n")
    try:
        return subprocess.run(argv, cwd=ROOT, env=env).returncode
    except FileNotFoundError:
        # Windows raises WinError 2 here, which arrives as a traceback ten
        # frames deep and says nothing about which program is missing.
        sys.exit(f"{argv[0]} is not on PATH, so this action cannot run.")


SESSION = ROOT / ".editor-session"


def stage_session(app: str) -> tuple[str, dict[str, bool], list[str]]:
    """Copy the app's flow into a session directory, every tab disabled.

    The editor writes flows.json wherever /data is mounted, so mounting
    apps/<app>/ directly means the local run and the committed file are the
    same thing — and then switching a tab off to work safely would be a change
    on its way to an instance. Staging a copy keeps the two apart.
    """
    flows = json.loads((ROOT / "apps" / app / "flows.json").read_text(encoding="utf-8"))
    was = {n["id"]: bool(n.get("disabled", False)) for n in flows if n.get("type") == "tab"}
    labels = []
    for node in flows:
        if node.get("type") == "tab":
            node["disabled"] = True
            labels.append(node.get("label") or node["id"])

    directory = SESSION / app
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "flows.json").write_text(json.dumps(flows, indent=2) + "\n", encoding="utf-8")
    return f".editor-session/{app}", was, labels


def stage_dns(app: str, search: list[str]) -> str | None:
    """A compose override carrying the instance's search domains.

    Flows address their targets the way their own host resolves them, and some
    do it unqualified — wfm-prod's broker is plain `dpn-svr-iot`. A normal
    network is not enough for that: without the instance's dns_search the name
    does not resolve, and the node goes red for a reason that looks like the
    broker being down.

    They differ per instance and compose cannot interpolate a list, so this is
    written next to the staged flow rather than parameterised in editor.yml.
    """
    if not search:
        return None
    body = ["services:", "  editor:", "    dns_search:"]
    body += [f"      - {domain}" for domain in search]
    path = SESSION / app / "dns.yml"
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return f".editor-session/{app}/dns.yml"


def session_digest(app: str) -> str | None:
    """Fingerprint of the session's flow, to tell "the editor wrote" from "it never ran".

    A compose run that fails — an image it cannot pull, a port already taken —
    leaves the staged copy exactly as staged. Merging that back is harmless,
    because the merge restores every tab's state from Git and lands on the same
    bytes, but reporting it as "copied back" points the reader at a diff that
    does not exist while the actual failure scrolls past above.
    """
    h = hashlib.sha256()
    seen = False
    for name in ("flows.json", "package.json"):
        f = SESSION / app / name
        if f.exists():
            h.update(f.read_bytes())
            seen = True
    return h.hexdigest() if seen else None


def merge_session(app: str, was: dict[str, bool]) -> list[str]:
    """Bring the session's flow back, restoring what Git said about each tab.

    A tab that existed before keeps the disabled state from Git, whatever it
    was switched to locally — that switching is how you work here, not
    something to deploy. A tab you added is new, so it keeps its own state.
    """
    staged = SESSION / app / "flows.json"
    if not staged.exists():
        return []

    flows = json.loads(staged.read_text(encoding="utf-8"))

    # If /data did not mount, Node-RED starts on an empty userDir and writes a
    # flow with nothing in it — and copying that back would delete the app.
    # An editor showing no tabs at all is that failure, not an empty app: the
    # staged copy always has at least the tabs the app has.
    if was and not any(n.get("type") == "tab" for n in flows):
        sys.exit(
            f"the session for {app} came back with no tabs, and the app has "
            f"{len(was)}.\n"
            "  Nothing was written. The editor was almost certainly looking at an\n"
            "  empty directory — the mount did not land, which on podman for\n"
            "  Windows usually means the path is not shared into the machine.\n"
            f"  The session is still there: .editor-session/{app}/flows.json"
        )

    added = []
    for node in flows:
        if node.get("type") != "tab":
            continue
        if node["id"] in was:
            node["disabled"] = was[node["id"]]
        else:
            added.append(node.get("label") or node["id"])

    sys.path.insert(0, str(ROOT / "scripts"))
    from normalize import normalize, render
    (ROOT / "apps" / app / "flows.json").write_text(render(normalize(flows)), encoding="utf-8")
    return added


def installed_version(app: str, module: str) -> str | None:
    """The version npm actually put in the session, read off the module itself."""
    manifest = SESSION / app / "node_modules" / module / "package.json"
    if not manifest.exists():
        return None
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("version")
    except json.JSONDecodeError:
        return None


def merge_palette(app: str) -> list[str]:
    """Carry a module installed through "Manage palette" into the app's palette.

    That install runs npm in the session's /data, so the module is real and
    resolved — and invisible to everything else: the session directory is
    gitignored and only flows.json was ever copied out of it. Writing it into
    apps/<app>/package.json is what ships it, and the version it resolved beats
    one typed from memory.

    Additive on purpose. The baked palette lives in the image, not under /data,
    so a name missing from the session means "already in the image", never
    "removed" — a two-way sync would empty the manifest on the first session.
    """
    session_pkg = SESSION / app / "package.json"
    app_pkg = ROOT / "apps" / app / "package.json"
    if not (session_pkg.exists() and app_pkg.exists()):
        return []
    try:
        installed = json.loads(session_pkg.read_text(encoding="utf-8")).get("dependencies") or {}
    except json.JSONDecodeError:
        return []

    manifest = json.loads(app_pkg.read_text(encoding="utf-8"))
    deps = dict(manifest.get("dependencies") or {})
    added = []
    for module, declared in sorted(installed.items()):
        if module in deps:
            continue
        # A range would make the built image drift from the one tested here.
        exact = installed_version(app, module) or declared.lstrip("^~>=< ")
        deps[module] = exact
        added.append(f"{module}@{exact}")

    if added:
        manifest["dependencies"] = dict(sorted(deps.items()))
        app_pkg.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return added


def bump_palette_tag(instance: str) -> tuple[str, str] | None:
    """Raise the palette-build suffix of one instance's image_tag.

    A new palette means a new image, and the image the deploy pins is named in
    registry.yml — so the two belong in the same commit. Left to a human this
    is the step that gets forgotten, and forgetting it is not cosmetic: CI
    builds on a package.json change and pushes the tag registry.yml names, so
    an unchanged tag is rebuilt with different content underneath. A pinned tag
    whose content moves is worse than no pin, because nothing reports it.

    Edited as text, not through PyYAML, which would drop every comment in the
    file — including the ones that record why each version is what it is.
    """
    reg = ROOT / "registry.yml"
    text = reg.read_text(encoding="utf-8")
    block = re.search(rf"^  - name: {re.escape(instance)}$.*?(?=^  - name: |\Z)",
                      text, re.S | re.M)
    if not block:
        return None
    line = re.search(r"^(\s+image_tag:\s*)(\S+)(.*)$", block.group(0), re.M)
    if not line:
        return None

    old_tag = line.group(2)
    head, sep, suffix = old_tag.rpartition("-")
    if not sep or not suffix.isdigit():
        return None
    new_tag = f"{head}-{int(suffix) + 1}"

    edited = block.group(0).replace(line.group(0),
                                    f"{line.group(1)}{new_tag}{line.group(3)}", 1)
    reg.write_text(text.replace(block.group(0), edited, 1), encoding="utf-8")
    return old_tag, new_tag


def compose_cmd(instance: str) -> list[str]:
    """`docker compose` or `podman compose`, whichever this machine has.

    The repository's own convention is podman on a workstation and Docker on the
    servers (docs/copilot-instructions.md), so hard-coding docker made `edit`
    the one action that failed on exactly the machines it exists for.
    """
    engine = os.environ.get("CONTAINER_ENGINE")
    if engine:
        return [engine, "compose"]
    for candidate in ("docker", "podman"):
        if shutil.which(candidate):
            return [candidate, "compose"]
    sys.exit(
        "The local editor needs a container engine, and neither docker nor\n"
        "  podman is on PATH. Set CONTAINER_ENGINE if yours is called something\n"
        "  else. It is the only action that needs one: status, check, capture\n"
        "  and deploy talk to the Admin API and need nothing but Python.\n"
        "\n"
        "  For a test instance the other route is the intended one anyway —\n"
        "  edit in that instance's own editor, then bring the change back:\n"
        f"      python3 scripts/nr.py capture {instance}\n"
        "  See docs/runbook.md, 'Changing a flow', route B.\n"
        "\n"
        "  An engine inside WSL is not enough: this runs as a Windows process\n"
        "  and needs the .exe on the Windows PATH."
    )


def act(action: str, inst: dict | None, cfg: dict, baked: bool = False,
        isolated: bool = False) -> int:
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
        compose = compose_cmd(inst["name"])
        data, was, labels = stage_session(inst["app"])
        print(f"\nEditor for {inst['name']} -> {data}/ (a copy, not apps/{inst['app']}/)\n"
              f"Open http://localhost:1880 once it starts, then Ctrl-C to finish.\n"
              f"\n"
              f"{len(labels)} tab(s) arrive DISABLED: {', '.join(labels) or '—'}\n"
              f"Enable the one you want to work on, or add a new tab. Only what you\n"
              f"enable runs — and it runs for real, against real systems.\n"
              f"\n"
              f"On Ctrl-C the flow is copied into apps/{inst['app']}/flows.json with each\n"
              f"existing tab's disabled state restored from Git, so the switching stays\n"
              f"local. Review it with git diff.\n")
        # Inside a dev container the docker daemon is the host's, so the bind
        # mount must name a host path. LOCAL_WORKSPACE_FOLDER is what the dev
        # container sets to that path; outside one it is unset and the compose
        # file falls back to its own relative path.
        env = {**os.environ, "APP": inst["app"]}
        if os.environ.get("LOCAL_WORKSPACE_FOLDER"):
            env["REPO_ROOT"] = os.environ["LOCAL_WORKSPACE_FOLDER"]

        # The registry pins each instance to the Node-RED version it runs, and
        # the editor has to match it: a 5.x editor writes fields a 4.0.x runtime
        # does not know, into a file that is meant to deploy unchanged.
        # harbor.example/dap-node-red/wfm-prod:4.0.9-1 -> 4.0.9
        version = inst["image_tag"].rsplit(":", 1)[1].rsplit("-", 1)[0]
        env["NODE_RED_VERSION"] = version
        if baked:
            # That app's own image, so its palette nodes open as themselves
            # rather than as "unknown". Needs a docker login to Harbor.
            env["EDITOR_IMAGE"] = inst["image_tag"]
        env["EDITOR_DATA"] = data
        files = ["-f", "compose/editor.yml"]
        if isolated:
            env["EDITOR_NETWORK"] = "isolated"
        else:
            # Pointless with no gateway, so only for the networked default.
            override = stage_dns(inst["app"], inst.get("dns_search") or [])
            if override:
                files += ["-f", override]
                print(f"search domains: {', '.join(inst['dns_search'])}")
        print(f"editor image:   {env.get('EDITOR_IMAGE', 'nodered/node-red:' + version)}")
        print(f"editor network: {env.get('EDITOR_NETWORK', 'bridged')}"
              f"{'  (no route out)' if isolated else '  (databases and brokers reachable)'}\n")
        staged = session_digest(inst["app"])
        code = None
        try:
            code = run([*compose, *files, "up"], env)
            return code
        finally:
            # Also on Ctrl-C, which is the normal way to end an editor session.
            if session_digest(inst["app"]) == staged:
                print(f"\nthe editor wrote no flow, so apps/{inst['app']}/flows.json is "
                      f"untouched.")
                if code:
                    registry = inst["image_tag"].split("/", 1)[0]
                    print(f"  The compose run above failed. 'unauthorized ... action: pull'\n"
                          f"  is a missing registry login, and the login belongs to the engine\n"
                          f"  that pulls — which is this one, whatever the compose provider is\n"
                          f"  called: `{compose[0]} compose` points the provider at its own\n"
                          f"  socket, so 'Error response from daemon' can be {compose[0]}\n"
                          f"  answering through the Docker-compatible API.\n"
                          f"    {compose[0]} login {registry}\n"
                          f"  Then confirm the image is reachable before retrying:\n"
                          f"    {compose[0]} pull {inst['image_tag']}")
            else:
                added = merge_session(inst["app"], was)
                print(f"\ncopied back into apps/{inst['app']}/flows.json"
                      f"{' — new tab(s) kept as you left them: ' + ', '.join(added) if added else ''}")
                print(f"  git diff apps/{inst['app']}/flows.json")
                palette = merge_palette(inst["app"])
                if palette:
                    print(f"\npalette: {', '.join(palette)} written into "
                          f"apps/{inst['app']}/package.json, pinned to what you installed.")
                    bumped = bump_palette_tag(inst["name"])
                    if bumped:
                        print(f"  image_tag: {bumped[0].rsplit('/', 1)[-1]} -> "
                              f"{bumped[1].rsplit('/', 1)[-1]} in registry.yml, so CI builds a\n"
                              f"  new tag instead of replacing the one this instance runs.")
                    else:
                        print(f"  image_tag for {inst['name']} does not end in -<number>, so the\n"
                              f"  palette build could not be raised. Do it by hand before pushing:\n"
                              f"  CI pushes the tag registry.yml names, and an unchanged tag gets\n"
                              f"  rebuilt with different content.")
                    print(f"  A flow deploy installs nothing, so this needs the other transport:\n"
                          f"  commit both, let CI build, then deploy with DEPLOY_PALETTE=true.\n"
                          f"  docs/runbook.md, 'Palette change'.")

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

    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    known = {"--baked", "--isolated", "--copy", "--move", "--dry-run"}
    if flags - known:
        sys.exit(f"unknown option(s): {', '.join(sorted(flags - known))}. "
                 f"Understood: {', '.join(sorted(known))}, and only for edit.")

    action = argv[0] if argv else None
    if action and action not in ACTIONS:
        sys.exit(f"unknown action '{action}'. One of: {', '.join(ACTIONS)}")
    if not action:
        action = choose("What do you want to do?", list(ACTIONS.items()))

    if action == "status":
        return act(action, None, cfg)

    if action == "promote":
        # Two instances and a tab, so the instance picker does not fit. The
        # instance names are the vocabulary everywhere else, so they are the
        # vocabulary here too, and this translates them to app directories.
        if len(argv) < 4:
            sys.exit("usage: nr.py promote <from-instance> <to-instance> <tab> "
                     "--copy|--move [--dry-run]\n"
                     "  --copy for prod -> workbench, --move for workbench -> prod.\n"
                     "  See docs/runbook.md, 'Changing a flow'.")
        apps = {}
        for name in argv[1:3]:
            inst = next((i for i in all_instances if i["name"] == name), None)
            if inst is None:
                sys.exit(f"no instance named {name} in {registry_source()}")
            if not inst.get("app"):
                sys.exit(f"{name} has no app of its own, so there is nothing to promote")
            apps[name] = inst["app"]
        return run([PY, "scripts/promote.py",
                    "--from", apps[argv[1]], "--to", apps[argv[2]], "--tab", argv[3],
                    *sorted(flags & {"--copy", "--move", "--dry-run"})])

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
        sys.exit(f"no instance named {name} in {registry_source()}.\n"
                 f"  Known: {', '.join(i['name'] for i in all_instances)}")
    return act(action, inst, cfg, baked="--baked" in flags,
               isolated="--isolated" in flags)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(130)
