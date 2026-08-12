#!/usr/bin/env bash
# Read-only discovery of the facts still missing for the deployment scaffold.
# Run on each Node-RED host. Writes a report to stdout and to /tmp/nr-gaps-<host>.txt
#
# Reports the EXISTENCE of credentialSecret / adminAuth, never their values.
# Makes no change to any container, file or network.

set -uo pipefail

OUT="/tmp/nr-gaps-$(hostname -s).txt"
exec > >(tee "$OUT") 2>&1

section() { printf '\n===== %s =====\n' "$1"; }

section "HOST"
hostname -f
hostname -s
ip -4 -o addr show scope global | awk '{print $2, $4}'

section "NODE-RED CONTAINERS"
CONTAINERS=$(docker ps -a --format '{{.Names}}' | grep -i 'node.\?red' || true)
if [ -z "$CONTAINERS" ]; then
  echo "none found"
else
  echo "$CONTAINERS"
fi

section "COMPOSE PROJECT MEMBERSHIP"
# Which compose file owns which service — decides the blast radius of a recreate.
docker ps -a \
  --format '{{.Names}}' \
  --filter 'label=com.docker.compose.project' \
  | while read -r c; do
      proj=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$c" 2>/dev/null)
      svc=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$c" 2>/dev/null)
      file=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$c" 2>/dev/null)
      printf '%-32s project=%-24s service=%-24s file=%s\n' "$c" "$proj" "$svc" "$file"
    done

section "PER-INSTANCE DETAIL"
for c in $CONTAINERS; do
  printf '\n--- %s ---\n' "$c"

  echo "image:      $(docker inspect -f '{{.Config.Image}}' "$c" 2>/dev/null)"
  echo "image_id:   $(docker inspect -f '{{.Image}}' "$c" 2>/dev/null)"
  echo "restart:    $(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$c" 2>/dev/null)"
  echo "state:      $(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null)"
  echo "networks:   $(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$c" 2>/dev/null)"
  echo "ip:         $(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "$c" 2>/dev/null)"
  echo "ports:      $(docker inspect -f '{{json .HostConfig.PortBindings}}' "$c" 2>/dev/null)"
  echo "dns_search: $(docker inspect -f '{{json .HostConfig.DnsSearch}}' "$c" 2>/dev/null)"

  DATA=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Source}}{{end}}{{end}}' "$c" 2>/dev/null)
  echo "data_mount: ${DATA:-<none>}"
  [ -z "$DATA" ] || [ ! -d "$DATA" ] && { echo "(no readable /data bind mount — skipping file facts)"; continue; }

  S="$DATA/settings.js"
  if [ -f "$S" ]; then
    echo "settings.js: present  sha256=$(sha256sum "$S" | cut -c1-16)"
    echo "  httpAdminRoot:         $(grep -oP 'httpAdminRoot\s*:\s*[\"'\'']\K[^\"'\'']*' "$S" | head -1 || echo '<unset>')"
    echo "  credentialSecret set:  $(grep -qE '^\s*credentialSecret\s*:' "$S" && echo yes || echo 'no (generated key in .config.runtime.json)')"
    echo "  adminAuth set:         $(grep -qE '^\s*adminAuth\s*:' "$S" && echo yes || echo no)"
    echo "  contextStorage set:    $(grep -qE '^\s*contextStorage\s*:' "$S" && echo yes || echo no)"
    echo "  functionExternalMods:  $(grep -oP 'functionExternalModules\s*:\s*\K(true|false)' "$S" | head -1 || echo '<unset>')"
    echo "  flowFilePretty:        $(grep -oP 'flowFilePretty\s*:\s*\K(true|false)' "$S" | head -1 || echo '<unset>')"
  else
    echo "settings.js: MISSING"
  fi

  F="$DATA/flows.json"
  if [ -f "$F" ]; then
    echo "flows.json: $(stat -c%s "$F") bytes  nodes=$(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1]))))' "$F" 2>/dev/null || echo '?')"
    echo "  function nodes with own npm module: $(grep -c '\"module\"\s*:' "$F" 2>/dev/null || echo 0)"
  else
    echo "flows.json: MISSING"
  fi

  echo "flows_cred.json:      $([ -f "$DATA/flows_cred.json" ] && echo present || echo absent)"
  echo ".config.runtime.json: $([ -f "$DATA/.config.runtime.json" ] && echo present || echo absent)"

  P="$DATA/package.json"
  if [ -f "$P" ]; then
    echo "palette modules:"
    python3 -c 'import json,sys;d=json.load(open(sys.argv[1])).get("dependencies",{});print("\n".join("  %s %s"%(k,v) for k,v in sorted(d.items())) or "  <none>")' "$P" 2>/dev/null || sed -n '/dependencies/,/}/p' "$P"
  else
    echo "package.json: MISSING"
  fi
done

section "ADMIN API REACHABILITY (from this host)"
# 401 = reachable and adminAuth active. 200 = reachable, auth NOT active.
# 000 = not reachable. Anything else = routed somewhere unexpected.
for c in $CONTAINERS; do
  IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "$c" 2>/dev/null | awk '{print $1}')
  DATA=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Source}}{{end}}{{end}}' "$c" 2>/dev/null)
  ROOT=$(grep -oP 'httpAdminRoot\s*:\s*[\"'\'']\K[^\"'\'']*' "$DATA/settings.js" 2>/dev/null | head -1)
  [ -z "$IP" ] && { echo "$c: no container IP"; continue; }
  CODE=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "http://${IP}:1880${ROOT}/flows" || echo 000)
  echo "$c: http://${IP}:1880${ROOT}/flows -> $CODE"
  CODE=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "http://${IP}:1880${ROOT}/auth/token" || echo 000)
  echo "$c: http://${IP}:1880${ROOT}/auth/token -> $CODE"
done

section "NGINX ROUTING FOR NODE-RED"
# Where the reverse proxy sends the admin root — decides the base URL CI must use.
for d in /etc/nginx /opt/nginx /home/administrator; do
  [ -d "$d" ] && grep -rl 'node.\?red' "$d" 2>/dev/null | head -10
done
docker ps --format '{{.Names}}' | grep -i nginx || echo "no nginx container on this host"

section "SHARED COMPOSE FILE — SERVICES"
CF=/home/administrator/base_container/docker-compose.yml
if [ -f "$CF" ]; then
  echo "file: $CF"
  python3 -c 'import sys,yaml;print("\n".join(sorted(yaml.safe_load(open(sys.argv[1])).get("services",{}))))' "$CF" 2>/dev/null \
    || grep -oP '^  \K[a-zA-Z0-9_-]+(?=:)' "$CF"
else
  echo "$CF not present on this host"
fi

printf '\nReport written to %s\n' "$OUT"
