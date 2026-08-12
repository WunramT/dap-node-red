#!/usr/bin/env python3
"""Collect everything the deployment scaffold still needs to know, over SSH.

Read-only. It runs `docker inspect` and reads files; it changes nothing on any
host and touches no container state.

Secrets never leave the host. credentialSecret, adminAuth and anything that
looks like a password, token or bcrypt hash is masked before a settings.js is
written to disk, hashed or printed. flows_cred.json and .config.runtime.json
are never downloaded — only their existence is reported.

Usage
-----
    pip install paramiko
    cp scripts/collect-inventory.py scripts/collect-inventory.local.py
    # fill in HOSTS in the copy — *.local.py is gitignored
    python3 scripts/collect-inventory.local.py

Credentials may also live in a gitignored hosts.local.json next to this file:

    [{"name": "wag-svr-lin01", "ip": "10.60.1.198", "user": "...", "password": "..."}]

which takes precedence over the HOSTS list below. Use `key_file` instead of
`password` for key auth.

Outputs
-------
    inventory/<host>.json                     raw facts per host
    inventory/settings/<instance>.settings.js masked settings.js
    inventory/REPORT.md                       the answers, human-readable
    samples/<instance>.flows.json             real flows, for normalize.py
    registry.draft.yml                        pre-filled registry.yml
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import sys
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIG — fill this in, in your gitignored *.local.py copy.
# ---------------------------------------------------------------------------

HOSTS = [
    {"name": "cho-svr-lin01",  "ip": "10.11.1.101",   "user": "", "password": ""},
    {"name": "pod-svr-lin01",  "ip": "10.20.1.160",   "user": "", "password": ""},
    {"name": "jan-svr-lin01",  "ip": "10.30.1.150",   "user": "", "password": ""},
    {"name": "srem-svr-lin01", "ip": "10.40.1.161",   "user": "", "password": ""},
    {"name": "wag-svr-lin01",  "ip": "10.60.1.198",   "user": "", "password": ""},
    {"name": "foi-svr-lnx01",  "ip": "192.168.64.60", "user": "", "password": ""},
    {"name": "gor-svr-lin01",  "ip": "10.87.1.150",   "user": "", "password": ""},
    {"name": "slu-svr-lin02",  "ip": "10.90.1.20",    "user": "", "password": ""},
]

SSH_PORT = 22
TIMEOUT = 20

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / "inventory"
SAMPLES = ROOT / "samples"

# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

SECRET_KEYS = "credentialSecret|password|pass|secret|token|apiKey|api_key|key"
_SECRET_ASSIGN = re.compile(
    rf"""(?P<head>\b({SECRET_KEYS})\b\s*[:=]\s*)(?P<q>["'])(?P<val>[^"']*)(?P=q)""",
    re.IGNORECASE,
)
_BCRYPT = re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}")


def mask_secrets(text: str) -> str:
    """Replace secret values with a length-preserving marker.

    Keeps the fact that a value exists (and whether it changed length),
    discards the value itself.
    """
    out = _SECRET_ASSIGN.sub(
        lambda m: f"{m.group('head')}{m.group('q')}<masked:{len(m.group('val'))}>{m.group('q')}",
        text,
    )
    return _BCRYPT.sub("<masked:bcrypt>", out)


# Per-instance by nature — masked as well, so the grouping answers
# "is it the same file apart from the fields that must differ".
_PER_INSTANCE = re.compile(
    r"""(?P<head>\b(httpAdminRoot|httpNodeRoot|uiPort|uiHost|flowFile|userDir)\b\s*[:=]\s*)"""
    r"""(?P<q>["'])(?P<val>[^"']*)(?P=q)""",
    re.IGNORECASE,
)


def mask_per_instance(text: str) -> str:
    return _PER_INSTANCE.sub(lambda m: f"{m.group('head')}{m.group('q')}<per-instance>{m.group('q')}", text)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Flow normalization — a preview of normalize.py, used here to compare
# instances against each other.
# ---------------------------------------------------------------------------

POSITIONAL = ("x", "y", "z", "w", "h")


def normalize_flow(nodes: list) -> list:
    out = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        clean = {k: v for k, v in node.items() if k not in POSITIONAL}
        out.append(dict(sorted(clean.items())))
    return sorted(out, key=lambda n: str(n.get("id", "")))


