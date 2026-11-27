# SANRO Chromium native activation handover — 2026-11-27

## Scope and current gate

The current cache executable is `/home/sanro/.cache/ms-playwright/chromium-1255/chrome-linux64/chrome`, owned by `sanro`, mode `0755`, inside a `sanro`-owned mode `0775` directory. It is therefore worker-writable and must not receive an AppArmor userns exception directly. No system Chrome/Chromium executable was found in the Codex-visible environment; the native VPS state is not independently attested here.

The copied Chromium tree observed in this environment is 414 MB, 301 regular files, no symlinks, tree SHA-256 `cdc517739626c4ce3b79194009447da47d4a4420944be45324b49c49c0c93461`; its `chrome` executable SHA-256 is `045558b2f167db04624e36d952496705418a85d87ff9b5fb55a8c40cc59201ae`. These hashes bind the exact bytes observed here; they are not a vendor signature. Abort if the native VPS source tree does not match the approved digest.

The hardening commits are `fc59e89e998335a354588a50bcf0b53c643c0d72` and `fbaf32ef890035eb6d20fa27e8ca7612aa1cd7ba`. Recovery script SHA-256: `9b74729c27bb5d8ab6b6e7c10e0f58b7cf6b67d8ba150bc9be783de3c5c47829`; acceptance script SHA-256: `17e976104c2628264d3c22a95ac811a86c4b7b4ee06b9c545c538d3dac3533db`. The recovery script only profiles the fixed executable path `/usr/local/lib/sanro-playwright/chromium-1255/chrome-linux64/chrome`; it requires every path component to be root-owned and not group/world writable. The Local CI test requires that same property, asserts Chromium `159.0.8154.6`, and launches Playwright with `chromiumSandbox: true`.

## Proposed native execution

This is one one-shot operation after Owner approval. It copies the exact approved tree to a root-owned path, installs the reviewed narrow recovery helper, validates and loads the path-specific AppArmor profile, then runs synthetic Local CI as `sanro`. A failed run unloads/removes the marked profile and removes only the newly staged tree if its digest still matches. A successful run leaves the profile and root-owned browser staged for SANRO QA. It does not restart Hermes or services, touch workers, change sysctls, or disable Chromium sandboxing.

