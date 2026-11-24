# Development task ledger — 2026-11-24

## Completed local implementation checkpoints
- JD-03 source directory has no Git history. Public import is preserved as isolated approval-gate and structured-inspection modules; path-specific machine details were generalized.
- JD-04 local history: `8f02f4b` initial worker/pilot, `636aa2d` routing and environment hardening, `338ef55` ledger checkpoint. Imported in repository commits `1d9c2e1` (JD-03) and `eb2bdd2` (JD-04).
- JD-03 validation: **29 PASS / 0 FAIL** using an isolated copy; initial fixture omission caused one test error, then the corrected fixture run passed all tests.
- JD-04 validation: **27 PASS / 0 FAIL** on imported tree (worker, adapter, native-plugin, routing suites).
- Secret-pattern scan: 28 public candidate files, 0 matches; no env files. Syntax/diff checks are recorded in `DEVELOPMENT_CHECKPOINT.md`.

## Status
- IMPLEMENTED: isolated JD-03 and JD-04 candidates, tests, sanitized integration documentation, capability registry, and development checkpoint.
- VERIFIED: synthetic suites and isolated native Hermes plugin loader pilot as stated in evidence.
- BLOCKED: live worker activation pending process/network/credential isolation and live approval-path verification.
- NOT TESTED: live Telegram response concurrency, provider quota behavior, model quality/tool reliability, Web App/API, bot/group integration, autonomous end-to-end.

## Active boundaries
No Gateway restart, runtime config or approval-gate change, cron activation, production write, SANRO Studio change, paid service, merge, or deployment. Branch base: `main` at `78fd2ab1f7cf4d77c01f5659e04c3217f489f5d2`; existing Draft PR #1 remains open and unchanged. Both autonomous cron jobs remain PAUSED.

## JD-05 continuous development checkpoint — 2026-11-24
- Recovered the feature branch at `57137d59ba17011e06382047a566faa9da33eb70`; local tree was clean before work. Draft PR #2 remains the authorized review target.
- IMPLEMENTED: Node API and private SQLite foundation (project ACL registry, logical role registry, conversations, task transitions, job bridge, approvals read view, audit events, durable checkpoints, explicit recovery/resume, loopback-only entry point).
- IMPLEMENTED: React/Vite source for project/thread/task/job/approval/activity views; bearer token stays in memory. JSX parses, but dependency install/build is NOT TESTED because the registry connection reset.
- IMPLEMENTED: worker seccomp network/process-group restrictions on top of Landlock; reduced child environment; timeout/cancellation; fast child exit status correction. Same-UID/kernel limitations remain, and no live Hermes activation is approved or verified.
- IMPLEMENTED: OpenAI-compatible adapter shape for 9Router/FreeLLMAPI endpoints, injected mock transport, rate-limit cooldown, bounded fallback, failback, private checkpoint metadata, pause/resume, and Codex-only engineering executor policy. Provider interfaces were tested with mocks only; no provider or credential was configured.
- TESTED: previous JD-03/JD-04 combined baseline **56 PASS / 0 FAIL**; current focused Python JD-04/provider suites **32 PASS / 0 FAIL** and Node API/supervisor suite **3 PASS / 0 FAIL**. These overlap prior JD-04 coverage and are not additive. JD-03 historical suite **29 PASS / 0 FAIL** was not rerun.
- Synthetic API measurements: submission **0.2734 s**, foreground API read **0.00057 s** in the latest passing run. Earlier pytest simulation and native Hermes pilot figures remain separate historical evidence.
- BLOCKED / NOT TESTED: Vite production build and browser run (registry failure); actual API network listener (sandbox `listen()` returns `EPERM`); model provider and quota behavior live; Telegram reporting; native Hermes approval/session mapping; full host/namespace isolation; live Gateway/runtime.
- Resume policy is explicit: interrupted jobs remain interrupted and are not replayed. A new job is created only after scoped recovery approval, caller confirms side effects are reconciled, and supplies a new resume key. The application stores a hash of the review note, not the note itself.
- Public source excludes real tokens/configuration/logs. Temporary API auth/state fixtures are created outside the repository and deleted by tests.
