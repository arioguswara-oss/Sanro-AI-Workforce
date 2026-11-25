# Hermes-first development checkpoint — 25 November 2026 Jakarta

Authorized repository/branch: `arioguswara-oss/Sanro-AI-Workforce`, `feature/hermes-workforce-foundation`; existing Draft PR #2. Starting remote SHA `6efeba5b0e0985da2feb352ad5c8877c262743bc`.

## Current implementation

Architecture is reconciled around existing Hermes conversation surfaces, Codex, Local CI and one existing Telegram transport. React/Vite source is preserved; standalone Workforce chat and four-bot roadmap are superseded. No Superadmin or other-project repository was changed.

JD-03/JD-04 candidates are reused. Native shim requires bound current actor/session (never route identity/environment fallback), authorized action scope, and literal native approval `true`. Pending/denied responses never enqueue. Worker rejects unsafe database targets, non-finite timeouts and idempotency content conflicts; seccomp validates architecture/x32. These controls do not establish full credential isolation or qualify authenticated Codex execution.

Free-only routing now disables unverified route selection/export, blocks unsafe credential-bearing endpoints/redirects, refuses completed/uncertain inference replay and preserves metadata checkpoints. Mocked fallback/failback/circuit/cooldown/resume pass. Canonical provider sources were inspected; 9Router and FreeLLMAPI remain disabled. No model API usage or paid service.

The deterministic Director binds private zero-cost project/repo/branch/environment mandates and fixed Codex/Local CI profiles. It checks actual clean Git scope before engineering, persists exact stage input before enqueue, advances Developer→QA→bounded self-fix→candidate→checkpoint→report, and supports bounded explicit reviewed recovery. Audit and release/blocker/critical-approval outbox are durable. Current workflow stops at a release candidate and queued report; per-job Draft PR creation and native Telegram delivery are not implemented live.

Monitoring is a dedicated GET-only scope, isolated from operational API routes. Real local HTTP tests verify project ACL and zero DB mutations/executor calls. It exposes sanitized persisted worker/job/run/queue/QA/approval/checkpoint data and explicit freshness. Model quotas and Hermes health remain unavailable. A presentation-only Virtual Office component is prepared; Superadmin is unchanged.

## Verification and provenance

- Tested remote source: **`44ed2cedb2f5d40829b3f215e1dd09026a91ed6d`**.
- Tested Git source tree: **`d25cbd37c120b311f5d5d615a19d2f6aa5322faa`**, identical to the local committed tree before verification.
- Python: **58 PASS / 0 FAIL / 11 NOT TESTED**.
- Node API/Director/real HTTP/real Git/controller: **11 PASS / 0 FAIL / 1 NOT TESTED**.
- Compiled monitoring render/security smoke: **1 PASS / 0 FAIL**.
- Both Vite builds, secret-pattern scan and diff check: **PASS**.
- Final evidence: [HERMES_FIRST_FINAL_ACCEPTANCE.json](evidence/HERMES_FIRST_FINAL_ACCEPTANCE.json). Initial failed combined run retained separately and resolved as described in [ACCEPTANCE_MATRIX](ACCEPTANCE_MATRIX.md).
- Current functional gate coverage: **20% → 80%, +60 percentage points over ten candidate gates**; documentation adds no software percentage. This is not live readiness.
- Public Hermes reference source `2506f5b0a4d310b96ec2eb6f2de4ea7349ba4d15` inspected via read-only AST contract probe; installed VPS version NOT VERIFIED.

Subsequent checkpoint/evidence commits change documentation and capability reporting only; tests are tied to the source SHA above, not claimed rerun at each documentation SHA. GitHub connector commits differ from local commit IDs; full source tree equality is verified after publishing.

## Runtime boundary and next work

Landlock ABI 0 blocks actual worker subprocess acceptance in this environment; security remains fail-closed. 12 dependent cases are NOT TESTED, not PASS. Existing worker confinement denies networking/process creation and lacks Codex credentials, so an approved existing Codex broker/admission path is still required. Private auth config is a snapshot; native dequeue/revocation must be verified on the host. No authenticated Hermes VPS access was available; browser reached Cloudflare Access login. No credentials, approval bypass, Gateway restart, live plugin activation, cron change, merge or production deployment occurred. Both cron jobs must remain PAUSED; actual remote state was not read.

## Herdr development follow-up — 2026-11-25

- Reconciled the eight subsequent feature-branch commits through `f909923` before adding the Herdr candidate; Director, monitoring, acceptance evidence and host handoff were preserved.
- Added a disabled co-located Herdr Core controller, explicit reduced supervisor environment, project/workspace authorization, duplicate session reuse, cancellation/status/output retrieval, no automatic replay, and opt-in OSC 7501 lifecycle status. Remote Herdr machines remain rejected until Workforce queue/workspace synchronization is implemented and verified.
- Current host Landlock ABI is 8 (the earlier ABI 0 finding above was environment/checkpoint-specific). Post-reconciliation focused results: **21 Node API tests PASS / 0 FAIL** and **10 Python worker tests PASS / 0 FAIL**. Latest synthetic job submit **0.220 s** and foreground read **0.000535 s**. These totals overlap the preceding acceptance results.
- Official Herdr Core `0.1.22` is pinned from the upstream release manifest. No target binary was installed or checksum-verified because VPS authentication and architecture/resources remain unknown. No Herdr Core session or Android connection was verified.
- Owner public SSH key was absent from the request; existing batch authentication was denied. No `authorized_keys`, SSHD, firewall, service, Hermes runtime, Telegram, cron, production, or other-project state was changed. Android acceptance remains pending Owner confirmation after the later target checks.

All remaining Hermes-specific work is consolidated in [HERMES_EXECUTION_HANDOFF](HERMES_EXECUTION_HANDOFF.md). GO for continued isolated development/host acceptance within mandate; **NO-GO for live activation or autonomous operation claim**. Live activation, production/merge and Superadmin changes require separate scoped approval after the missing runtime/security gates pass. No approval is needed to review this committed candidate.


## TokenEconomizer isolated pilot checkpoint — 2026-11-25

Prepared synthetic-only Codex pilot (existing v0.1.0) with separate `CODEX_HOME` and state. Effective runtime configuration: `envfacts` only (max 5 facts/200 tokens), `toolprune=off`, `loopguard=off`, `repomap=off`; config/state permissions `0600`/`0700`. No workers, global Codex, Gateway, 9Router, FreeLLMAPI, or project data changed. Landlock permits TCP 443 egress only for official sign-in; bind and other ports are denied. Filesystem exclusion preflight passed without reading credential values. No authentication, hook execution, model task, or benchmark occurred. **Owner gate:** sign in through ChatGPT in the pilot, then `/hooks` → **Trust all and continue**; restart and notify us before one brief synthetic smoke. Pilot trust only; global activation NO-GO pending separate approval. Token savings and quality comparison remain unmeasured. See TokenEconomizer pilot evidence.