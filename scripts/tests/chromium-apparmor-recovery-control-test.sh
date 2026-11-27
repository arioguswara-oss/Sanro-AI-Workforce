#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
test_root="$(mktemp -d /tmp/sanro-apparmor-control.XXXXXX)"
trap 'rm -rf -- "$test_root"' EXIT

root="$test_root/root"
bin="$test_root/bin"
mkdir -p "$root/etc/apparmor.d" "$root/usr/local/lib/sanro-playwright/chromium-1255/chrome-linux64" "$bin"
printf 'profile /opt/google/chrome/chrome {\n}\n' > "$root/etc/apparmor.d/chrome"
printf 'profile /usr/lib/@{chromium}/@{chromium} {\n}\n' > "$root/etc/apparmor.d/chromium"
printf '#!/bin/sh\nexit 0\n' > "$root/usr/local/lib/sanro-playwright/chromium-1255/chrome-linux64/chrome"
chmod 0555 "$root/usr/local/lib/sanro-playwright/chromium-1255/chrome-linux64/chrome"

sed \
  -e "s|/etc/apparmor.d|$root/etc/apparmor.d|g" \
  -e "s|/usr/local/lib/sanro-playwright|$root/usr/local/lib/sanro-playwright|g" \
  "$repo_root/scripts/chromium-apparmor-recovery.sh" > "$test_root/recovery.sh"
chmod 0755 "$test_root/recovery.sh"

cat > "$bin/stat" <<'SH'
#!/usr/bin/env bash
case "$2" in
  %u) printf '0\n' ;;
  %a) printf '755\n' ;;
  *) exit 2 ;;
esac
SH
cat > "$bin/id" <<'SH'
#!/usr/bin/env bash
[[ "$1" = -u ]] && printf '0\n'
SH
cat > "$bin/sysctl" <<'SH'
#!/usr/bin/env bash
printf '1\n'
SH
cat > "$bin/aa-status" <<'SH'
#!/usr/bin/env bash
case "$1" in
  --enabled) exit 0 ;;
  --profiled) [[ -f "$SANRO_TEST_STATE" ]] && printf 'sanro-playwright-chromium-1255\n' ;;
  *) exit 2 ;;
esac
SH
cat > "$bin/apparmor_parser" <<'SH'
#!/usr/bin/env bash
[[ "$1" = -K ]] && shift
case "$1" in
  -Q) exit 0 ;;
  -a|-r)
    [[ "${SANRO_TEST_FAIL_ADD:-0}" = 1 && "$1" = -a ]] && exit 1
    : > "$SANRO_TEST_STATE"
    ;;
  -R) rm -f -- "$SANRO_TEST_STATE" ;;
  *) exit 2 ;;
esac
SH
chmod 0755 "$bin"/*

export PATH="$bin:$PATH"
export SANRO_TEST_STATE="$test_root/loaded-profile"
export SANRO_QA_OWNER_APPROVAL="synthetic-approval"

"$test_root/recovery.sh" --preflight >/dev/null
"$test_root/recovery.sh" --apply synthetic-approval >/dev/null
[[ -f "$SANRO_TEST_STATE" && -f "$root/etc/apparmor.d/sanro-playwright-chromium-1255" ]]
"$test_root/recovery.sh" --apply synthetic-approval >/dev/null
"$test_root/recovery.sh" --rollback synthetic-approval >/dev/null
[[ ! -e "$SANRO_TEST_STATE" && ! -e "$root/etc/apparmor.d/sanro-playwright-chromium-1255" ]]
"$test_root/recovery.sh" --rollback synthetic-approval | grep -Fq 'IDEMPOTENT'

export SANRO_TEST_FAIL_ADD=1
if "$test_root/recovery.sh" --apply synthetic-approval >/dev/null 2>&1; then
  printf 'FAIL: injected profile load error was not propagated\n' >&2
  exit 1
fi
[[ ! -e "$SANRO_TEST_STATE" && ! -e "$root/etc/apparmor.d/sanro-playwright-chromium-1255" ]]

printf 'PASS: synthetic preflight, apply, repeated apply, rollback, repeated rollback, and failed-apply cleanup\n'
