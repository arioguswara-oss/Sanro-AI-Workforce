# SANRO Hybrid Git PoC V1 — Rootless Runner Activation

## Checkpoint

- Workforce branch: `feature/hermes-workforce-foundation`
- Baseline host evidence supplied by Owner: Gitea 28.1.0 at `127.0.0.1:3000`, SQLite, private pilot repository, and GitHub/Gitea `main` at `4436660bfc4dbdf11aadb0800b043c2c75ce6eaa`.
- Host activation is **not run from Codex**. The current Codex sandbox has no authorized VPS executor.
- Docker Rootless, runner registration, workflow dispatch, Chromium acceptance, Git synchronization and Hermes continuity remain **NOT VERIFIED**.

## Private Gitea endpoint design

`scripts/sanro-gitea-runner-bridge.py` is a fixed upstream TCP-to-Unix-socket bridge. It only connects to host `127.0.0.1:3000`; it accepts no upstream address from a client. The intended host service runs as `sanro-ci-runner` and creates one mode-0660 Unix socket at `/var/lib/sanro-ci-runner/gitea-3000.sock`.

The workflow mounts only that socket into its job container. A job-local TCP shim binds only the container's `127.0.0.1:3000`, so Gitea's existing ROOT_URL remains valid. Docker API sockets, host networking and host loopback access are not mounted or enabled. The runner configuration must allow only this socket, the Playwright browser cache read-only, and the private evidence directory.

This design has source-level review only. The socket service, Docker Rootless route, container reachability, other-host-service denial and returned URLs/artifacts have not been exercised. The workflow includes checks, but their presence is not acceptance evidence.

## Workflow template

`scripts/sanro-gitea-browser-qa.workflow.yml` is intended to be copied into `.gitea/workflows/` on `poc/rootless-runner-acceptance`. It is limited to manual dispatch and pushes to that PoC branch. It uses the Gitea job token for read-only checkout, Playwright 1.56.1, `chromiumSandbox: true`, a synthetic page, and SHA-bound PNG/JSON evidence. It does not use `actions/checkout`, privileged containers, the Docker socket, or `--no-sandbox`.

The host Playwright cache must be readable by the dedicated runner and compatible with Playwright 1.56.1. If the browser binary or sandbox is unavailable, the workflow should fail; it must not download Chromium or weaken the sandbox.

## Host provisioning gate

The host must have rootless Docker prerequisites already available, delegated subordinate UID/GID ranges for the dedicated identity, working user namespaces under current AppArmor policy, cgroup v2/systemd resource controls, and a repository-scoped Gitea runner registration token. No kernel/AppArmor/global security changes are permitted. Runner concurrency is 1; intended bounds are 1 CPU and 2 GiB for the rootless daemon/job cgroup and 512 MiB for the runner process.

Do not activate until a reviewed one-shot host installer verifies all prerequisites, installs only the dedicated rootless user services and bridge, registers only `sanro-admin/SANRO-Browser-QA`, performs branch-only fast-forward synchronization, dispatches the acceptance workflow, records the actual job ID/SHA/resource use, and rolls back only PoC-created units on failure. No such integrated activation script is present in this checkpoint.

## Acceptance ledger

| Gate | State |
|---|---|
| Gitea/SQLite and matching `main` SHA | VERIFIED by Owner-supplied evidence |
| Bridge and workflow source | IMPLEMENTED, host not activated |
| Docker Rootless / resource cgroups | NOT TESTED |
| Runner registration / repository scope | NOT TESTED |
| Container access only to Gitea endpoint | NOT TESTED |
| Checkout / Playwright / screenshot | NOT TESTED |
| PoC branch fast-forward sync | NOT TESTED |
| Hermes continuity | NOT TESTED in this session; no Hermes process was touched |
| Extra service cost | $0 reported; no service provisioned by this session |

Do not report the PoC as accepted until the host run produces a successful Gitea job record, matching commit SHA, screenshot digest, resource measurements, negative-access results and cleanup status.
