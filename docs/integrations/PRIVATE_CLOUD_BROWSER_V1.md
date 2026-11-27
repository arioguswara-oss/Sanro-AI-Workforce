# SANRO Private Cloud Browser V1

## Status

The project now contains a fixed, project-scoped host runtime controller and acceptance path. It reuses the pinned Microsoft Playwright MCP `0.0.86`, project-local browser cache, isolated Chromium configuration, existing seven-tool allowlist, Workforce approval path, and runtime executor wrapper. **The host systemd boundary and Chromium acceptance have not run on the VPS; service activation remains blocked until an official native runtime callback and private profile registration are supplied.** No dependency was installed or changed.

The current Codex session cannot reach an authorized host executor. `ssh-add -l` returned `Error connecting to agent: No such file or directory`; `hc machine ls` returned no machines. `hc server status` confirmed the existing Hermes Core is live, but exposes no shell execution capability. No SSH connection or remote command was attempted. The previously reviewed Workforce runtime wrapper applies seccomp that denies socket syscalls, so it cannot host MCP HTTP without a separately reviewed compatible host execution boundary. It has not been weakened or bypassed.

## Host runtime controller

Runtime requests use the authenticated Workforce `runtime-acceptance` route, its project principal scopes, active `runtime:browser` approval record, mandate admission, and native approval callback. They enter a bounded, single-active FIFO (up to 16 waiting runtime requests) and the fixed wrapper rejects any project except `sanro-ai-workforce` for this operation. Generic shell/profile arguments cannot select another executable. The runner is only called after the wrapper validates project, branch, repository, clean source SHA, mandate, approval evidence, and job identity.

The private host authorization config must define the fixed profile (the token/reference values remain in that private config):

```json
"private-browser": {
  "command": ["/usr/bin/true"],
  "projects": ["sanro-ai-workforce"],
  "role": "qa",
  "executor": "local-ci",
  "runtime_operation": "private_browser_acceptance",
  "runtime_timeout_seconds": 180
}
```

The wrapper starts the acceptance script only through a transient **systemd user service**. The fixed unit sets `CPUQuota=100%`, `MemoryMax=2G`, `TasksMax=128`, `RuntimeMaxSec` to the approved job timeout, `TimeoutStopSec=3s`, `KillMode=control-group`, `PrivateNetwork=yes`, `PrivateTmp=yes`, `NoNewPrivileges=yes`, and `ProtectSystem=strict`; only that job's private root (scratch and artifacts) is writable. The service command begins with `/usr/bin/env -i`, so the browser receives only a minimal clean environment. Missing systemd/cgroup/network-namespace enforcement fails closed. The runner verifies a distinct network namespace, loopback as its only interface, no default route, the live cgroup limits, non-root UID, sandbox-enabled config, and absence of Chromium `--no-sandbox`. It probes an external IP, the metadata IP, and an unrelated local port and requires each connection to fail. The MCP and fixture listeners bind to `127.0.0.1` inside that job network namespace; other host loopback services and all external targets are unreachable from the job.

The Workforce API serializes runtime callback execution globally. The existing runtime wrapper additionally holds the project worktree lock and rejects replayed job IDs. The systemd unit's runtime limit and control-group kill policy bound/clean child processes; the runner closes MCP and fixture processes and preserves only the successful synthetic screenshot. Source tests do not verify that target systemd delegated these controls; the acceptance runner checks their actual cgroup and namespace state before launching Chromium.

## Acceptance entrypoint

`apps/web/scripts/private-browser-mcp-acceptance.mjs` is the synthetic acceptance entrypoint. Direct invocation is refused unless it detects the required private network namespace and cgroup limits. It:

- refuses root and verifies the pinned package, Chromium executable, dynamic libraries, and `chromiumSandbox: true`;
- records host CPU count, available/total memory, kernel, user-namespace visibility, and AppArmor availability;
- starts the official Playwright MCP process and synthetic fixture on ephemeral `127.0.0.1` ports only, after verified default-deny network isolation;
- uses a per-job active-job lock and fails closed on replay; the authenticated API FIFO and wrapper's project worktree lock enforce one active job;
- performs MCP `initialize`, `tools/list`, Chromium navigation, DOM snapshot, form fill, click, JavaScript state check, PNG screenshot, and browser close;
- keeps the screenshot in a mode-0700 per-run directory outside the repository, reports its SHA-256, and samples Chromium/MCP process-tree RSS and CPU ticks;
- confirms the browser child ran without `--no-sandbox`, terminates the MCP child, closes the fixture server, and removes temporary artifacts on a blocked run.

