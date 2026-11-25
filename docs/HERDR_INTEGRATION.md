# Herdr integration candidate

Updated: 2026-11-25. This document records a disabled development candidate, not an installation or live integration.

## Compatibility verified from upstream

- Herdr Android connects directly to a machine using SSH; Herdr Core is the remote terminal runtime. Herdr does not require a public listener for the mobile connection.
- The documented `hc` CLI supports terminal creation, list/status, output read, and kill. The optional adapter uses these argv-based CLI calls and pins `herdr-core 0.1.22`, the version in the current official release manifest. That manifest lists per-platform SHA-256 values; the VPS architecture is unknown, so no target artifact/hash was selected or downloaded.
- The local Workforce API and durable FIFO worker remain authoritative for job submission, ACL, project/workspace binding, approvals, cancellation, logs/results and checkpoints. Herdr owns one named serial worker terminal and exposes worker lifecycle through OSC 7501 without including job content.
- The current adapter is co-located only. It rejects remote Herdr machine dispatch because the Workforce SQLite queue, API, code and workspace have no verified shared state or synchronization protocol across machines.

## Security and resource boundary

Herdr sessions run with the OS account's permissions and do not provide a sandbox or approval boundary. Same-account software can access the Herdr control socket; terminal output can retain sensitive data. Use a dedicated non-root account with no unrelated secrets, no production access, and a separately bounded workspace. Existing Workforce Landlock/seccomp controls apply only to child jobs started by the Workforce worker and do not sandbox the Herdr supervisor or provide a VM/kernel boundary. Do not enable the attestation flag until this environment is verified. The key used by Android must be treated as account-level SSH command access, not read-only monitoring.

No `hc` binary was found in the development workspace, VPS SSH authentication failed, VPS CPU/RAM/storage are unknown, and no Herdr server or Android session was started. Upstream describes Linux x86_64/aarch64 artifacts; actual target architecture and capacity remain unverified. Version `0.1.22` is the candidate pin; no artifact was installed or checksum verified on the target.

## Inactive configuration and rollback

Example only; do not place credentials in this file or enable it on a live service:

```ini
WORKFORCE_WORKER_BACKEND=herdr
WORKFORCE_HERDR_PROJECT_ID=<single authorized non-production project>
WORKFORCE_ALLOW_WORKER_CONTROL=1
WORKFORCE_HERDR_CORE_ENV_ATTESTED=1
WORKFORCE_WORKER_AUTOSTART=0
```

Before using these settings, provide an isolated account/workspace and verify the pinned Core binary and ownership/resource limits. On API shutdown the adapter requests termination of its named active supervisor. Rollback in the isolated candidate is to unset `WORKFORCE_WORKER_BACKEND` and related Herdr variables (the default returns to the local controller), then use the scoped worker-control stop operation if the session is still active. Do not kill unrelated Herdr sessions. This repository has not applied the configuration or exercised either procedure against a live host.

## SSH authorization status

The supplied request contained no public-key line. No `authorized_keys` file was changed. The SSH host key already present in local known-hosts for `13.140.185.9` fingerprints as `SHA256:Y2QmgEV3aB9cc7lUrMOynkLWVQ5FTl2rTOUYyQXFYSM` (ED25519); a batch SSH authentication probe for `sanro` was rejected with `Permission denied (publickey)`. This is not independent verification of the VPS/account identity. Registration requires the Owner's public key and successful authentication to the verified target; private keys must never be sent or committed.

Revocation, once separately registered, is to remove only the exact matching public-key line from `/home/sanro/.ssh/authorized_keys` on the verified host, preserve other entries, and re-check owner/mode (`~/.ssh` 0700, `authorized_keys` 0600). No SSH daemon/firewall/sudo setting is needed or authorized.

## Test evidence and acceptance

Mocked CLI tests cover fixed command construction, auth/project/workspace checks, duplicate session reuse, status/output/cancel, interrupted-state non-replay, no auto-start on read-only status, output bounds and remote-machine rejection. A Python synthetic test verifies opt-in idle/working/done OSC status. These are unit/synthetic results only. Live Core, SSH key registration, VPS resource check, Android session visibility and owner acceptance are NOT TESTED.


## Owner-supplied Android key and current access check — 2026-11-25

The Owner supplied an Ed25519 public key labelled `herdr-mobile`. OpenSSH accepted its format; SHA-256 fingerprint is `SHA256:4VZviw2bb9DF6F1n0axjEQzeKug3yD/7DG0MrdEese0`. The key line was not added to this public repository.

Strict SSH host-key checking matched the existing local ED25519 known-hosts pin `SHA256:Y2QmgEV3aB9cc7lUrMOynkLWVQ5FTl2rTOUYyQXFYSM`. A batch connection to `sanro@13.140.185.9:22` was rejected with `Permission denied (publickey)`. Therefore the account identity/session was not authenticated, the key was not registered, and `authorized_keys` ownership/mode were not inspected or changed. Host-key pin match alone is not proof of account ownership.

No authenticated VPS resource/runtime check was possible. Herdr Core `0.1.22` remains a candidate pin only; no binary was selected, checksum verified, or installed. No worker/session was launched. Herdr Android is **NOT READY**; do not press **Check again** until the key has been registered on the verified account and the isolated Core session is visible. After that, Owner confirmation is still required to claim Android acceptance.

TokenEconomizer remains separate: the prior isolated Codex pilot is prepared, but five-hook trust, invocation, and any Herdr Codex-session compatibility are not verified. No global hook/config changes were made.
