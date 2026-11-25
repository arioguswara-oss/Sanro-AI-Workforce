# Herdr integration candidate

Updated: 2026-11-25. This document records a disabled development candidate, not an installation or live integration.

## Workforce adapter update — isolated synthetic verification

The API can start the per-project Herdr supervisor after an engineering submission passes the existing command-profile, approval, project, and engineering-execute checks. Herdr mode additionally requires the server-side worker-control switch and the principal's project-scoped `worker:manage` grant. A controller instance is deliberately single-project and rejects a second project before queue insertion. Job creation returns without awaiting Herdr startup; startup failures are visible as `FAILED` in the scoped worker status endpoint. Read-only status does not start a terminal. Jobs and their serial FIFO remain in the durable Workforce queue, not in Herdr session state.

Worker names are deterministic project-scoped names (a normalized short slug plus a SHA-256 suffix); sessions also carry a hashed `sanro.project` label and run in that project's authorized workspace. Discovery and cleanup match both Workforce and project labels, so another project's session is not reused or stopped. The registered command is a fixed local Workforce supervisor, never caller-supplied. Codex command profiles must invoke `codex` directly; the bridge inserts `--no-daemon` immediately after it when missing and rejects wrapped executables. This verifies argv construction only; Codex authentication and an actual Codex task were not exercised.

The focused integration simulation used a mock `hc` CLI and launched the actual synthetic Python queue worker locally. It verified approved submission, immediate job ID, project-specific session naming/cwd/labels, job completion, status, logs/result retrieval, and cleanup. Submission through the mocked Herdr path measured **0.711 s**. Foreground read while a background synthetic worker ran measured **0.000872 s** in the separate FIFO API simulation. These are local simulation timings, not VPS/Herdr measurements. The installed Core binary, `t1`, Android Spaces, SSH identity, Codex model call, and Owner-reported 6 s pilot were not independently verified in this execution environment.

Official CLI contract used for implementation: [`hc` commands at v0.1.22](https://github.com/herdrdev/herdr-core/blob/v0.1.22/docs/commands.md) documents `run --bg --json --name --cwd --label --no-parent`, `ls`, `read`, and `kill`; [`SKILL.md at v0.1.22](https://github.com/herdrdev/herdr-core/blob/v0.1.22/crates/herdr-core/src/SKILL.md) documents terminal lifecycle and foreground Codex child sessions. The installed VPS CLI docs/version could not be inspected because SSH public-key authentication from this environment was denied.

## Compatibility verified from upstream

- Herdr Android connects directly to a machine using SSH; Herdr Core is the remote terminal runtime. Herdr does not require a public listener for the mobile connection.
- The documented `hc` CLI supports terminal creation, list/status, output read, and kill. The optional adapter uses these argv-based CLI calls and pins `herdr-core 0.1.22`, the version in the current official release manifest. That manifest lists per-platform SHA-256 values; the VPS architecture is unknown, so no target artifact/hash was selected or downloaded.
- The local Workforce API and durable FIFO worker remain authoritative for job submission, ACL, project/workspace binding, approvals, cancellation, logs/results and checkpoints. Herdr owns one named serial worker terminal and exposes worker lifecycle through OSC 7501 without including job content.
- The current adapter is co-located only. It rejects remote Herdr machine dispatch because the Workforce SQLite queue, API, code and workspace have no verified shared state or synchronization protocol across machines.

## Security and resource boundary

Herdr sessions run with the OS account's permissions and do not provide a sandbox or approval boundary. Same-account software can access the Herdr control socket; terminal output can retain sensitive data. Use a dedicated non-root account with no unrelated secrets, no production access, and a separately bounded workspace. Existing Workforce Landlock/seccomp controls apply only to child jobs started by the Workforce worker and do not sandbox the Herdr supervisor or provide a VM/kernel boundary. Do not enable the attestation flag until this environment is verified. The key used by Android must be treated as account-level SSH command access, not read-only monitoring.

No `hc` binary was found in the development workspace, VPS SSH authentication failed, VPS CPU/RAM/storage are unknown, and this execution did not start or attach to a Herdr server or Android session. Upstream describes Linux x86_64/aarch64 artifacts; actual target architecture and capacity remain unverified. Version `0.1.22` is the candidate pin; no artifact was installed or checksum verified on the target. Owner reports Herdr Core v0.1.22, terminal `t1`, Android discovery, and a 6-second Codex response; these remain owner-reported evidence.

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

TokenEconomizer remains separate: the prior isolated Codex pilot is prepared, but five-hook trust, invocation, and any Herdr Codex-session compatibility are not verified. Hooks remain untrusted and were not activated or invoked. No global hook/config changes were made.

## Runtime integration disposition — 2026-11-25

The opt-in adapter is still disabled for live services. A strict SSH attempt to `sanro@13.140.185.9:22` was denied with `Permission denied (publickey)`; the existing host-key pin was not changed. No process, `t1` session, service, or configuration on the VPS was touched. **HERDR ANDROID READY is not asserted by this execution**, because host account/runtime and installed CLI interfaces could not be independently authenticated. Do not press **Check again** based on this repository change alone; press it after an authenticated host check confirms that the intended isolated terminal remains visible, then confirm Android acceptance.

## Per-job lifecycle continuation — 2026-11-25

The project terminal now has `sanro.project_id`, `sanro.worker_name`, `sanro.execution_engine=hermes`, and `sanro.queue=serial` labels. The existing FIFO worker emits a separate OSC 7501 record per durable Job ID for active, completed/cancelled, failed, and recovered-interrupted work. The project worker read endpoint projects those records after validating the Job ID and app marker. This keeps the serial queue and approval/idempotency/recovery path authoritative; jobs are not dispatched outside that queue.

Validation includes API/Herdr **13 PASS**, worker/Hermes **21 PASS**, and a real synthetic job under a distinct `HC_SESSION` on Herdr Core `0.1.22`. The synthetic job reached queue `succeeded` and Herdr record `done`, and Core returned the expected project/worker/engine/queue labels. See [per-job synthetic acceptance evidence](evidence/HERDR_PER_JOB_SYNTHETIC_ACCEPTANCE.json). The isolated Core was stopped after the test. Existing external Codex/Hermes inventory remains unavailable; those Owner-reported sessions are `UNMANAGED` until PID/project/session mapping is verified. Owner's Android Spaces evidence for `sanro-monitor-test` is retained as OWNER-REPORTED; Android visibility of the new job records is NOT TESTED.