Use the existing authenticated Workforce runtime API only after the official native runtime callback and the private `private-browser` QA profile have been registered in the host's private authorization config. That callback must invoke the existing wrapper and its transient systemd boundary; do not launch this script or `systemd-run` directly from a terminal. The single acceptance request is:

```sh
curl --fail-with-body --request POST "${WORKFORCE_API_URL}/api/projects/sanro-ai-workforce/runtime-acceptance" --header "Authorization: Bearer ${WORKFORCE_OWNER_TOKEN}" --header "Content-Type: application/json" --data '{"profile":"private-browser","approval_ref":"<existing approved runtime:browser reference>","idempotency_key":"private-browser-v1-acceptance-20261126"}'
```

The API authenticates the caller and checks the project approval. Its native runtime adapter must obtain/validate the actual native approval and invoke the existing wrapper. It currently is **not registered**, so this request is not executable yet and must not be sent as a runtime attempt. The supplied host AppArmor/user-namespace values have not proven systemd `PrivateNetwork` availability; if that property cannot be created, the unit must fail closed. Do not weaken AppArmor or kernel settings. Capture API evidence, systemd unit outcome, screenshot digest, cgroup/network checks, resource use and cleanup in the private runtime audit after activation.

## Service boundary and activation gates

The acceptance runner is a temporary loopback MCP process; it is not a persistent authenticated service. Playwright MCP documents that it is not itself a security boundary. Its origin allowlist is only a browser feature and does not constrain redirects or arbitrary egress. Therefore the runner does not claim to provide the production service controls below, and it must not be registered for general client use yet.

Before service activation, the authorized host executor must provide and verify all of these controls without changing global policy:

1. A non-root, per-job process launched only after Workforce project/job/mandate/native-approval admission. The API runtime FIFO serializes jobs; the private browser boundary allows one active job.
2. A loopback-only official MCP HTTP endpoint isolated inside the job's private network namespace. The raw Playwright MCP port is not exposed to host peers or remote clients; no public listener or CDP port.
3. Per-project/job browser state and artifact directories with owner-only permissions, systemd hard runtime timeout, automatic process/artifact cleanup, and cgroup CPU/memory/task limits.
4. Default-deny egress enforced outside Chromium using `PrivateNetwork=yes`; only job-local loopback is available. Acceptance rejects external, metadata and unrelated host-loopback probes. No arbitrary authorized website access is enabled.
5. Redacted audit records with actor, project, job, approval reference digest, tool names, outcome, resource measurements, screenshot digest, and cleanup result. Never record credentials, page payloads, or screenshot bytes in logs.
6. A reviewed project-only Codex HTTP registration after the endpoint is running. Preserve Hostinger. Hermes registration remains inactive until an official isolated Hermes profile/runtime interface is identified and reviewed; do not restart Hermes.

The official Codex configuration should use its supported HTTP MCP `url` field for a service URL ending in `/mcp` ([OpenAI Docs: Codex MCP configuration](https://developers.openai.com/learn/docs-mcp)). Do not write the entry into `.codex/config.toml` until a loopback/tunnel route and gateway authentication are actually available. No Hermes MCP registration method has been verified in this repository, so none is proposed as active.

## Current execution evidence

- Host-preflight values supplied by Owner: UID 1001, 4 vCPU, 7.8 GiB RAM, 3.2 GiB available, 1.7 GiB swap used, Node 22.22.1, `unprivileged_userns_clone=1`, and `apparmor_restrict_unprivileged_userns=1`. These are reported preflight values, not measurements made by the acceptance runner.
- This continuation implemented source-level admission, API serialization, systemd transient-unit settings and runner boundary checks. It did not run systemd or Chromium on the VPS, change host policy, touch Hermes/worker processes, or access production.
- The previous Codex sandbox Chromium failure remains historical and was not repeated. No host PASS, browser version, actual cgroup/resource measurement, screenshot, or cleanup result is claimed.
- Authentication/admission and the systemd launch boundary are implemented in source, but official native runtime callback/profile registration and systemd user-unit availability remain activation gates. Codex HTTP/Hermes registration remains inactive.

See `docs/evidence/PRIVATE_CLOUD_BROWSER_V1_20261126.json` for current blocked status, approval counts, and the evidence delta.
