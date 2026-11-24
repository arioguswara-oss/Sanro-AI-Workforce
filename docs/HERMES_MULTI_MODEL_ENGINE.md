# Hermes Multi-Model Engine (WF-MME-001)
Date: 2026-11-24. Priority: P0. Status: PLANNED / NOT IMPLEMENTED / NOT TESTED.
Companion to BUILD_PLAN.md; dependency of Phase 4 and release gate of Phase 5. No runtime or spending authorization.

## Architecture
Retain existing Hermes/Codex authentication and serial worker lock. Evaluate native Hermes fallback first, 9Router as first free-only fallback, FreeLLMAPI as optional second fallback only if it adds measurable independent capacity. Use isolated local endpoints, not public listeners. Upstream candidates: https://github.com/decolua/9router and https://github.com/Pendia/FreeLLMAPI. Verify pinned versions, licenses, provider terms and actual supported interfaces before installation. ChatGPT subscription is not an API credit balance; do not bypass provider limits or use unsupported authentication.

## Policy
- Zero incremental AI spend; deny paid routes, automatic top-ups and unknown pricing. No new VPS or services without approval.
- Provider registry: model ID, capabilities, context limit, tool calling, data policy, quota/reset, health, cost class, allowed projects. Deduplicate shared upstream quota across routers.
- Route only to approved providers for each project/data classification. Never send secrets, customer records or private code to unapproved providers. Enforce permissions outside the model.
- On confirmed quota exhaustion or transient failure, bounded retries/backoff and circuit breaker; no retry loops on invalid requests or policy denials. On auth failure, isolate provider and report. Fail back to primary at safe job/session boundary after health/quota check.
- Persist job ID, project, repo, SHA, worktree, task state, last completed tool operation, provider and retry state. Reconcile side effects before resuming; never blindly replay writes. If no eligible provider, checkpoint and wait with bounded health probes.
- Keep credentials and private evidence on Hermes, redact logs, no secrets in public GitHub. Preserve existing mandates, tool allowlists and approval gates regardless of model.

## Implementation backlog
1. MME-01: read-only audit Hermes version, fallback semantics, CPU/RAM/disk, existing auth and active services; assess provider terms.
2. MME-02: isolated 9Router pilot with 3–5 eligible free models; verify endpoint, structured tool calls, coding and context limits. No active worker changes.
3. MME-03: integrate native fallback and failback in isolated pilot, cost deny policy, checkpoint/resume and idempotency.
4. MME-04: evaluate FreeLLMAPI incremental independent quota and operational overhead; add only if justified.
5. MME-05: SANRO Studio synthetic or authorized non-production job, simulated quota exhaustion, coding→QA→Draft PR, 24h observation and reporting.

## Acceptance
PASS requires actual evidence tied to SHA and job ID: primary success; simulated 429 fallback; tool calling; bounded retries; all providers unavailable checkpoint; restart/resume without duplicate writes; primary recovery; zero paid calls; secret redaction; cross-project isolation; existing workers unaffected. Record latency, success rate, quota and cost evidence. No guaranteed 24/7 inference or unlimited free tokens. No progress credit for documentation alone.

## Approval
This proposal does not authorize VPS install, new credentials, provider signup, paid APIs, staging writes, merge or production changes. Existing scoped mandates remain unchanged. Report blockers and request only missing critical authorization.

## Checkpoint 2026-11-24 — Owner handoff
Reported, not independently runtime verified: Gateway/Telegram working; Codex CLI 0.162.1; delegation and repo audit reported success; GitHub read and isolated workspace PASS; initial integration 8/10. Gemini Flash Lite instability/rate limits; Qwen 1.7B inconsistent tools; background FAIL; concurrency NOT TESTED; Telegram response ~11 min with irrelevant tool call; repeated Backup/DR approvals on read-only tasks. Both autonomous crons remain PAUSED. Do not repeat passing tests without relevant changes.

## P0 recovery and two-lane architecture
Read-only audit: correlate sanitized gateway timing, primary/auxiliary retries, timeout, session lock, subprocess lifecycle, queue and approval rule IDs. Hypotheses: synchronous wait, retry amplification, inappropriate tools/model, overbroad policy. No restart, cron resume or Studio/production changes.
Conversation lane: independent session, general chat and sanitized ledger status, no terminal by default. Engineering lane: persistent job ID, serial FIFO, existing Codex delegation, isolated workspace, async acknowledgement and completion via existing Telegram. Reconcile uncertain side effects before retry. Retain critical approvals. Future marketing and support profiles require separate budgets and tenant isolation.
Router review: Hermes native main/aux fallback; 9Router combo, quota and tool/stream translation; FreeLLMAPI profiles, streaming, context catalog and per-key limits documented, local tests pending. Sources: https://hermes-agent.nousresearch.com/docs/user-guide/configuration ; https://github.com/decolua/9router/releases ; https://github.com/Pendia/FreeLLMAPI . FreeLLMAPI personal experimentation scope excludes production support unless permitted. Use approved provider access only, no identity spoofing or limit evasion. Pin reviewed release; avoid nested retries. Exclude Qwen 1.7B from engineering until qualified.
Next: (1) runtime audit (2) isolated split-lane design and concurrency test (3) 9Router free-only qualification with synthetic fixtures (4) FreeLLMAPI only if permitted and incremental value (5) fallback/resume and approval isolation evidence. Test tool schemas/IDs/results, streaming termination, non-stream auxiliary, context, 429 cooldown, zero paid calls.
Proposed targets: acknowledgement <=5s, general reply p95 <=30s across 20 synthetic prompts, zero irrelevant general-chat tool calls, two concurrent conversation requests during one serial job, no duplicate writes. Not measured.
Runtime audit BLOCKED: no authorized terminal access in current chat. Documentation only, implementation delta 0%. No runtime changes.