def flow_signature(nodes: list) -> str:
    """Identity of the flow's logic, ignoring ids and layout.

    Two instances running the same application produce the same signature
    even though every node id differs.
    """
    shape = sorted(
        (str(n.get("type", "")), str(n.get("name", "")))
        for n in nodes
        if isinstance(n, dict)
    )
    return sha(json.dumps(shape))


# ---------------------------------------------------------------------------
# SSH
# ---------------------------------------------------------------------------

class Remote:
    def __init__(self, cfg):
        import paramiko

        self.name = cfg["name"]
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs = dict(
            hostname=cfg.get("ip") or cfg["name"],
            port=cfg.get("port", SSH_PORT),
            username=cfg["user"],
            timeout=TIMEOUT,
            banner_timeout=TIMEOUT,
            auth_timeout=TIMEOUT,
        )
        if cfg.get("key_file"):
            kwargs["key_filename"] = cfg["key_file"]
        else:
            kwargs["password"] = cfg["password"]
            kwargs["look_for_keys"] = False
        self.client.connect(**kwargs)
        self.sftp = self.client.open_sftp()

    def run(self, cmd: str) -> str:
        _, stdout, _ = self.client.exec_command(cmd, timeout=TIMEOUT)
        return stdout.read().decode("utf-8", "replace").strip()

    def read(self, container: str, mount: str, filename: str) -> str | None:
        """Read a /data file, preferring the bind mount, falling back to exec."""
        if mount:
            try:
                with self.sftp.open(f"{mount}/{filename}") as fh:
                    return fh.read().decode("utf-8", "replace")
            except IOError:
                pass
        out = self.run(f"docker exec {container} cat /data/{filename} 2>/dev/null")
        return out or None

    def close(self):
        try:
            self.sftp.close()
            self.client.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Per-host collection
# ---------------------------------------------------------------------------

SETTINGS_FIELDS = {
    "httpAdminRoot": r"""httpAdminRoot\s*:\s*["']([^"']*)["']""",
    "flowFile": r"""flowFile\s*:\s*["']([^"']*)["']""",
    "functionExternalModules": r"""functionExternalModules\s*:\s*(true|false)""",
    "flowFilePretty": r"""flowFilePretty\s*:\s*(true|false)""",
}

SETTINGS_PRESENT = ("credentialSecret", "adminAuth", "contextStorage")


