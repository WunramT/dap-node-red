#!/usr/bin/env python3
"""Validate registry.yml against the schema, plus the rules a schema cannot express.

    python3 scripts/validate-registry.py            # fails on CHANGEME
    python3 scripts/validate-registry.py --draft     # allows CHANGEME, still checks the rest

Exit code 0 means the registry is deployable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry.yml"
SCHEMA = ROOT / "schemas" / "registry.schema.json"
APPS = ROOT / "apps"


def check(registry: dict, allow_changeme: bool) -> list[str]:
    """The rules the schema cannot express: cross-field and cross-file ones."""
    errors = []
    instances = registry.get("instances", [])

    seen: dict[str, str] = {}
    for inst in instances:
        name = inst.get("name")
        if name in seen:
            errors.append(f"duplicate instance name '{name}'")
        seen[name] = inst.get("host", "?")

    for inst in instances:
        name = inst.get("name", "?")

        # A host may run several services, but not two with the same name.
        twins = [
            o for o in instances
            if o is not inst
            and o.get("host") == inst.get("host")
            and o.get("compose_service") == inst.get("compose_service")
        ]
        if twins:
            errors.append(
                f"{name}: compose_service '{inst.get('compose_service')}' is claimed twice "
                f"on {inst.get('host')} (also by {twins[0].get('name')})"
            )

        # An app must exist as a directory, or the deploy has nothing to push.
        app = inst.get("app")
        if app and not (APPS / app).is_dir():
            errors.append(f"{name}: app '{app}' has no directory at apps/{app}/")
        if app and not (APPS / app / "flows.json").is_file():
            errors.append(f"{name}: apps/{app}/flows.json is missing")

        if not allow_changeme:
            for field in ("image_tag", "auth_credential_id", "credential_secret_id"):
                if str(inst.get(field, "")).startswith("CHANGEME"):
                    errors.append(f"{name}: {field} is still a placeholder")

    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", action="store_true",
                    help="allow CHANGEME placeholders; use while the registry is being filled in")
    args = ap.parse_args()

    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    errors = [
        f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
        for e in sorted(Draft202012Validator(schema).iter_errors(registry),
                        key=lambda e: list(e.absolute_path))
    ]
    errors += check(registry, allow_changeme=args.draft)

    if errors:
        print(f"registry.yml: {len(errors)} problem(s)\n", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    n = len(registry.get("instances", []))
    print(f"registry.yml OK — {n} instances"
          + (" (draft: placeholders allowed)" if args.draft else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
