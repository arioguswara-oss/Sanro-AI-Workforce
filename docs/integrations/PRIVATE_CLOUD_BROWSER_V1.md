# SANRO Private Cloud Browser V1

## Status

This is a host execution and acceptance package, not an activated persistent browser service. It reuses the pinned Microsoft Playwright MCP `0.0.86`, the project-local browser cache, the existing isolated Chromium configuration, and the existing seven-tool MCP allowlist. No dependency was installed or changed.

The current Codex session cannot reach the authorized Hermes VPS: `ssh-add -l` returned `Error connecting to agent: No such file or directory`. No SSH connection or remote command was attempted. The previously reviewed Workforce runtime wrapper applies seccomp that denies socket syscalls, so it cannot host MCP HTTP without a separately reviewed compatible host execution boundary. It has not been weakened or bypassed.

## Host acceptance package

`apps/web/scripts/private-browser-mcp-acceptance.mjs` is the single bounded synthetic acceptance entrypoint. It:

- refuses root and verifies the pinned package, Chromium executable, dynamic libraries, and `chromiumSandbox: true`;
- records host CPU count, available/total memory, kernel, user-namespace visibility, and AppArmor availability;
- starts the official Playwright MCP process and synthetic fixture on ephemeral `127.0.0.1` ports only;
- uses a per-state-root active-job lock and fails closed if another run is active; the Workforce FIFO must still provide queueing before this runner is invoked;
- performs MCP `initialize`, `tools/list`, Chromium navigation, DOM snapshot, form fill, click, JavaScript state check, PNG screenshot, and browser close;
- keeps the screenshot in a mode-0700 per-run directory outside the repository, reports its SHA-256, and samples Chromium/MCP process-tree RSS and CPU ticks;
- terminates the MCP child, closes the fixture server, and removes temporary artifacts on a blocked run.

The exact one-shot invocation for the authorized non-root host executor, from this repository checkout, is:

```sh
SANRO_PROJECT_ID=sanro-ai-workforce SANRO_JOB_ID=private-browser-v1-acceptance-20261126 node apps/web/scripts/private-browser-mcp-acceptance.mjs
```

The executor must validate the Workforce project, branch, current mandate, zero-cost scope, job ID, and native approval before invoking it. The command is not to be run from the restricted Codex sandbox. On the host, capture its JSON output and exit status in the private runtime audit. Stop after the first host launch failure; inspect its exact root cause before any different method is considered.

## Service boundary and activation gates

The acceptance runner is a temporary loopback MCP process; it is not a persistent authenticated service. Playwright MCP documents that it is not itself a security boundary. Its origin allowlist is only a browser feature and does not constrain redirects or arbitrary egress. Therefore the runner does not claim to provide the production service controls below, and it must not be registered for general client use yet.

Before service activation, the authorized host executor must provide and verify all of these controls without changing global policy:

1. A non-root, per-job process launched only after Workforce project/job/mandate/native-approval admission. One active job initially; the existing FIFO decides admission.
2. A loopback-only official MCP HTTP endpoint behind an authenticated client gateway. The raw Playwright MCP port must not be reachable by other users or remote clients; no public listener or CDP port.
3. Per-project/job browser state and artifact directories with owner-only permissions, hard session timeout, automatic process/artifact cleanup, and bounded per-job CPU and memory.
4. Default-deny network egress enforced outside Chromium by an approved per-service network boundary. Explicitly reject loopback, private, link-local, metadata, and unauthorized DNS/IP destinations, including redirect and subresource paths. Add destinations only after the project policy authorizes them.
5. Redacted audit records with actor, project, job, approval reference digest, tool names, outcome, resource measurements, screenshot digest, and cleanup result. Never record credentials, page payloads, or screenshot bytes in logs.
6. A reviewed project-only Codex HTTP registration after the endpoint is running. Preserve Hostinger. Hermes registration remains inactive until an official isolated Hermes profile/runtime interface is identified and reviewed; do not restart Hermes.

The official Codex configuration should use its supported HTTP MCP `url` field for a service URL ending in `/mcp` ([OpenAI Docs: Codex MCP configuration](https://developers.openai.com/learn/docs-mcp)). Do not write the entry into `.codex/config.toml` until a loopback/tunnel route and gateway authentication are actually available. No Hermes MCP registration method has been verified in this repository, so none is proposed as active.

## Current execution evidence

- Last tested source SHA: `397b7cb1884023b875d182927095a54f9d15ab8f`.
- Authorized VPS capacity is **reported** as 4 vCPU / 8 GB RAM, not measured in this session. The acceptance runner records actual host values and peak process-tree resources when the authorized executor can invoke it.
- This session did not launch Chromium, change host policy, touch the Hermes Core, inspect or signal workers, or access production.
- The previous sandbox Chromium failure remains: `No usable sandbox`, `SIGTRAP`. This method was not repeated. The host package has not run, so no host PASS, browser version, resource measurement, or screenshot is claimed.
- Codex and Hermes service integration: NOT ACTIVE. Authentication/project-job gateway, default-deny network enforcement, persistent queueing/session supervisor, and host runtime registration remain implementation/activation gates.

See `docs/evidence/PRIVATE_CLOUD_BROWSER_V1_20261126.json` for current blocked status, approval counts, and the evidence delta.
