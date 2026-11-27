#!/usr/bin/env bash
set -euo pipefail

# Minimal, rollbackable AppArmor userns allowlist for the existing Playwright
# Chromium 1255 executable. This script never changes sysctls or global policy.
readonly PROFILE_NAME="sanro-playwright-chromium-1255"
readonly PROFILE_FILE="/etc/apparmor.d/${PROFILE_NAME}"
readonly PROFILE_MARKER="# SANRO QA Chromium userns exception v1"
readonly OWNER="sanro"
readonly BROWSER_REL=".cache/ms-playwright/chromium-1255/chrome-linux64/chrome"

die() { printf 'BLOCKED: %s\n' "$*" >&2; exit 3; }
info() { printf '%s\n' "$*"; }

owner_home="$(getent passwd "$OWNER" | cut -d: -f6)"
[[ -n "$owner_home" && "$owner_home" = /* ]] || die "cannot resolve ${OWNER} home directory"
browser="${owner_home}/${BROWSER_REL}"
[[ -x "$browser" && ! -L "$browser" ]] || die "expected executable not present as a regular file: ${browser}"
browser_real="$(readlink -f -- "$browser")"
[[ "$browser_real" = "$browser" ]] || die "browser path resolves elsewhere; refusing broader or unexpected executable path"
command -v apparmor_parser >/dev/null || die "apparmor_parser is unavailable"
command -v aa-status >/dev/null || die "aa-status is unavailable"

profile_text() {
  cat <<EOF
${PROFILE_MARKER}
abi <abi/4.0>,
include <tunables/global>

profile ${PROFILE_NAME} ${browser} flags=(unconfined) {
  userns,
  @{exec_path} mr,
}
EOF
}

preflight() {
  info "PREFLIGHT PASS: existing Chromium executable: ${browser}"
  aa-status --enabled || die "AppArmor is not enabled"
  [[ "$(sysctl -n kernel.apparmor_restrict_unprivileged_userns 2>/dev/null || true)" = "1" ]] || die "expected AppArmor unprivileged userns restriction is not enabled"
  info "PREFLIGHT PASS: AppArmor is enabled and unprivileged userns restriction is 1"
  for stock_profile in /etc/apparmor.d/chrome /etc/apparmor.d/chromium; do
    [[ -r "$stock_profile" ]] || die "expected existing profile unavailable: ${stock_profile}"
    info "EXISTING PROFILE ${stock_profile}:"
    grep -nE '^(@\{chromium\}|profile |[[:space:]]*userns,)' "$stock_profile" || true
  done
  info "PROFILE MATCH: this exact executable is outside the observed chrome/chromium profile paths"
  if [[ -e "$PROFILE_FILE" ]]; then
    grep -Fqx "$PROFILE_MARKER" "$PROFILE_FILE" || die "target profile path is occupied by an unowned file"
    cmp -s "$PROFILE_FILE" <(profile_text) || die "existing SANRO profile differs; manual review required"
    info "IDEMPOTENT: exact SANRO profile file already exists"
  else
    info "READY: would add only ${PROFILE_FILE}; no file or kernel policy changed"
  fi
  info "No sysctl, global policy, browser flags, Hermes profile, service, or worker is changed by preflight."
}

apply_profile() {
  [[ "$#" -eq 1 && -n "$1" ]] || die "apply requires the recorded Owner approval reference"
  [[ "$(id -u)" -eq 0 ]] || die "apply must be run by root after Owner approval"
  [[ "${SANRO_QA_OWNER_APPROVAL:-}" = "$1" ]] || die "approval reference must also be supplied as SANRO_QA_OWNER_APPROVAL"
  preflight
  local staged
  local created=0 active=0
  staged=""
  rollback_on_error() {
    local code=$?
    trap - ERR INT TERM
    if [[ "$active" -eq 1 ]]; then
      apparmor_parser -R "$PROFILE_FILE" >/dev/null 2>&1 || true
    fi
    if [[ "$created" -eq 1 ]]; then rm -f -- "$PROFILE_FILE"; fi
    if [[ -n "$staged" ]]; then rm -f -- "$staged"; fi
    exit "$code"
  }
  trap rollback_on_error ERR INT TERM
  if [[ -e "$PROFILE_FILE" ]]; then
    grep -Fqx "$PROFILE_MARKER" "$PROFILE_FILE" || die "target profile path is occupied by an unowned file"
    cmp -s "$PROFILE_FILE" <(profile_text) || die "existing SANRO profile differs; manual review required"
    apparmor_parser -r "$PROFILE_FILE"
  else
    staged="$(mktemp /etc/apparmor.d/.${PROFILE_NAME}.XXXXXX)"
    profile_text > "$staged"
    chmod 0644 "$staged"
    apparmor_parser -Q "$staged"
    mv -- "$staged" "$PROFILE_FILE"
    staged=""
    created=1
    apparmor_parser -a "$PROFILE_FILE"
  fi
  active=1
  aa-status --profiled | grep -Fq "$PROFILE_NAME"
  info "PROFILE ACTIVE: ${PROFILE_NAME}; Chromium sandbox is still required by the acceptance runner"
  trap - ERR INT TERM
}

rollback_profile() {
  [[ "$#" -eq 1 && -n "$1" ]] || die "rollback requires the recorded Owner approval reference"
  [[ "$(id -u)" -eq 0 ]] || die "rollback must be run by root"
  [[ "${SANRO_QA_OWNER_APPROVAL:-}" = "$1" ]] || die "approval reference must also be supplied as SANRO_QA_OWNER_APPROVAL"
  [[ -e "$PROFILE_FILE" ]] || { info "IDEMPOTENT: SANRO profile file is absent"; exit 0; }
  grep -Fqx "$PROFILE_MARKER" "$PROFILE_FILE" || die "refusing to remove profile without SANRO marker"
  apparmor_parser -R "$PROFILE_FILE"
  rm -f -- "$PROFILE_FILE"
  [[ ! -e "$PROFILE_FILE" ]] || die "profile file remains after rollback"
  if aa-status --profiled | grep -Fq "$PROFILE_NAME"; then die "profile remains loaded after rollback"; fi
  info "ROLLBACK PASS: SANRO profile unloaded and removed"
}

case "${1:---preflight}" in
  --preflight) [[ "$#" -eq 1 ]] || die "unexpected arguments"; preflight ;;
  --apply) shift; apply_profile "$@" ;;
  --rollback) shift; rollback_profile "$@" ;;
  *) die "usage: $0 [--preflight | --apply OWNER-APPROVAL-REF | --rollback OWNER-APPROVAL-REF]" ;;
esac
