# SANRO QA native Hermes profile integration V1

## Contract and scope

This package targets the installed Hermes v0.22.0 plugin contract: a directory plugin has `plugin.yaml`, `__init__.py`, and `register(ctx)`, with tools registered through `ctx.register_tool`. The manifest requires Hermes `>=0.22.0`. It declares no hooks and no privileged plugin capabilities. Source references: [v0.22.0 plugin guide](https://raw.githubusercontent.com/NousResearch/hermes-agent/v0.22.0/website/docs/user-guide/features/plugins.md), [v0.22.0 plugin runtime](https://raw.githubusercontent.com/NousResearch/hermes-agent/v0.22.0/hermes_cli/plugins.py), and [v0.22.0 plugin CLI](https://raw.githubusercontent.com/NousResearch/hermes-agent/v0.22.0/hermes_cli/plugins_cmd.py).

The two tools submit only fixed operations for project `sanro-ai-workforce` to `http://127.0.0.1:8787/api/projects/sanro-ai-workforce/runtime-acceptance`:

| Tool | Workforce profile | Fixed operation | Timeout |
|---|---|---|---:|
| `sanro_qa_browser_smoke` | `sanro-qa-browser-smoke` | `browser_smoke` | 150 s |
| `sanro_qa_private_browser_acceptance` | `sanro-qa-private-browser-acceptance` | `private_browser_acceptance` | 300 s |

Tool arguments accept only schema version 1 and a bounded idempotency/job ID. They cannot provide a command, URL, filesystem path, project, profile, operation, or approval scope. The client rejects redirects, bounds the HTTP timeout and response read, requires profile-provided bearer authorization and approval reference, and returns only a sanitized status/job/project/operation tuple. Workforce API project ACL, the project-bound QA/local-ci profile, operation scope, unexpired approval, native per-job approval callback, Local CI, and the existing isolated runtime remain authoritative. A missing callback or approval fails closed. No tool directly starts a process or browser.

## Isolation and activation status

The plugin is a candidate and is not installed/enabled in the host profile by this change. The profile and default profile use the same OS user; a Hermes profile is configuration separation, not an OS security boundary. Do not put credentials in this repository or copy them from another profile. The host profile must already receive its own authorized Workforce token and approval context through the existing secret mechanism; no such secret was inspected or provisioned in this work. The loopback Workforce API and its native approval callback must be available before enabling the plugin. Same-UID local processes can potentially connect to loopback, so loopback binding is not a substitute for authentication and runtime isolation.

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
