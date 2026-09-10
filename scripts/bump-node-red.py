#!/usr/bin/env python3
"""Move one or more instances to another Node-RED version.

    python3 scripts/bump-node-red.py --to 5.0.1 --instance cho-test
    python3 scripts/bump-node-red.py --to 5.0.1 --all --dry-run

The version of an instance lives in two places that must agree:

  * apps/<app>/Dockerfile   FROM docker.io/nodered/node-red:<version>
  * registry.yml            image_tag  .../<app>:<version>-<palette build>

The first is what CI builds. The second is what the deploy pins, what a
palette rebuild is triggered by, and what `nr.py edit` runs locally. Editing
one and not the other gives an image whose contents do not match its name —
and across twelve apps that is a matter of when, not if. So this edits both,
in one pass, or neither.

The palette build resets to 1, because it counts builds of that palette on
that version, and this is the first.

An upgrade is a real change, not bookkeeping: it crosses whatever the release
notes say between the two versions, and it reaches an instance only through
the palette transport, which recreates the container. Roll it one instance at
a time, workbench first.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry.yml"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def instances() -> list[dict]:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["instances"]


def dockerfile_version(app: str) -> str | None:
    path = ROOT / "apps" / app / "Dockerfile"
    if not path.exists():
        return None
    found = re.search(r"^FROM\s+\S+/node-red:(\S+)\s*$", path.read_text(encoding="utf-8"), re.M)
    return found.group(1) if found else None


def bump(inst: dict, to: str, write: bool) -> tuple[str, str] | None:
    """Rewrite one instance's Dockerfile and image_tag. Returns (old, new) tags."""
    app = inst["app"]
    tag = inst["image_tag"]
    path, _, version_build = tag.partition(":")
    old_version, _, _build = version_build.rpartition("-")
    if old_version == to:
        return None

    new_tag = f"{path}:{to}-1"
    if not write:
        return tag, new_tag

    # The Dockerfile: only the FROM line, so the comments explaining the
    # palette install survive.
    docker = ROOT / "apps" / app / "Dockerfile"
    text = docker.read_text(encoding="utf-8")
    text, n = re.subn(r"^(FROM\s+\S+/node-red:)\S+\s*$", rf"\g<1>{to}", text, count=1, flags=re.M)
    if n != 1:
        sys.exit(f"{app}: no FROM ...node-red:<version> line in its Dockerfile")
    docker.write_text(text, encoding="utf-8")

    # registry.yml as text, because PyYAML would drop every comment in it,
    # including the ones recording which version each instance runs and why.
    registry = REGISTRY.read_text(encoding="utf-8")
    block = re.search(rf"^  - name: {re.escape(inst['name'])}$.*?(?=^  - name: |\Z)",
                      registry, re.S | re.M)
    line = re.search(r"^(\s+image_tag:\s*)(\S+)(.*)$", block.group(0), re.M)
    edited = block.group(0).replace(line.group(0), f"{line.group(1)}{new_tag}{line.group(3)}", 1)
    REGISTRY.write_text(registry.replace(block.group(0), edited, 1), encoding="utf-8")
    return tag, new_tag


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", required=True, metavar="VERSION",
                    help="the Node-RED version to move to, e.g. 5.0.1")
    target = ap.add_mutually_exclusive_group(required=True)
    target.add_argument("--instance", action="append", default=[],
                        help="one instance; repeat for several")
    target.add_argument("--all", action="store_true", help="every instance that has an app")
    ap.add_argument("--dry-run", action="store_true", help="print the changes, write nothing")
    args = ap.parse_args()

    if not VERSION.match(args.to):
        sys.exit(f"--to takes a version like 5.0.1, not {args.to!r}. A floating tag "
                 f"would defeat the pin (decision 5).")

    known = {i["name"]: i for i in instances() if i.get("app")}
    if args.all:
        targets = list(known.values())
    else:
        unknown = [n for n in args.instance if n not in known]
        if unknown:
            sys.exit(f"no instance with an app named: {', '.join(unknown)}.\n"
                     f"  Known: {', '.join(sorted(known))}")
        targets = [known[n] for n in args.instance]

    moved, already = [], []
    for inst in targets:
        # The Dockerfile is what CI builds from, so a disagreement there is the
        # one that produces a wrongly named image.
        on_disk = dockerfile_version(inst["app"])
        in_tag = inst["image_tag"].partition(":")[2].rpartition("-")[0]
        if on_disk and on_disk != in_tag:
            sys.exit(f"{inst['name']}: its Dockerfile says {on_disk} and its image_tag "
                     f"says {in_tag}. Reconcile that first — this script would carry "
                     f"the disagreement forward.")

        result = bump(inst, args.to, write=not args.dry_run)
        (already if result is None else moved).append(inst["name"])
        if result:
            print(f"  {inst['name']:<11} {result[0].rsplit('/', 1)[-1]} -> "
                  f"{result[1].rsplit('/', 1)[-1]}")

    if already:
        print(f"\nalready on {args.to}: {', '.join(already)}")
    if not moved:
        print("nothing to do")
        return 0
    if args.dry_run:
        print(f"\ndry run — nothing written. Drop --dry-run to move "
              f"{len(moved)} instance(s).")
        return 0

    # The generated pipeline embeds the tags, and CI fails if it is stale.
    subprocess.run([sys.executable, "scripts/gen-image-pipeline.py"], cwd=ROOT, check=True)

    print(f"\n{len(moved)} instance(s) moved to {args.to}. Next:\n"
          f"  python3 scripts/validate-registry.py\n"
          f"  git diff\n"
          f"  commit to the default branch — CI builds each changed app\n"
          f"  then per instance: Jenkins DEPLOY_PALETTE=true, DRY_RUN=false\n"
          f"\nThat last step recreates the container, so it is an interruption per\n"
          f"instance. Workbench first, then one prod, then the rest — and read the\n"
          f"release notes between the two versions before the first one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