```bash
set -Eeuo pipefail
umask 077
REPO=/home/sanro/workforce-dev/Sanro-AI-Workforce-gdi02
IMPL_SHA=fbaf32ef890035eb6d20fa27e8ca7612aa1cd7ba
SCRIPT_SHA=9b74729c27bb5d8ab6b6e7c10e0f58b7cf6b67d8ba150bc9be783de3c5c47829
ACCEPT_SHA=17e976104c2628264d3c22a95ac811a86c4b7b4ee06b9c545c538d3dac3533db
TREE_SHA=cdc517739626c4ce3b79194009447da47d4a4420944be45324b49c49c0c93461
SOURCE=/home/sanro/.cache/ms-playwright/chromium-1255/chrome-linux64
BASE=/usr/local/lib/sanro-playwright
DEST=$BASE/chromium-1255
HELPER=/usr/local/sbin/sanro-chromium-apparmor-recovery
APPROVAL=SANRO-CHROMIUM-NATIVE-20261128

cd "$REPO"
test "$(git branch --show-current)" = feature/hermes-workforce-foundation
test "$(git remote get-url origin)" = https://github.com/arioguswara-oss/Sanro-AI-Workforce.git
git merge-base --is-ancestor "$IMPL_SHA" HEAD
test -z "$(git status --porcelain -- scripts/chromium-apparmor-recovery.sh apps/web/scripts/chromium-sandbox-recovery-acceptance.mjs)"
test "$(git show "$IMPL_SHA:scripts/chromium-apparmor-recovery.sh" | sha256sum | cut -d' ' -f1)" = "$SCRIPT_SHA"
test "$(git show "$IMPL_SHA:apps/web/scripts/chromium-sandbox-recovery-acceptance.mjs" | sha256sum | cut -d' ' -f1)" = "$ACCEPT_SHA"
test "$(sha256sum apps/web/scripts/chromium-sandbox-recovery-acceptance.mjs | cut -d' ' -f1)" = "$ACCEPT_SHA"

tree_sha() {
  test -d "$1" && test ! -L "$1"
  test "$(readlink -f -- "$1")" = "$1"
  ! find -P "$1" -type l -print -quit | grep -q .
  ! find -P "$1" ! -type f ! -type d -print -quit | grep -q .
  (cd -- "$1" && find -P . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)
}
tree_sha_root() {
  sudo bash -Eeuo pipefail -c '
    [[ "$(id -u)" = 0 ]]
    d=$1
    [[ -d "$d" && ! -L "$d" && "$(readlink -f -- "$d")" = "$d" ]]
    ! find -P "$d" -type l -print -quit | grep -q .
    ! find -P "$d" ! -type f ! -type d -print -quit | grep -q .
    (cd -- "$d" && find -P . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d" " -f1)
  ' _ "$1"
}
test "$(readlink -f "$SOURCE")" = "$SOURCE"
test "$(tree_sha "$SOURCE")" = "$TREE_SHA"

for p in /usr/local /usr/local/lib; do
  test "$(readlink -f "$p")" = "$p"
  test "$(stat -c %u "$p")" = 0
  mode=$(stat -c %a "$p")
  (( (8#$mode & 0022) == 0 ))
done
if [[ ! -e "$BASE" ]]; then sudo install -d -o root -g root -m 0755 "$BASE"; fi
test "$(readlink -f "$BASE")" = "$BASE"
test "$(stat -c %u "$BASE")" = 0
mode=$(stat -c %a "$BASE")
(( (8#$mode & 0022) == 0 ))

COPY_CREATED=0
PROFILE_APPLIED=0
HELPER_CREATED=0
STAGE=
TMP_HELPER=
cleanup_failure() {
  rc=$?
  trap - EXIT
  if (( rc != 0 )); then
    rollback_ok=1
    if (( PROFILE_APPLIED )); then
      sudo env SANRO_QA_OWNER_APPROVAL="$APPROVAL" "$HELPER" --rollback "$APPROVAL" || rollback_ok=0
    fi
    if (( COPY_CREATED && rollback_ok )) && [[ -d "$DEST" && ! -L "$DEST" ]] && [[ "$(readlink -f -- "$DEST")" = "$DEST" ]] && [[ "$(stat -c %u "$DEST")" = 0 ]] && [[ "$(tree_sha_root "$DEST/chrome-linux64")" = "$TREE_SHA" ]]; then
      sudo rm -rf --one-file-system -- "$DEST"
    elif (( COPY_CREATED )); then
      printf 'ROLLBACK BLOCKED: destination failed integrity or rollback gate; retained at %s\n' "$DEST" >&2
    fi
    if [[ -n "$STAGE" && -d "$STAGE" && ! -L "$STAGE" && "$(readlink -f -- "$STAGE")" = "$STAGE" && "$(stat -c %u "$STAGE")" = 0 && "$(stat -c %a "$STAGE")" = 700 ]]; then sudo rm -rf --one-file-system -- "$STAGE"; fi
    if [[ -n "$TMP_HELPER" && -e "$TMP_HELPER" ]]; then rm -f -- "$TMP_HELPER"; fi
    if (( HELPER_CREATED && rollback_ok )); then sudo rm -f -- "$HELPER"; fi
  fi
  exit "$rc"
}
trap cleanup_failure EXIT

if [[ ! -e "$DEST" && ! -L "$DEST" ]]; then
  available_kb=$(df -Pk /usr/local/lib | awk 'NR==2 {print $4}')
  source_kb=$(du -sk "$SOURCE" | awk '{print $1}')
  (( available_kb >= source_kb + 102400 )) || { echo 'BLOCKED: less than source size plus 100 MiB free'; exit 3; }
  STAGE=$(sudo mktemp -d "$BASE/.chromium-stage.XXXXXX")
  test "$(stat -c %u "$STAGE")" = 0
  test "$(stat -c %a "$STAGE")" = 700
  test "$(readlink -f -- "$STAGE")" = "$STAGE"
  sudo install -d -o root -g root -m 0755 "$STAGE/chromium-1255"
  sudo bash -c 'umask 077; cp -R --no-dereference --no-preserve=ownership -- "$1" "$2"' _ "$SOURCE" "$STAGE/chromium-1255/chrome-linux64"
  test "$(tree_sha_root "$STAGE/chromium-1255/chrome-linux64")" = "$TREE_SHA"
  sudo chown -R root:root "$STAGE/chromium-1255"
  ! sudo find -P "$STAGE/chromium-1255/chrome-linux64" -type f -perm /6000 -print -quit | grep -q .
  sudo find -P "$STAGE/chromium-1255/chrome-linux64" -type d -exec chmod 0755 {} +
  sudo find -P "$STAGE/chromium-1255/chrome-linux64" -type f -perm /111 -exec chmod 0755 {} +
  sudo find -P "$STAGE/chromium-1255/chrome-linux64" -type f ! -perm /111 -exec chmod 0644 {} +
  test "$(tree_sha_root "$STAGE/chromium-1255/chrome-linux64")" = "$TREE_SHA"
  sudo mv -- "$STAGE/chromium-1255" "$DEST"
  COPY_CREATED=1
  sudo rmdir -- "$STAGE"
  STAGE=
else
  test -d "$DEST" && test ! -L "$DEST"
  test "$(readlink -f -- "$DEST")" = "$DEST"
  test "$(stat -c %u "$DEST")" = 0
  test "$(tree_sha "$DEST/chrome-linux64")" = "$TREE_SHA"
fi

if [[ ! -e "$HELPER" && ! -L "$HELPER" ]]; then
  TMP_HELPER=$(mktemp /tmp/sanro-chromium-helper.XXXXXX)
  git show "$IMPL_SHA:scripts/chromium-apparmor-recovery.sh" > "$TMP_HELPER"
  test "$(sha256sum "$TMP_HELPER" | cut -d' ' -f1)" = "$SCRIPT_SHA"
  sudo install -o root -g root -m 0755 "$TMP_HELPER" "$HELPER"
  rm -f -- "$TMP_HELPER"
  TMP_HELPER=
  HELPER_CREATED=1
else
  test "$(stat -c %u "$HELPER")" = 0
  test "$(sha256sum "$HELPER" | cut -d' ' -f1)" = "$SCRIPT_SHA"
fi
for p in /usr/local/sbin "$HELPER"; do
  test "$(stat -c %u "$p")" = 0
  mode=$(stat -c %a "$p")
  (( (8#$mode & 0022) == 0 ))
done

sudo env SANRO_QA_OWNER_APPROVAL="$APPROVAL" "$HELPER" --preflight
sudo env SANRO_QA_OWNER_APPROVAL="$APPROVAL" "$HELPER" --apply "$APPROVAL"
PROFILE_APPLIED=1

EVIDENCE="$REPO/docs/evidence/SANRO_CHROMIUM_NATIVE_QA_20261127"
test ! -e "$EVIDENCE"
mkdir -m 0700 "$EVIDENCE"
SANRO_CHROMIUM_EXECUTABLE="$DEST/chrome-linux64/chrome" \
SANRO_CHROMIUM_EVIDENCE_DIR="$EVIDENCE" \
  npm --prefix apps/web run --silent test:chromium-recovery > "$EVIDENCE/result.json"
cat "$EVIDENCE/result.json"
trap - EXIT
printf 'PASS: approved root-owned browser and exact-path profile remain available for SANRO QA; screenshot is in %s\n' "$EVIDENCE"
```

On a successful acceptance, explicit rollback later is:

```bash
sudo env SANRO_QA_OWNER_APPROVAL=SANRO-CHROMIUM-NATIVE-20261128 /usr/local/sbin/sanro-chromium-apparmor-recovery --rollback SANRO-CHROMIUM-NATIVE-20261128
```

Then remove `/usr/local/lib/sanro-playwright/chromium-1255` only after verifying its tree digest is still the approved `TREE_SHA` above. No host command has been run from this continuation.

## Owner approval request

**Owner authorization:** GO approved for one native VPS operation under reference `SANRO-CHROMIUM-NATIVE-20261128`: copy the exact Chromium tree with SHA-256 `cdc517739626c4ce3b79194009447da47d4a4420944be45324b49c49c0c93461` (414 MB, 301 regular files, no symlinks as observed here) into the non-worker-writable root-owned path, load only the `sanro-playwright-chromium-1255` AppArmor profile for that executable, and run one synthetic Local CI browser acceptance with the Chromium sandbox enabled. The cache source is user-writable before staging; the displayed digest pins its bytes but is not a vendor signature. The package fails closed if the source/copy digest differs. Approval includes rollback of only the profile and staged copy created by this invocation. No service restart, global sysctl/policy change, active worker, production, or cost is included.