def collect_host(cfg) -> dict:
    host = {"host": cfg["name"], "instances": [], "error": None}
    remote = None
    try:
        remote = Remote(cfg)
        host["fqdn"] = remote.run("hostname -f")

        names = [
            n for n in remote.run(
                "docker ps -a --format '{{.Names}}'"
            ).splitlines() if re.search(r"node.?red", n, re.I)
        ]

        # Every service sharing a compose file with Node-RED — the blast
        # radius of a bare `docker compose up -d`.
        host["compose_neighbours"] = {}

        for name in names:
            raw = remote.run(f"docker inspect {name}")
            try:
                info = json.loads(raw)[0]
            except Exception:
                host["instances"].append({"name": name, "error": "docker inspect failed"})
                continue

            cfg_ = info.get("Config", {})
            hostcfg = info.get("HostConfig", {})
            labels = cfg_.get("Labels") or {}
            nets = info.get("NetworkSettings", {}).get("Networks", {}) or {}

            mount = next(
                (m.get("Source") for m in info.get("Mounts", [])
                 if m.get("Destination") == "/data"),
                "",
            )
            compose_file = labels.get("com.docker.compose.project.config_files", "")

            inst = {
                "name": name,
                "host": cfg["name"],
                "image": cfg_.get("Image"),
                "image_pinned": bool(cfg_.get("Image")) and ":" in str(cfg_.get("Image"))
                                and not str(cfg_.get("Image")).endswith((":latest", ":main", ":master")),
                "state": info.get("State", {}).get("Status"),
                "restart_policy": hostcfg.get("RestartPolicy", {}).get("Name"),
                "published_ports": hostcfg.get("PortBindings") or {},
                "dns_search": hostcfg.get("DnsSearch") or [],
                "networks": sorted(nets),
                "ip": next((v.get("IPAddress") for v in nets.values() if v.get("IPAddress")), ""),
                "compose_project": labels.get("com.docker.compose.project"),
                "compose_service": labels.get("com.docker.compose.service"),
                "compose_file": compose_file,
                "data_mount": mount,
            }

            if compose_file and compose_file not in host["compose_neighbours"]:
                host["compose_neighbours"][compose_file] = sorted(set(
                    remote.run(
                        "docker ps -a "
                        f"--filter 'label=com.docker.compose.project.config_files={compose_file}' "
                        "--format '{{index .Labels \"com.docker.compose.service\"}}'"
                    ).split()
                ))

            # --- settings.js -------------------------------------------------
            settings = remote.read(name, mount, "settings.js")
            if settings:
                masked = mask_secrets(settings)
                inst["settings"] = {
                    "hash_exact": sha(masked),
                    "hash_ignoring_per_instance": sha(mask_per_instance(masked)),
                    "bytes": len(settings),
                }
                for field, pattern in SETTINGS_FIELDS.items():
                    m = re.search(pattern, settings)
                    inst["settings"][field] = m.group(1) if m else None
                for field in SETTINGS_PRESENT:
                    inst["settings"][f"{field}_set"] = bool(
                        re.search(rf"^\s*{field}\s*:", settings, re.M)
                    )
                (INV / "settings").mkdir(parents=True, exist_ok=True)
                (INV / "settings" / f"{cfg['name']}__{name}.settings.js").write_text(masked)
            else:
                inst["settings"] = None

            # --- flows.json --------------------------------------------------
            flows_raw = remote.read(name, mount, inst.get("settings", {}).get("flowFile") or "flows.json") \
                if inst.get("settings") else remote.read(name, mount, "flows.json")
            if flows_raw:
                try:
                    nodes = json.loads(flows_raw)
                    norm = normalize_flow(nodes)
                    inst["flows"] = {
                        "bytes": len(flows_raw),
                        "nodes": len(nodes),
                        "normalized_hash": sha(json.dumps(norm, sort_keys=True)),
                        "signature": flow_signature(nodes),
                        "external_modules": sorted({
                            n["module"] for n in nodes
                            if isinstance(n, dict) and n.get("module")
                        }),
                        "node_types": len({
                            n.get("type") for n in nodes if isinstance(n, dict)
                        }),
                    }
                    SAMPLES.mkdir(parents=True, exist_ok=True)
                    (SAMPLES / f"{cfg['name']}__{name}.flows.json").write_text(flows_raw)
                except json.JSONDecodeError as exc:
                    inst["flows"] = {"error": f"unparseable: {exc}"}
            else:
                inst["flows"] = None

            # --- package.json ------------------------------------------------
            pkg = remote.read(name, mount, "package.json")
            if pkg:
                try:
                    inst["palette"] = json.loads(pkg).get("dependencies", {})
                except json.JSONDecodeError:
                    inst["palette"] = {"error": "unparseable"}
            else:
                inst["palette"] = {}

            # --- credential files: existence only ------------------------------
            for f in ("flows_cred.json", ".config.runtime.json"):
                probe = f"test -f '{mount}/{f}'" if mount else f"docker exec {name} test -f /data/{f}"
                inst[f.strip('.').replace('.', '_')] = remote.run(f"{probe} && echo yes || echo no") == "yes"

            # --- Admin API reachability from the host -------------------------
            root = (inst.get("settings") or {}).get("httpAdminRoot") or ""
            if inst["ip"]:
                url = f"http://{inst['ip']}:1880{root.rstrip('/')}/flows"
                code = remote.run(
                    f"curl -s -o /dev/null -m 5 -w '%{{http_code}}' '{url}' || echo 000"
                )
                inst["admin_api"] = {"url": url, "http_code": code}

            host["instances"].append(inst)

    except Exception as exc:
        host["error"] = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    finally:
        if remote:
            remote.close()
    return host


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def build_report(hosts: list) -> str:
    instances = [i for h in hosts for i in h["instances"] if not i.get("error")]
    L = []
    add = L.append

    add("# Inventory report\n")
    add(f"{len(instances)} instances across {len([h for h in hosts if not h['error']])} reachable hosts.\n")

    failed = [h for h in hosts if h["error"]]
    if failed:
        add("## Unreachable hosts\n")
        for h in failed:
            add(f"- **{h['host']}** — {h['error']}")
        add("")

    # --- Q1: settings.js ---------------------------------------------------
    add("## Q1 — Are the settings.js files the same file?\n")
    groups: dict[str, list] = {}
    for i in instances:
        if i.get("settings"):
            groups.setdefault(i["settings"]["hash_ignoring_per_instance"], []).append(i)
    if len(groups) == 1:
        add("**One group.** Every settings.js is identical once httpAdminRoot, flowFile, "
            "uiPort/uiHost and the secret values are set aside.\n")
        add("→ One template in the repo plus env overrides.\n")
    else:
        add(f"**{len(groups)} groups.** The files differ beyond the per-instance fields.\n")
        add("→ Each difference needs reconciling; see the diffs below.\n")
    for idx, (h, members) in enumerate(sorted(groups.items(), key=lambda kv: -len(kv[1])), 1):
        add(f"- group {idx} (`{h}`, {len(members)}): " +
            ", ".join(f"{m['host']}/{m['name']}" for m in members))
    add("")

    if len(groups) > 1:
        add("### Diffs between group representatives\n")
        reps = [members[0] for _, members in sorted(groups.items(), key=lambda kv: -len(kv[1]))]
        base = reps[0]
        base_txt = (INV / "settings" / f"{base['host']}__{base['name']}.settings.js").read_text()
        for other in reps[1:]:
            other_txt = (INV / "settings" / f"{other['host']}__{other['name']}.settings.js").read_text()
            diff = list(difflib.unified_diff(
                mask_per_instance(base_txt).splitlines(),
                mask_per_instance(other_txt).splitlines(),
                fromfile=f"{base['host']}/{base['name']}",
                tofile=f"{other['host']}/{other['name']}",
                lineterm="", n=2,
            ))
            add(f"<details><summary>{base['host']}/{base['name']} vs "
                f"{other['host']}/{other['name']} — {len(diff)} diff lines</summary>\n")
            add("```diff")
            L.extend(diff[:200])
            if len(diff) > 200:
                add(f"... {len(diff) - 200} more lines")
            add("```\n</details>\n")

    add("### Per-instance fields\n")
    add("| instance | httpAdminRoot | dns_search | credentialSecret | adminAuth | contextStorage |")
    add("|---|---|---|---|---|---|")
    for i in sorted(instances, key=lambda x: (x["host"], x["name"])):
        s = i.get("settings") or {}
        add(f"| {i['host']}/{i['name']} | `{s.get('httpAdminRoot')}` | "
            f"{', '.join(i['dns_search']) or '—'} | "
            f"{'set' if s.get('credentialSecret_set') else 'GENERATED'} | "
            f"{'on' if s.get('adminAuth_set') else 'off'} | "
            f"{'on' if s.get('contextStorage_set') else 'off'} |")
    add("")

    # --- Q4/Q5: flows -------------------------------------------------------
    add("## Q4/Q5 — Flow sizes, and which instances share logic\n")
    add("| instance | nodes | bytes | node types | palette | own npm modules |")
    add("|---|---|---|---|---|---|")
    for i in sorted(instances, key=lambda x: (x["host"], x["name"])):
        f = i.get("flows") or {}
        pal = ", ".join(sorted(i.get("palette", {}))) or "—"
        ext = ", ".join(f.get("external_modules", [])) or "—"
        add(f"| {i['host']}/{i['name']} | {f.get('nodes', '?')} | {f.get('bytes', '?')} | "
            f"{f.get('node_types', '?')} | {pal} | {ext} |")
    add("")

    sigs: dict[str, list] = {}
    for i in instances:
        if (i.get("flows") or {}).get("signature"):
            sigs.setdefault(i["flows"]["signature"], []).append(i)
    shared = {s: m for s, m in sigs.items() if len(m) > 1}
    if shared:
        add("Instances running the same logic (matching node type/name multiset, ids and layout ignored):\n")
        for s, members in shared.items():
            add(f"- `{s}`: " + ", ".join(f"{m['host']}/{m['name']}" for m in members))
        add("\n→ Each group becomes one `apps/<name>/` directory.\n")
    else:
        add("No two instances share a flow signature — every instance is a one-off, "
            "so every instance gets its own `apps/` directory or `app: null`.\n")

    ext_users = [i for i in instances if (i.get("flows") or {}).get("external_modules")]
    add(f"Function nodes declaring their own npm module: "
        f"{'NONE — the baked image is a real guarantee' if not ext_users else 'FOUND, see table above'}\n")

    # --- transport ----------------------------------------------------------
    add("## Admin API reachability from the host\n")
    add("401 = reachable and adminAuth active. 200 = reachable, auth off. 000 = unreachable.\n")
    add("| instance | url | code |")
    add("|---|---|---|")
    for i in sorted(instances, key=lambda x: (x["host"], x["name"])):
        a = i.get("admin_api") or {}
        add(f"| {i['host']}/{i['name']} | `{a.get('url', '—')}` | **{a.get('http_code', '—')}** |")
    add("")

    # --- images and compose --------------------------------------------------
    add("## Image tags and compose blast radius\n")
    add("| instance | image | pinned | restart | published ports | compose service | compose file |")
    add("|---|---|---|---|---|---|---|")
    for i in sorted(instances, key=lambda x: (x["host"], x["name"])):
        add(f"| {i['host']}/{i['name']} | `{i['image']}` | "
            f"{'yes' if i['image_pinned'] else '**NO**'} | {i['restart_policy']} | "
            f"{i['published_ports'] or 'none'} | {i['compose_service']} | `{i['compose_file']}` |")
    add("")
    for h in hosts:
        for f, services in (h.get("compose_neighbours") or {}).items():
            others = [s for s in services if s and not re.search(r"node.?red", s, re.I)]
            if others:
                add(f"- `{h['host']}:{f}` also holds: {', '.join(others)} "
                    f"— a bare `docker compose up -d` recreates these")
    add("")

    add("## Not answerable from the hosts\n")
    add("- **Harbor project for Node-RED images.** Whether a `dap-nodered` project exists "
        "and which GitLab CI variable holds its push credential is a Harbor/GitLab question.\n")
    return "\n".join(L)


