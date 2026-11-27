# SANRO QA native Hermes profile integration V1

## Contract and scope

This package targets the installed Hermes v0.22.0 plugin contract: a directory plugin has `plugin.yaml`, `__init__.py`, and `register(ctx)`, with tools registered through `ctx.register_tool`. The manifest requires Hermes `>=0.22.0`. It declares no hooks and no privileged plugin capabilities. Source references: [v0.22.0 plugin guide](https://raw.githubusercontent.com/NousResearch/hermes-agent/v0.22.0/website/docs/user-guide/features/plugins.md), [v0.22.0 plugin runtime](https://raw.githubusercontent.com/NousResearch/hermes-agent/v0.22.0/hermes_cli/plugins.py), and [v0.22.0 plugin CLI](https://raw.githubusercontent.com/NousResearch/hermes-agent/v0.22.0/hermes_cli/plugins_cmd.py).

The two tools submit only fixed operations for the pilot project ID `sanro-browser-qa` to `http://127.0.0.1:8787/api/projects/sanro-browser-qa/runtime-acceptance`. API auth must independently bind that ID to the exact SANRO-Browser-QA repository, workspace, branch, worker identity, fixed profiles, mandate and scopes; the plugin does not create or broaden that registry entry.

| Tool | Workforce profile | Fixed operation | Timeout |
|---|---|---|---:|
| `sanro_qa_browser_smoke` | `sanro-qa-browser-smoke` | `browser_smoke` | 150 s |
| `sanro_qa_private_browser_acceptance` | `sanro-qa-private-browser-acceptance` | `private_browser_acceptance` | 300 s |

Tool arguments accept only schema version 1 and a bounded idempotency/job ID. They cannot provide a command, URL, filesystem path, project, profile, operation, or approval scope. The client rejects redirects, bounds the HTTP timeout and response read, requires profile-provided bearer authorization and approval reference, and returns only a sanitized status/job/project/operation tuple. Workforce API project ACL, the project-bound QA/local-ci profile, operation scope, unexpired approval, native per-job approval callback, Local CI, and the existing isolated runtime remain authoritative. A missing callback or approval fails closed. No tool directly starts a process or browser.

## Isolation and activation status

### Chromium Runtime Recovery lock

The Chromium Runtime Recovery milestone is **LOCKED / VERIFIED RUNTIME** from the preserved native Local CI result at `docs/evidence/SANRO_CHROMIUM_NATIVE_QA_20261128.m7u7kJ/` (exit code 0; Chromium 159.0.8154.6; namespace/PID/network/Seccomp-BPF/TSYNC PASS; screenshot and cleanup PASS; Yama Non-broker WARNING). The existing Workforce `private_browser_acceptance` adapter now passes only `/usr/local/lib/sanro-playwright/chromium-1255/chrome-linux64/chrome` into an ephemeral project MCP configuration with `chromiumSandbox=true`, and verifies the trusted executable appears in the browser process tree. It refuses missing/substituted binaries and has no Playwright-cache fallback. This is source integration only; it was not launched by this continuation and does not create the `sanro-browser-qa` registry binding.

### Current dispatch blocker and supported route

The Hermes client target is `sanro-browser-qa`, while the existing Workforce private-browser runtime operation is explicitly restricted to project `sanro-ai-workforce` and uses the Workforce checkout's fixed entrypoint. The `sanro-browser-qa` Project Registry row still lacks canonical workspace, authorized branch/source SHA, worker ID, private mandate and matching entrypoint. Do not repoint or enable the profile to cross this boundary. The existing Workforce API accepts runtime dispatch only when a genuine host `nativeApprovalProvider` is injected; default server startup rejects it with 503. Hermes v0.22's official plugin/approval interfaces can submit fixed tool requests and route an existing human approval, but do not create that per-job native approval provider. Enabling the plugin alone cannot unblock execution.

Minimal supported continuation: bind the exact QA checkout and its fixed browser operation in the private Workforce registry, then have the authorized host supply a provider through the existing `createApp({ nativeApprovalProvider })` seam that obtains an actor/project/job/operation-bound native approval. Only then can the existing `sanro-qa` plugin issue its fixed `private_browser_acceptance` request through Workforce. Until both are present, keep profile/plugin inactive; do not use a synthetic callback or direct executor substitute.

The manifest now declares both `SANRO_QA_WORKFORCE_BEARER_TOKEN` and `SANRO_QA_APPROVAL_REF` with Hermes `requires_env` secret prompting. Values are never stored in the repository or copied from the default profile. The plugin is not installed/enabled and no secret was inspected or provisioned. The profile and default profile use the same OS user; a Hermes profile is configuration separation, not an OS security boundary. The loopback Workforce API and a genuine native per-job approval provider must be available before enabling the plugin. Hermes v0.22's documented approval transport does not create that provider; the current host preflight exits blocked without changing profile state.

Do not enable while `sanro-qa` is serving a session through a live gateway. Enabling is a profile-scoped configuration change and may change tools visible to sessions using that profile. This work did not run Hermes CLI, alter the profile, change gateway/default profile/hooks, or start a Local CI/Playwright job. No host command is authorized by the current “do not activate” boundary.

## One reviewed activation and rollback procedure

Prerequisites: a separate explicit Owner approval for enabling this candidate; the existing native `sanro-qa` profile; Hermes v0.22+; reviewed Workforce host auth profile for this exact project and the two fixed runtime operation IDs; an approved per-job native callback; Local CI runtime available; and a maintenance window in which no `sanro-qa` gateway session is active. If any prerequisite is absent, stop. Do not create/copy credentials or weaken any hook.

From the Workforce checkout, as `sanro` on the VPS, the single activation invocation is:

```sh
python3 integrations/hermes/sanro_qa_runtime/profile_activation.py --activate
```

The helper stages only `plugin.yaml`, `__init__.py`, and `client.py` under the existing `~/.hermes/profiles/sanro-qa/plugins/sanro-qa-runtime`, rejects an unexpected profile path, symlink, or conflicting existing package, runs the official profile-scoped `hermes -p sanro-qa plugins doctor <path> --ci`, then `hermes -p sanro-qa plugins enable sanro-qa-runtime`. It suppresses command output to avoid leaking local configuration. On nonzero exit, stop and inspect locally; it does not print secrets or error details. Stage-only review is `python3 integrations/hermes/sanro_qa_runtime/profile_activation.py --stage`.

Rollback invocation, if activation had been separately approved, is:

```sh
python3 integrations/hermes/sanro_qa_runtime/profile_activation.py --rollback
```

This runs the official profile-scoped disable command and leaves staged source in place for review; it does not remove profile data or alter gateway/default profile/hooks. Confirm only `sanro-qa-runtime` is disabled in that profile. If doctor/enable/disable fails, do not edit Hermes config manually; preserve the failure locally and stop.

## Acceptance and evidence

Implemented and locally tested: tool registration contract, closed schemas, project/operation mapping, no-hook registration, fail-closed missing authorization, redirect rejection, response sanitization, package staging idempotency, conflict/path refusal, existing fixed executor policy, protected path denial, and Backup/DR gate regressions.

Not tested: host staging, official `plugins doctor` against installed Hermes, enable/rollback, gateway effect, API callback/token/approval availability, Local CI job, browser/Playwright, screenshot, runtime cleanup, live Hermes continuity. No native activation or runtime PASS is claimed. See `docs/evidence/SANRO_QA_NATIVE_HERMES_PROFILE_V1_20261126.json`.
