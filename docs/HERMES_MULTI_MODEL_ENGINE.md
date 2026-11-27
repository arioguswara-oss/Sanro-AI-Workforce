# Hermes Multi-Model Engine (WF-MME-001)
Date: 2026-11-24. Priority: P0. Status: LOCAL ADAPTER CANDIDATE IMPLEMENTED / MOCK-TESTED; PROVIDERS NOT LIVE-TESTED.
Companion to BUILD_PLAN.md; dependency of Phase 4 and release gate of Phase 5. No runtime or spending authorization.

## Architecture
Retain existing Hermes/Codex authentication and serial worker lock. Evaluate native Hermes fallback first. Treat 9Router as an OpenAI-compatible candidate only if its downstream routing can be pinned and verified free-only; otherwise it is excluded by policy. Evaluate FreeLLMAPI only if its isolated pool adds measurable independent capacity and provider terms permit the data. Use loopback endpoints, not public listeners. Upstream candidates: https://github.com/decolua/9router and https://github.com/Pendia/FreeLLMAPI. Verify pinned versions, licenses, provider terms and actual supported interfaces before installation. ChatGPT subscription is not an API credit balance; do not bypass provider limits or use unsupported authentication.

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

## Local provider adapter checkpoint — 2026-11-24

`provider_adapters.py` implements the OpenAI chat-completions request/response shape used by the current 9Router and FreeLLMAPI documentation. 9Router documents an OpenAI-compatible endpoint; its routing includes subscription, cheap/paid, and free tiers, so this code's `cost_usd_per_million == 0` check cannot certify the router's internal downstream tier. A 9Router deployment would need a separately verified free-only configuration. FreeLLMAPI documents `/v1/chat/completions`, tool-call payloads, and a local default endpoint; the candidate does not start it or provide keys. Sources: [9Router endpoint guide](https://github.com/decolua/9router/blob/master/gitbook/content/en/integration/other-tools.md), [9Router routing tiers](https://docs.9router.com/), [FreeLLMAPI REST API](https://github.com/emmgmm/FreeLLMAPI/blob/main/docs/en/api/01-rest-api.md).

Eight routing/provider tests use injected mock transports only. They verify schema adaptation, 429 cooldown, bounded fallback, failback after cooldown, checkpoint metadata without prompt text, pause/resume, and rejection of engineering execution. No live model calls, provider keys, downstream quota, price, context window, or tool reliability were tested. Conversation fallback is separate; engineering job execution remains assigned to Codex. Tool schemas returned by any fallback are data and are never executed by this adapter.

## Fallback semantics reconciliation

Hermes `fallback.min_switch_reset_seconds` is a reset-time deferral for switching after a rate-limit response. It is not a usage threshold and not a retry count; `0` disables the deferral. Hermes native retries/fallback are request/turn scoped. This correction reflects the previously inspected installed Hermes source; original JD-02 source evidence was not present here, so the JD-02 report itself was not independently re-audited.

## Mock implementation limits

The adapter only models providers explicitly declared with zero cost and an approved capability profile. It cannot independently verify an aggregator's internal routing, contract terms, data retention or quotas. It reads the configured key from the named environment variable only when explicitly called; the tests use synthetic keys and injected in-memory responses. Unverified model capabilities remain unavailable for engineering. Codex stays the preferred and only engineering executor until a separately approved live qualification.

## Checkpoint 2026-11-24 — Owner handoff
Reported, not independently runtime verified: Gateway/Telegram working; Codex CLI 0.162.1; delegation and repo audit reported success; GitHub read and isolated workspace PASS; initial integration 8/10. Gemini Flash Lite instability/rate limits; Qwen 1.7B inconsistent tools; background FAIL; concurrency NOT TESTED; Telegram response ~11 min with irrelevant tool call; repeated Backup/DR approvals on read-only tasks. Both autonomous crons remain PAUSED. Do not repeat passing tests without relevant changes.

## P0 recovery and two-lane architecture
Read-only audit: correlate sanitized gateway timing, primary/auxiliary retries, timeout, session lock, subprocess lifecycle, queue and approval rule IDs. Hypotheses: synchronous wait, retry amplification, inappropriate tools/model, overbroad policy. No restart, cron resume or Studio/production changes.
Conversation lane: independent session, general chat and sanitized ledger status, no terminal by default. Engineering lane: persistent job ID, serial FIFO, existing Codex delegation, isolated workspace, async acknowledgement and completion via existing Telegram. Reconcile uncertain side effects before retry. Retain critical approvals. Future marketing and support profiles require separate budgets and tenant isolation.
Router review: Hermes native main/aux fallback; 9Router combo, quota and tool/stream translation; FreeLLMAPI profiles, streaming, context catalog and per-key limits documented, local tests pending. Sources: https://hermes-agent.nousresearch.com/docs/user-guide/configuration ; https://github.com/decolua/9router/releases ; https://github.com/Pendia/FreeLLMAPI . FreeLLMAPI personal experimentation scope excludes production support unless permitted. Use approved provider access only, no identity spoofing or limit evasion. Pin reviewed release; avoid nested retries. Exclude Qwen 1.7B from engineering until qualified.
Next: (1) runtime audit (2) isolated split-lane design and concurrency test (3) 9Router free-only qualification with synthetic fixtures (4) FreeLLMAPI only if permitted and incremental value (5) fallback/resume and approval isolation evidence. Test tool schemas/IDs/results, streaming termination, non-stream auxiliary, context, 429 cooldown, zero paid calls.
Proposed targets: acknowledgement <=5s, general reply p95 <=30s across 20 synthetic prompts, zero irrelevant general-chat tool calls, two concurrent conversation requests during one serial job, no duplicate writes. Not measured.
Runtime audit BLOCKED: no authorized terminal access in current chat. Documentation only, implementation delta 0%. No runtime changes.


## Development checkpoint — 2026-11-24

A local, standard-library free-only routing policy candidate is implemented in `model_routing.py`: it rejects nonzero/unknown cost, records per-route quota cooldown checkpoints, selects ordered eligible routes, fails back after cooldown expiry, and denies engineering tool eligibility unless explicitly marked verified. Five local tests pass. This is policy code, not provider integration: 9Router and FreeLLMAPI were not installed or called, and no model has been qualified for engineering tool execution.

Hermes source review corrects the reset setting semantics: `fallback.min_switch_reset_seconds` is not a usage/quota threshold or retry count. It defers switching only when a rate-limited primary reports a reset sooner than the configured number of seconds; the default `0` disables this deferral. Hermes fallback otherwise follows its retry/error policy and is turn-scoped. Original JD-02 evidence was unavailable in the development workspace, so this correction is based on installed Hermes source and does not claim a re-review of JD-02.

JD-04's worker candidate preserves FIFO, checkpoints, idempotency, cancellation, and approval/authorization checks. It drops inherited environment variables, but Landlock does not isolate process behavior or network access. Live integration remains BLOCKED pending a validated least-privilege execution boundary and real human approval-path verification.
