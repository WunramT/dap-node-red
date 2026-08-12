#!/usr/bin/env bash
# Claude Code web — cached Setup script (runs once per ~7-day environment cache).
# Point the web environment's "Setup script" field at:
#   bash "$CLAUDE_PROJECT_DIR/.claude/scripts/web-setup.sh"
#
# Bakes everything expensive and cacheable into the environment snapshot so that
# per-session startup (web-session-start.sh) is fast with NO late-stage installs:
#   - toolchain the build/test/E2E need on the plain Ubuntu 24.04 web VM
#     (podman and the .devcontainer are NOT present there)
#   - the Playwright Chromium build the repo pins, under /opt/pw-browsers
#   - a warm NuGet package cache (/root/.nuget) for fast, offline-capable builds
#   - pre-pulled infra container images
#
# WHAT PERSISTS: only system paths survive into the snapshot — /usr, /opt,
# /var/lib/docker, and $HOME caches (/root/.nuget, /root/.npm). The repo working
# tree is re-cloned fresh every session, so anything written under it (bin/,
# obj/, node_modules) is discarded and must NOT be relied on here.
#
# Runs as root on the web VM. Idempotent — safe to re-run.
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive
# Resolve the repo root from THIS script's location. The setup phase is not the
# SessionStart hook, so $CLAUDE_PROJECT_DIR is NOT a guaranteed part of its
# environment — deriving from BASH_SOURCE is correct regardless of cwd or env.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

# --- .NET SDK (channel 10.0; global.json pins 10.0.101 with rollForward). Use
#     dotnet-install.sh to avoid Ubuntu-24.04 apt/dotnet feed conflicts. --------
if ! command -v dotnet >/dev/null 2>&1; then
  curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh
  bash /tmp/dotnet-install.sh --channel 10.0 --install-dir /usr/share/dotnet
  ln -sf /usr/share/dotnet/dotnet /usr/local/bin/dotnet
fi

# --- PowerShell (drives Playwright's playwright.ps1 dry-run) -------------------
if ! command -v pwsh >/dev/null 2>&1; then
  curl -fsSL https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb \
    -o /tmp/ms-prod.deb
  dpkg -i /tmp/ms-prod.deb
  # -o Acquire::AllowReleaseInfoChange::Label=true: the base image ships the
  # ondrej/php PPA as a pre-existing apt source, and it has changed its
  # Release file's Label field (deprecation notice pointing at
  # packages.sury.org). apt refuses `update` on any release-info change by
  # default (exit 100) unless told this specific field is expected to change;
  # narrower than blanket --allow-releaseinfo-change, which would also wave
  # through Origin/Codename changes we have no reason to expect.
  apt-get update -o Acquire::AllowReleaseInfoChange::Label=true
  apt-get install -y --no-install-recommends powershell
fi

# --- Node.js LTS (on-demand frontend theme rebuilds) --------------------------
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -
  apt-get install -y --no-install-recommends nodejs
fi

# --- Chromium system libraries. The base web image usually ships these already;
#     install is a cheap idempotent guarantee. Mirrors .devcontainer/Containerfile.
apt-get update -o Acquire::AllowReleaseInfoChange::Label=true
apt-get install -y --no-install-recommends \
  libnss3 libnspr4 \
  libatk1.0-0t64 libatk-bridge2.0-0t64 \
  libcups2t64 \
  libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libxfixes3 libxext6 \
  libgbm1 \
  libpango-1.0-0 libcairo2 libasound2t64 \
  libdbus-1-3 libdrm2 libglib2.0-0t64 \
  fonts-liberation fonts-noto-color-emoji \
  || true

cd "$REPO"

# --- Repo tools (csharpier) + warm NuGet cache. `dotnet tool restore` needs
#     TELERIK_NUGET_KEY set as a web env var (NuGet.Config uses it), else Telerik
#     restore fails. The full solution restore populates /root/.nuget (persists),
#     so per-session builds are fast and largely offline. -----------------------
dotnet --info
dotnet tool restore
dotnet restore Polipol.ProductionAssistant.slnx

# --- Bake the pinned Playwright Chromium build into /opt/pw-browsers (persists).
#     This replaces the old per-session download. Non-fatal: web-session-start.sh
#     self-heals if it is ever missing. See ensure-playwright-browsers.sh for why
#     we curl the build ourselves instead of `playwright install`. --------------
bash "$REPO/.claude/scripts/ensure-playwright-browsers.sh" \
  || echo "[web-setup] WARNING: Playwright provisioning failed; session-start will retry."

# --- Warm the npm cache (/root/.npm persists) so on-demand theme rebuilds
#     (UIX-005: npm ci && npm run build:theme) are fast/offline later. The
#     resulting node_modules lives in the ephemeral repo tree, so it is only a
#     cache warm-up here, not a persisted artifact. Non-fatal. -----------------
npm --prefix src/Polipol.PA.Frontend ci || echo "[web-setup] WARNING: npm ci failed; theme rebuilds may need network."

# --- Pre-pull infra container images into the cached snapshot (persists under
#     /var/lib/docker). The dev project (compose.yaml + auto-loaded
#     compose.override.yaml) covers every image the test project uses too — they
#     share the same service images. Needs the daemon, which has no systemd unit
#     on this VM, so start it first (same as web-session-start.sh does). --------
if ! docker info >/dev/null 2>&1; then
  nohup dockerd >/tmp/dockerd-setup.log 2>&1 &
  disown
  for _ in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 1; done
fi
docker compose --project-directory "$REPO/environment" pull || true

# --- Best-effort plugin marketplace + install warm-up. NOTE: ~/.claude/plugins
#     is NOT among the persisted snapshot paths above (only /usr, /opt,
#     /var/lib/docker, /root/.nuget, /root/.npm survive), so this almost
#     certainly does not carry into the next session on its own — see
#     provision-plugins.sh. web-session-start.sh's copy of this step is the one
#     that actually matters and runs unconditionally every session; this call
#     is kept here only in case a future snapshot format persists more of
#     $HOME. Safe no-op today either way. ----------------------------------
bash "$REPO/.claude/scripts/provision-plugins.sh" \
  || echo "[web-setup] WARNING: plugin provisioning failed; session-start will retry."