def build_registry_draft(hosts: list) -> str:
    L = ["# Generated by scripts/collect-inventory.py — review before use.",
         "# Credential ids and image tags are placeholders.",
         "",
         "global_variables: {}",
         "",
         "instances:"]
    for h in hosts:
        for i in h["instances"]:
            if i.get("error"):
                continue
            s = i.get("settings") or {}
            L += [
                f"  - name: {i['name']}",
                f"    host: {h['host']}",
                f"    app: null",
                f"    admin_root: {s.get('httpAdminRoot') or '/'}",
                f"    auth_credential_id: CHANGEME-{h['host']}-{i['name']}-auth",
                f"    credential_secret_id: CHANGEME-{h['host']}-{i['name']}-credsecret",
                f"    dns_search: [{', '.join(i['dns_search'])}]",
                f"    image_tag: CHANGEME  # currently running {i['image']}",
                f"    variables: {{}}",
            ]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------

def main():
    try:
        import paramiko  # noqa: F401
    except ImportError:
        sys.exit("paramiko is missing — run: pip install paramiko")

    local = ROOT / "hosts.local.json"
    targets = json.loads(local.read_text()) if local.exists() else HOSTS
    targets = [t for t in targets if t.get("user") and (t.get("password") or t.get("key_file"))]
    if not targets:
        sys.exit("No credentials configured — fill in HOSTS or create hosts.local.json.")

    INV.mkdir(parents=True, exist_ok=True)
    results = []
    for cfg in targets:
        print(f"[{cfg['name']}] connecting ...", flush=True)
        host = collect_host(cfg)
        n = len([i for i in host["instances"] if not i.get("error")])
        print(f"[{cfg['name']}] {'ERROR: ' + host['error'] if host['error'] else f'{n} instances'}", flush=True)
        (INV / f"{cfg['name']}.json").write_text(json.dumps(host, indent=2, sort_keys=True))
        results.append(host)

    (INV / "REPORT.md").write_text(build_report(results))
    (ROOT / "registry.draft.yml").write_text(build_registry_draft(results))

    print(f"\nWrote:\n  {INV / 'REPORT.md'}\n  {ROOT / 'registry.draft.yml'}"
          f"\n  {SAMPLES}/ ({len(list(SAMPLES.glob('*.json'))) if SAMPLES.exists() else 0} flow files)")
    print("\nSend me inventory/REPORT.md.")


if __name__ == "__main__":
    main()
