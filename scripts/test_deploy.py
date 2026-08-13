#!/usr/bin/env python3
"""Tests for deploy.py against a stub Admin API. Run: python3 scripts/test_deploy.py

The stub answers the way Node-RED does: a token endpoint, a v2 GET that carries
a rev, and a POST that returns 409 when the rev it is given is stale.
"""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "deploy.py"

FAILED = []


def check(label, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}{'  ' + detail if detail and not condition else ''}")
    if not condition:
        FAILED.append(label)


STATE = {
    "rev": "rev-1",
    "flows": [],
    "require_auth": True,
    "stale": False,      # make POST see a rev that has moved on
    "posted": None,
    "saw_deploy_type": None,
    "saw_auth": None,
}


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, payload=None):
        body = json.dumps(payload).encode() if payload is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")

        if self.path.endswith("/auth/token"):
            if body.get("username") == "admin" and body.get("password") == "secret":
                return self._send(200, {"access_token": "tok-123", "token_type": "Bearer"})
            return self._send(401, {"error": "invalid"})

        if self.path.endswith("/flows"):
            STATE["saw_auth"] = self.headers.get("Authorization")
            STATE["saw_deploy_type"] = self.headers.get("Node-RED-Deployment-Type")
            if STATE["require_auth"] and STATE["saw_auth"] != "Bearer tok-123":
                return self._send(401, {"error": "unauthorized"})
            if STATE["stale"] or body.get("rev") != STATE["rev"]:
                return self._send(409, {"error": "version_mismatch"})
            STATE["posted"] = body.get("flows")
            STATE["flows"] = body.get("flows")
            STATE["rev"] = "rev-2"
            return self._send(204)
        self._send(404)

    def do_GET(self):
        if self.path.endswith("/flows"):
            auth = self.headers.get("Authorization")
            if STATE["require_auth"] and auth != "Bearer tok-123":
                return self._send(401, {"error": "unauthorized"})
            return self._send(200, {"rev": STATE["rev"], "flows": STATE["flows"]})
        self._send(404)


server = HTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{server.server_address[1]}"

print("deploy.py")


def run(*args, creds=True, base=BASE):
    env = {**os.environ, "NODE_RED_BASE_URL": base}
    if creds:
        env["CHANGEME_NODERED_WAG_PROD_AUTH_USR"] = "admin"
        env["CHANGEME_NODERED_WAG_PROD_AUTH_PSW"] = "secret"
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, env=env, cwd=ROOT)


desired = json.loads((ROOT / "apps" / "wag-prod" / "flows.json").read_text(encoding="utf-8"))

# --- registry is readable, and the target resolves --------------------------
sys.path.insert(0, str(ROOT / "scripts"))
from deploy import load_instances, env_credentials  # noqa: E402

instances = load_instances()
check("registry loads", len(instances) == 13, str(len(instances)))
check("instance names are unique", len({i["name"] for i in instances}) == 13)
wag = next(i for i in instances if i["name"] == "wag-prod")
check("admin_root read correctly", wag["admin_root"] == "/node-red-prod", wag.get("admin_root"))
check("empty admin_root stays empty",
      next(i for i in instances if i["name"] == "wfm")["admin_root"] == "")
check("credential env naming", env_credentials("nodered-x-auth") is None)

# --- dry run ----------------------------------------------------------------
r = run("--instance", "wag-prod", "--dry-run")
check("dry-run exits 0", r.returncode == 0, r.stderr[-400:])
check("dry-run changes nothing on the instance", STATE["posted"] is None)
check("dry-run prints a diff", "+++ git/apps/wag-prod" in r.stdout)
check("dry-run reports the rev", "rev rev-1" in r.stdout, r.stdout[:200])

# --- real deploy ------------------------------------------------------------
r = run("--instance", "wag-prod")
check("deploy exits 0", r.returncode == 0, r.stderr[-400:])
check("deploy sent the flow", STATE["posted"] == desired)
check("deploy sent Node-RED-Deployment-Type: flows",
      STATE["saw_deploy_type"] == "flows", str(STATE["saw_deploy_type"]))
check("deploy authenticated with a bearer token",
      STATE["saw_auth"] == "Bearer tok-123", str(STATE["saw_auth"]))

# --- idempotence ------------------------------------------------------------
STATE["posted"] = None
r = run("--instance", "wag-prod")
check("redeploying an unchanged flow is a no-op",
      r.returncode == 0 and STATE["posted"] is None and "already up to date" in r.stdout,
      r.stdout[:200])

# --- 409 --------------------------------------------------------------------
STATE["flows"] = [{"id": "hand-edit", "type": "inject", "z": "t", "name": "edited in browser"}]
STATE["stale"] = True
r = run("--instance", "wag-prod")
check("a rev conflict exits non-zero", r.returncode == 2, f"rc={r.returncode}")
check("the conflict message names the cause", "edited it in the browser" in r.stderr)
check("the conflict message points at the runbook", "runbook.md" in r.stderr)
check("a conflict leaves the running flow alone",
      STATE["flows"][0]["id"] == "hand-edit")

# --- no --force exists ------------------------------------------------------
r = run("--instance", "wag-prod", "--force")
check("--force is not a flag", r.returncode != 0 and "unrecognized arguments" in r.stderr)
check("the word --force appears nowhere in the source",
      "--force" not in (ROOT / "scripts" / "deploy.py").read_text(encoding="utf-8").replace(
          "There is no --force", ""))

# --- auth failures are loud -------------------------------------------------
STATE["stale"] = False
STATE["rev"] = "rev-1"
r = run("--instance", "wag-prod", "--dry-run", creds=False)
check("missing credentials are reported, not silently skipped",
      "no credentials in the environment" in r.stdout, r.stdout[:200])
check("an unauthenticated call against a protected instance fails",
      r.returncode != 0, f"rc={r.returncode}")

# --- unknown instance -------------------------------------------------------
r = run("--instance", "does-not-exist", "--dry-run")
check("an unknown instance fails clearly",
      r.returncode != 0 and "no instance named" in r.stderr)

server.shutdown()
print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
sys.exit(1 if FAILED else 0)
