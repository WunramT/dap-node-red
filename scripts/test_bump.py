#!/usr/bin/env python3
"""Tests for bump-node-red.py. Run: python3 scripts/test_bump.py

The version of an instance lives in its Dockerfile and in its image_tag, and
the whole point of the script is that those two never diverge. So that is what
this checks, plus that it refuses rather than guessing.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "bump-node-red.py"
FAILED = []


def check(label, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}{'  ' + detail if detail and not condition else ''}")
    if not condition:
        FAILED.append(label)


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=ROOT)


REG = ROOT / "registry.yml"
DOCKER = ROOT / "apps" / "wfm-test" / "Dockerfile"
PIPELINE = ROOT / "apps" / "build-image-pipeline.yml"
saved = {p: p.read_bytes() for p in (REG, DOCKER, PIPELINE)}

print("bump-node-red.py")
try:
    r = run("--to", "latest", "--all")
    check("a floating version is refused", r.returncode != 0 and "5.0.1" in r.stderr, r.stderr[-200:])

    r = run("--to", "5.0.1", "--instance", "no-such-instance")
    check("an unknown instance is refused", r.returncode != 0 and "Known:" in r.stderr)

    r = run("--to", "5.0.1", "--instance", "slu-prod")
    check("an instance without an app is not a target", r.returncode != 0, r.stderr[-200:])

    r = run("--to", "5.0.1", "--instance", "wfm-test", "--dry-run")
    check("--dry-run reports the move", "wfm-test:4.0.9-1 -> wfm-test:5.0.1-1" in r.stdout, r.stdout)
    check("and writes nothing",
          REG.read_bytes() == saved[REG] and DOCKER.read_bytes() == saved[DOCKER])

    comments_before = saved[REG].decode().count("#")
    r = run("--to", "5.0.1", "--instance", "wfm-test")
    check("the move exits 0", r.returncode == 0, r.stderr[-300:])
    registry, dockerfile = REG.read_text(encoding="utf-8"), DOCKER.read_text(encoding="utf-8")

    check("the image_tag carries the new version", "wfm-test:5.0.1-1" in registry)
    check("the palette build resets to 1", "wfm-test:5.0.1-2" not in registry)
    check("the Dockerfile FROM follows",
          re.search(r"^FROM \S+/node-red:5\.0\.1$", dockerfile, re.M) is not None)
    check("no other instance moved", "wfm-prod:4.0.9-1" in registry)
    check("every comment in the registry survives", registry.count("#") == comments_before)
    check("the Dockerfile keeps its explanation",
          "node-red itself" in dockerfile and "palette.json" in dockerfile)
    check("the generated pipeline was refreshed", "wfm-test:5.0.1-1" in PIPELINE.read_text(encoding="utf-8")
          or "5.0.1-1" in PIPELINE.read_text(encoding="utf-8"))

    r = run("--to", "5.0.1", "--instance", "wfm-test")
    check("moving an instance that is already there is a no-op",
          "already on 5.0.1" in r.stdout and "nothing to do" in r.stdout, r.stdout)

    # A Dockerfile and a tag that disagree is exactly what this script exists to
    # prevent, so it must not carry such a state forward silently.
    DOCKER.write_text(re.sub(r"^FROM (\S+)/node-red:\S+$", r"FROM \1/node-red:4.0.5",
                             DOCKER.read_text(encoding="utf-8"), count=1, flags=re.M),
                      encoding="utf-8")
    r = run("--to", "5.0.2", "--instance", "wfm-test")
    check("a Dockerfile that disagrees with the tag stops it",
          r.returncode != 0 and "Reconcile" in r.stderr, r.stderr[-200:])
finally:
    for path, content in saved.items():
        path.write_bytes(content)

print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
sys.exit(1 if FAILED else 0)
