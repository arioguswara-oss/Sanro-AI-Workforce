#!/usr/bin/env bash
set -euo pipefail

# Read-only host readiness check. It intentionally does not install/enable the
# plugin, read secrets, start a job, or restart Hermes. Hermes v0.22 plugin
# approval transports do not provide the missing per-job policy callback.
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if [[ "$(id -u)" -eq 0 ]]; then
  echo "BLOCKED: run as the existing non-root sanro account" >&2
  exit 3
fi
profile="${HOME}/.hermes/profiles/sanro-qa"
plugin="${repo_root}/integrations/hermes/sanro_qa_runtime"
[[ -d "$profile" && ! -L "$profile" ]] || { echo "BLOCKED: existing sanro-qa profile is unavailable" >&2; exit 3; }
[[ -f "${plugin}/plugin.yaml" && -f "${plugin}/client.py" && -f "${plugin}/__init__.py" ]] || { echo "BLOCKED: reviewed profile plugin source is incomplete" >&2; exit 3; }
command -v hermes >/dev/null || { echo "BLOCKED: Hermes CLI is unavailable" >&2; exit 3; }

echo "PREFLIGHT: non-root identity, existing profile, and plugin source PASS"
echo "BLOCKED: Hermes plugin registration has no official per-job native approval policy/callback contract in v0.22.0. Workforce will not register a runtime executor without that provider."
echo "No profile, secret, API, service, worker, or browser state was changed."
exit 3
