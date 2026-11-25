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

## Herdr adapter implementation checkpoint — 2026-11-25

Starting synced feature SHA: `bcaf43feb31af4c17d39c39d49ebba9d9178cbe4`.

### Source changes

- Added deterministic project-specific Herdr terminal name and hashed project label. Discovery/cleanup only sees the matching project session, while the fixed supervisor runs from the authorized project's workspace.
- An approved API job submission can asynchronously create/reuse the project's Herdr terminal after checking the opt-in worker-control gate and project-scoped `worker:manage`. Job queue, FIFO, dedup, approval, timeout and durable checkpoint remain owned by Workforce. The API response does not wait for startup.
- Codex profiles in the bridge must use the `codex` binary directly; `--no-daemon` is inserted once. Wrapper executors are rejected.
- No live runtime, SSH config/key, TokenEconomizer hook, Gateway, or Android service changed.

### Verification for this source delta

- API suite: **5 PASS / 0 FAIL**; synthetic Herdr dispatch/completion/status/logs/result through a mocked CLI and a real local synthetic Python queue worker, plus a second-authorized-project rejection before enqueue.
- Herdr controller: **8 PASS / 0 FAIL** (mocked CLI contract).
- Codex bridge: **4 PASS / 0 FAIL**.
- Total: **17 PASS / 0 FAIL**. Mocked Herdr-path submission: **0.711 s**; foreground read during a background synthetic worker: **0.000872 s** in the separate FIFO API simulation.
- Syntax/compile checks, secret-pattern scan, and `git diff --check`: pending until final source set is staged. No test result here represents a live Core/Codex/Android run.

### Runtime evidence and disposition

Owner reports Herdr Core `0.1.22`, Android SSH PASS, terminal `t1`, Codex CLI `0.162.1 --no-daemon`, 6-second response, and Android Spaces discovery. These claims are OWNER-REPORTED. This execution's strict SSH attempt to `sanro@13.140.185.9:22` returned `Permission denied (publickey)`, so installed `hc` docs/version, session visibility, Codex execution, TokenEconomizer compatibility, VPS resources, and cleanup could not be independently verified. The attempt did not alter or interrupt sessions. Adapter remains opt-in. HERDR ANDROID READY and autonomous E2E readiness are not claimed; runtime disposition: **NO-GO** pending authenticated runtime acceptance.

Official CLI surface: [Herdr Core v0.1.22 commands](https://github.com/herdrdev/herdr-core/blob/v0.1.22/docs/commands.md) and [worker session instructions](https://github.com/herdrdev/herdr-core/blob/v0.1.22/crates/herdr-core/src/SKILL.md). Installed VPS documentation is NOT TESTED.


## TokenEconomizer isolated pilot checkpoint — 2026-11-25

Prepared synthetic-only Codex pilot (existing v0.1.0) with separate `CODEX_HOME` and state. Effective runtime configuration: `envfacts` only (max 5 facts/200 tokens), `toolprune=off`, `loopguard=off`, `repomap=off`; config/state permissions `0600`/`0700`. No workers, global Codex, Gateway, 9Router, FreeLLMAPI, or project data changed. Landlock permits TCP 443 egress only for official sign-in; bind and other ports are denied. Filesystem exclusion preflight passed without reading credential values. No authentication, hook execution, model task, or benchmark occurred. **Owner gate:** sign in through ChatGPT in the pilot, then `/hooks` → **Trust all and continue**; restart and notify us before one brief synthetic smoke. Pilot trust only; global activation NO-GO pending separate approval. Token savings and quality comparison remain unmeasured. See TokenEconomizer pilot evidence.

## Herdr activation attempt — 2026-11-25

- Owner supplied the Android Ed25519 public key. OpenSSH validation passed; fingerprint: `SHA256:4VZviw2bb9DF6F1n0axjEQzeKug3yD/7DG0MrdEese0`. No private key was requested or read.
- Strict host-key checking matched the existing ED25519 known-hosts fingerprint `SHA256:Y2QmgEV3aB9cc7lUrMOynkLWVQ5FTl2rTOUYyQXFYSM`. SSH authentication as `sanro` was denied (`Permission denied (publickey)`); this did not verify the account or allow key registration. No VPS files, runtime, services, or active workers were changed.
- VPS architecture/resources, installed `hc`, Herdr session, Codex execution, and Android visibility remain NOT TESTED. Herdr Android is NOT READY; Owner should wait before pressing **Check again**.
- Draft PR #2 readback: open/draft, head `944424fccdaedf543d4d264e62a5e0e8691a4cd4`, base `78fd2ab1f7cf4d77c01f5659e04c3217f489f5d2). Compare reports 38 commits ahead and 0 behind. Initial metadata returned `mergeable=false`, then full PR readback returned `mergeable=true`; treat the first value as transient/inconsistent, with no merge/conflict currently reported. No merge attempted.
- TokenEconomizer evidence remains limited to the previously prepared isolated Codex pilot. Hooks remain untrusted/uninvoked; Herdr-to-Codex/TokenEconomizer session execution was not verified. No token use or savings claim.
- **Disposition:** development candidate remains intact; isolated VPS pilot blocked on an authenticated non-root SSH session. Live/Android readiness: NO-GO.


## TokenEconomizer authentication blocker and product classification — 2026-11-25

- **Product boundary:** TokenEconomizer is **OPTIONAL / EXPERIMENTAL**, not a dependency of Codex CLI, SANRO AI Workforce, or primary development. Evaluation remains isolated and opt-in. No global activation is required or authorized here.
- **Authentication diagnosis:** one official Device Code attempt in isolated pilot session 34885 failed before code issuance at `https://auth.openai.com/api/accounts/deviceauth/usercode` with client error `-32603`. The pilot-context HTTPS probe reported DNS resolution failure (curl exit 6); TLS was not reached. The pilot was stopped after this failure; no repeated attempt.
- **Credential-free comparison:** ordinary network DNS resolved `auth.openai.com`; HTTPS to the official host returned 302 with TLS verification result 0. A sandbox-restricted ordinary probe could not resolve the host. `/etc/resolv.conf` points at the local systemd-resolved stub `127.0.0.53`.
- **Boundary review:** existing launcher uses `env -i`; the Landlock helper handles TCP networking and allows outbound TCP connect on port 443 only. The pilot has no explicit DNS exception. Filesystem restrictions remain; no credential values were read. The observed blocker is DNS/network availability inside the pilot boundary, before OAuth credentials or TLS are evaluated. The exact denied resolver syscall was not instrumented.
- **Disposition:** hooks remain untrusted and uninvoked; no runtime smoke, token benchmark, install/update, global config change, worker interruption, merge, or production deployment. Existing installation and configuration were left intact. Authentication and pilot runtime acceptance are **NO-GO**.
- **One resolution:** provide an independently approved pilot egress path with an explicit DNS resolver and HTTPS allowlist for required official OpenAI auth/runtime endpoints, while preserving Landlock filesystem rules and denying arbitrary direct egress. Do not pass proxy credentials into the agent environment.

See [credential-free authentication evidence](evidence/TOKENECONOMIZER_AUTH_DIAGNOSIS_2026-11-25.md).
