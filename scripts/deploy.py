#!/usr/bin/env python3
"""Deploy a flow to a Node-RED instance through the Admin API.

    python3 scripts/deploy.py --instance wag-prod --dry-run
    python3 scripts/deploy.py --instance wag-prod

Runs **on the target host** — Jenkins ships it over SSH and executes it there,
because port publishing is inconsistent across the estate and the site servers
sit in separate subnets (decision 10). From the host it finds the instance by
asking Docker for the container's address.

Standard library only, on purpose: the site hosts are not guaranteed to have
pip, and a deploy script that needs installing is a deploy script that fails at
3am.

Credentials come from the environment, named after the ids in registry.yml —
Jenkins injects them from its credential store and they are never read from a
file (decision 7):

    <auth_credential_id>_USR   /  <auth_credential_id>_PSW

with `-` replaced by `_` and the whole name upper-cased. So a registry entry
naming `nodered-wag-prod-auth` reads NODERED_WAG_PROD_AUTH_USR and _PSW.

A `409` from POST aborts, always. It means the running flow diverged from Git —
someone edited in the browser — and overwriting that edit destroys work and
teaches everyone that the pipeline eats what they do. There is no --force, and
adding one would undo decision 3. Recovery is in docs/runbook.md.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import normalize, render  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 30


# --------------------------------------------------------------------------
# The instance list
#
# registry.yml is YAML, and PyYAML is not guaranteed on a site host. Rather
# than hand-parse it — a parser that is wrong in one edge case deploys the
# wrong flow to the wrong instance — CI emits registry.json beside it and
# Jenkins ships that along with this script.
# --------------------------------------------------------------------------

# Set by load_instances, so an error message can name the file it actually read
# rather than the file the reader assumes.
LOADED_FROM: Path | None = None


def load_instances() -> list[dict]:
    """The instance list, from registry.yml where that is possible.

    registry.json is the copy Jenkins ships to a site host, because PyYAML is
    not guaranteed there. It is a transport artifact, not a cache: it is
    generated, gitignored, and can be older than the registry beside it.

    Reading it first therefore made a stale copy in a working tree shadow the
    real registry without a word — `nr.py check wfm-test` reported that an
    instance plainly present in registry.yml did not exist. So the YAML wins
    wherever it can be read, and the JSON is the fallback it was meant to be.
    """
    global LOADED_FROM
    as_yaml, as_json = ROOT / "registry.yml", ROOT / "registry.json"

    if as_yaml.exists():
        try:
            import yaml
        except ImportError:
            yaml = None
        if yaml is not None:
            LOADED_FROM = as_yaml
            return yaml.safe_load(as_yaml.read_text(encoding="utf-8"))["instances"]

    if as_json.exists():
        LOADED_FROM = as_json
        return json.loads(as_json.read_text(encoding="utf-8"))["instances"]

    raise SystemExit(
        "Neither registry.yml with PyYAML nor registry.json is available.\n"
        "Generate the JSON where PyYAML exists:\n"
        "  python3 scripts/validate-registry.py --emit-json"
    )


# --------------------------------------------------------------------------
# Target resolution
# --------------------------------------------------------------------------

def container_url(service: str) -> str:
    """Where the instance answers, asked of Docker rather than assumed."""
    out = subprocess.run(
        ["docker", "inspect", "-f",
         "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}", service],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise SystemExit(f"docker inspect {service}: {out.stderr.strip()}")
    ip = out.stdout.split()
    if not ip:
        raise SystemExit(f"{service} has no container address — is it running?")
    return f"http://{ip[0]}:1880"


def env_var(prefix: str, name: str) -> str:
    return f"{prefix}_{re.sub(r'[^A-Za-z0-9]', '_', name).upper()}"


def base_url_for(inst: dict) -> str:
    """Where to reach this instance.

    On the host — where the pipeline runs — Docker answers, and every instance
    is at the container address on 1880. From a workstation there is no single
    answer: some instances sit behind nginx, some publish a port, some neither.
    So a per-instance override comes first, which is what makes a sweep across
    the estate possible before Jenkins exists.

        NODE_RED_BASE_URL_GOR_PROD=http://gor-svr-lin01:1881
        NODE_RED_BASE_URL=http://one-host-for-everything   # fallback
    """
    return (os.environ.get(env_var("NODE_RED_BASE_URL", inst["name"]))
            or os.environ.get("NODE_RED_BASE_URL")
            or container_url(inst["compose_service"]))


def env_credentials(credential_id: str) -> tuple[str, str] | None:
    stem = re.sub(r"[^A-Za-z0-9]", "_", credential_id).upper()
    user, password = os.environ.get(f"{stem}_USR"), os.environ.get(f"{stem}_PSW")
    return (user, password) if user and password else None


# --------------------------------------------------------------------------
# Admin API
# --------------------------------------------------------------------------

def resolve_base(base: str, admin_root: str) -> str:
    """The base URL, with the admin root removed if it was pasted in.

    NODE_RED_BASE_URL is the host, and the admin root comes from registry.yml —
    but the URL a human has in their browser is the two already joined, so
    pasting that is the obvious mistake and doubling the root yields a 404 that
    explains nothing.
    """
    base = base.rstrip("/")
    if admin_root and base.endswith(admin_root):
        stripped = base[: -len(admin_root)]
        print(f"note: NODE_RED_BASE_URL already ends in {admin_root!r}, which "
              f"registry.yml supplies — using {stripped}")
        return stripped
    return base


def request(url: str, *, method="GET", body=None, token=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    # v1 returns a bare array with no rev, which would make the conflict check
    # impossible. v2 returns {rev, flows}.
    req.add_header("Node-RED-API-Version", "v2")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            payload = response.read()
            return response.status, (json.loads(payload) if payload else None)
    except urllib.error.HTTPError as exc:
        # 409 is a real answer the caller handles; everything else is reported
        # with the URL, because a bare status tells nobody what was called.
        if exc.code == 409:
            raise
        raise SystemExit(
            f"{method} {url} -> {exc.code} {exc.reason}\n"
            + {401: "  The credentials were rejected, or adminAuth expects a different user.",
               404: "  Nothing answers on that path. Check admin_root in registry.yml against "
                    "the instance, and that NODE_RED_BASE_URL is the host only.",
               }.get(exc.code, f"  {exc.read()[:300].decode('utf-8', 'replace')}")
        ) from None
    except urllib.error.URLError as exc:
        raise SystemExit(f"{method} {url} -> unreachable: {exc.reason}") from None


def get_token(base: str, admin_root: str, user: str, password: str) -> str:
    _, data = request(f"{base}{admin_root}/auth/token", method="POST", body={
        "client_id": "node-red-admin",
        "grant_type": "password",
        "scope": "*",
        "username": user,
        "password": password,
    })
    token = (data or {}).get("access_token")
    if not token:
        raise SystemExit("auth/token returned no access_token")
    return token


# --------------------------------------------------------------------------

def deploy(inst: dict, dry_run: bool) -> int:
    name = inst["name"]
    app = inst.get("app")
    if not app:
        print(f"{name}: no app — nothing to deploy")
        return 0

    flow_file = ROOT / "apps" / app / "flows.json"
    desired = json.loads(flow_file.read_text(encoding="utf-8"))

    admin_root = inst.get("admin_root") or ""
    base = resolve_base(base_url_for(inst), admin_root)
    print(f"{name}: {base}{admin_root}/flows")

    token = None
    creds = env_credentials(inst["auth_credential_id"])
    if creds:
        token = get_token(base, admin_root, *creds)
    else:
        # wfm-prod has adminAuth switched off, so there is nothing to authenticate
        # against until that is fixed (decision 13). Say so rather than failing
        # silently into an unauthenticated deploy.
        print(f"{name}: no credentials in the environment for "
              f"{inst['auth_credential_id']} — continuing unauthenticated")

    status, current = request(f"{base}{admin_root}/flows", token=token)
    rev = (current or {}).get("rev")
    running = (current or {}).get("flows", [])
    if rev is None:
        raise SystemExit(f"{name}: GET /flows returned no rev (status {status}) — "
                         "the instance may predate the v2 Admin API")

    before = render(normalize(running))
    after = render(normalize(desired))

    if before == after:
        print(f"{name}: already up to date ({len(desired)} nodes)")
        return 0

    diff = list(difflib.unified_diff(
        before.splitlines(), after.splitlines(),
        fromfile=f"running/{name}", tofile=f"git/apps/{app}", lineterm="", n=3,
    ))
    changed = sum(1 for line in diff if line.startswith(("+", "-"))
                  and not line.startswith(("+++", "---")))
    print(f"{name}: {changed} changed lines, rev {rev}")

    if dry_run:
        print("\n".join(diff))
        return 0

    try:
        status, _ = request(
            f"{base}{admin_root}/flows", method="POST", token=token,
            body={"rev": rev, "flows": desired},
            headers={"Node-RED-Deployment-Type": "flows"},
        )
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            print(f"\n{name}: CONFLICT. The running flow has changed since rev {rev} — "
                  f"someone edited it in the browser.\n"
                  f"That edit is not in Git and deploying would destroy it.\n"
                  f"Recover it first: docs/runbook.md, 'On 409'.", file=sys.stderr)
            return 2
        raise

    print(f"{name}: deployed ({status})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    target = ap.add_mutually_exclusive_group(required=True)
    target.add_argument("--instance", help="registry.yml name, e.g. wag-prod")
    target.add_argument("--all", action="store_true", help="every instance with an app")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the diff and exit 0, changing nothing")
    args = ap.parse_args()

    instances = load_instances()
    if args.instance:
        chosen = [i for i in instances if i.get("name") == args.instance]
        if not chosen:
            raise SystemExit(f"no instance named {args.instance} in registry.yml")
    else:
        chosen = [i for i in instances if i.get("app")]

    worst = 0
    for inst in chosen:
        worst = max(worst, deploy(inst, args.dry_run))
    return worst


if __name__ == "__main__":
    sys.exit(main())
