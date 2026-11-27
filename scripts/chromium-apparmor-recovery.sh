#!/usr/bin/env bash
set -euo pipefail

# Minimal, rollbackable AppArmor userns allowlist for a root-owned, immutable
# copy of Playwright Chromium 1255. Never profile a worker-writable executable.
readonly PROFILE_NAME="sanro-playwright-chromium-1255"
readonly PROFILE_FILE="/etc/apparmor.d/${PROFILE_NAME}"
readonly PROFILE_MARKER="# SANRO QA Chromium userns exception v2"
readonly TRUSTED_BROWSER="/usr/local/lib/sanro-playwright/chromium-1255/chrome-linux64/chrome"

die() { printf 'BLOCKED: %s\n' "$*" >&2; exit 3; }
info() { printf '%s\n' "$*"; }

browser="$TRUSTED_BROWSER"
command -v apparmor_parser >/dev/null || die "apparmor_parser is unavailable"
command -v aa-status >/dev/null || die "aa-status is unavailable"

check_browser() {
  [[ -x "$browser" && -f "$browser" && ! -L "$browser" ]] || die "trusted root-owned Chromium is not staged at ${browser}"
  local browser_real path_part path_mode
  browser_real="$(readlink -f -- "$browser")"
  [[ "$browser_real" = "$browser" ]] || die "browser path resolves elsewhere; refusing unexpected executable path"
  path_part="$browser"
  while [[ "$path_part" != "/" ]]; do
    [[ "$(stat -c %u -- "$path_part")" = "0" ]] || die "trusted Chromium path contains a non-root-owned component: ${path_part}"
    path_mode="$(stat -c %a -- "$path_part")"
    (( (8#${path_mode} & 0022) == 0 )) || die "trusted Chromium path is group/world writable: ${path_part}"
    path_part="$(dirname -- "$path_part")"
  done
}

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
  check_browser
  info "PREFLIGHT PASS: trusted root-owned Chromium executable: ${browser}"
  aa-status --enabled || die "AppArmor is not enabled"
  [[ "$(sysctl -n kernel.apparmor_restrict_unprivileged_userns 2>/dev/null || true)" = "1" ]] || die "expected AppArmor unprivileged userns restriction is not enabled"
  info "PREFLIGHT PASS: AppArmor is enabled and unprivileged userns restriction is 1"
  info "PROFILE MATCH: this exact immutable executable receives the SANRO userns exception"
  local parse_file
  parse_file="$(mktemp /tmp/${PROFILE_NAME}.XXXXXX)"
  profile_text > "$parse_file"
  if ! apparmor_parser -K -Q "$parse_file"; then rm -f -- "$parse_file"; die "AppArmor parser rejected generated profile"; fi
  rm -f -- "$parse_file"
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
    if aa-status --profiled | grep -Fq "$PROFILE_NAME"; then
      apparmor_parser -r "$PROFILE_FILE"
    else
      active=1
      apparmor_parser -a "$PROFILE_FILE"
    fi
  else
    staged="$(mktemp /etc/apparmor.d/.${PROFILE_NAME}.XXXXXX)"
    profile_text > "$staged"
    chmod 0644 "$staged"
    apparmor_parser -K -Q "$staged"
    mv -- "$staged" "$PROFILE_FILE"
    staged=""
    created=1
    active=1
    apparmor_parser -a "$PROFILE_FILE"
  fi
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
  --render-profile) [[ "$#" -eq 1 ]] || die "unexpected arguments"; profile_text ;;
  --apply) shift; apply_profile "$@" ;;
  --rollback) shift; rollback_profile "$@" ;;
  *) die "usage: $0 [--preflight | --render-profile | --apply OWNER-APPROVAL-REF | --rollback OWNER-APPROVAL-REF]" ;;
esac
