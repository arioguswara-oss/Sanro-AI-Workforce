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
Implementation commit: `d7b945ee1d2f882f82d41abd6bdea8832e7f373a`. The authorized branch later advanced to `e30036f01c3637a7bc1d0b83d554bc706ef0dbb9` through four concurrent TokenEconomizer documentation commits; the Herdr implementation commit is an ancestor and was preserved. This Herdr change itself touched no TokenEconomizer code or hooks.

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
- Syntax checks for changed Node files, Python byte-compilation, tracked-file secret scan (**76 files, 0 findings**), and staged `git diff --check`: PASS. No test result here represents a live Core/Codex/Android run.

### Runtime evidence and disposition

Owner reports Herdr Core `0.1.22`, Android SSH PASS, terminal `t1`, Codex CLI `0.162.1 --no-daemon`, 6-second response, and Android Spaces discovery. These claims are OWNER-REPORTED. This execution's strict SSH attempt to `sanro@13.140.185.9:22` returned `Permission denied (publickey)`, so installed `hc` docs/version, session visibility, Codex execution, TokenEconomizer compatibility, VPS resources, and cleanup could not be independently verified. The attempt did not alter or interrupt sessions. Adapter remains opt-in. HERDR ANDROID READY and autonomous E2E readiness are not claimed; runtime disposition: **NO-GO** pending authenticated runtime acceptance.

Official CLI surface: [Herdr Core v0.1.22 commands](https://github.com/herdrdev/herdr-core/blob/v0.1.22/docs/commands.md) and [worker session instructions](https://github.com/herdrdev/herdr-core/blob/v0.1.22/crates/herdr-core/src/SKILL.md). Installed VPS documentation is NOT TESTED.

## Herdr runtime discovery continuation — 2026-11-25

- Synced authorized branch and Draft PR #2 head: `4e6634a4b6bbceb2cfc9d93f8b5bb388c4764c92`; PR is OPEN, DRAFT, base `main`, merge state CLEAN. Isolated checkout: `/tmp/sanro-herdr-integration`; no concurrent local edits were present.
- Current local `hc server status` reports Herdr Core `0.1.22`, core `vmi3646685`, `live: 1`, and `keeps_running_after_logout: true` for user `sanro`. `hc ls --all` and `hc get sanro-monitor-test` report `t2` (`sleep 600`, project label `workforce`) as LIVE, parentless, and `die_with_parent: false`. This is current Herdr registry evidence only; independent process-table confirmation was unavailable in the execution namespace, so no separate persistence claim is made. No session was stopped or changed.
- `hc machine ls` reports no configured remote machines. Visible process inspection did not expose VPS worker processes; therefore Codex/Hermes/Claude/Gemini/OpenCode inventory and independent PID/PPID/cwd/execution-state classification remain NOT TESTED. Do not infer unmanaged workers absent from this environment.
- Code review confirms the adapter creates one project-scoped Herdr terminal for a fixed serial Workforce queue consumer, not a distinct terminal per job/AI worker. It does not yet register per-worker job ID, role, model, lifecycle/checkpoint/resume metadata, nor adopt existing Codex/Hermes sessions. Changing this to per-job dispatch now would bypass the queue's current approval/dedup/recovery boundary and risks duplicate execution; no such runtime change was made.
- The candidate is opt-in and disabled by default, co-located only, and gated by project ACL, `worker:manage`, approval and explicit core-environment attestation. Existing Herdr controller tests remain mock CLI tests; no isolated second Core/runtime is configured. Android Spaces visibility is not agent lifecycle reporting.
- Targeted verification at this SHA: API Herdr acceptance **2 PASS / 0 FAIL**, controller **8 PASS / 0 FAIL**, Codex bridge **4 PASS / 0 FAIL**, `git diff --check` PASS. The attempted name-pattern Node invocation selected zero individual cases and is not counted as test coverage. No source changes; capability registry and checkpoint/ledger were updated. Existing implementation remains a candidate, not complete runtime integration.
- Disposition: **GO** for continued isolated implementation and synthetic tests; **NO-GO** for shared runtime activation/autonomous end-to-end claim. The next implementation must bind each job's visible metadata to the existing serial queue without bypassing approval, idempotency, timeout or recovery controls. Production activation is not requested by this checkpoint.


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

## Herdr per-job lifecycle integration continuation — 2026-11-25

- Source implementation on `feature/hermes-workforce-foundation`: Herdr project terminal now carries `sanro.project_id`, stable `sanro.worker_name`, `sanro.execution_engine=hermes`, and `sanro.queue=serial`. The existing FIFO consumer emits OSC 7501 status records keyed by its durable 32-hex Job ID for working, done/error, and recovery-interrupted jobs. Subprocess output remains captured to the existing private job log; only the trusted supervisor emits Herdr records. Workforce remains the execution/approval/idempotency/recovery authority.
- The project worker GET snapshot now returns validated Herdr job records; it accepts the Core record map at the top level and nested status shape. Codex invocation and `--no-daemon` path are unchanged. Adapter remains disabled unless existing project, approval, `worker:manage`, and Core-attestation gates are configured.
- Real isolated Core acceptance: Core `0.1.22`, separate `HC_SESSION` and scratch XDG directories under `/tmp`; no shared Core or production session used. Synthetic job `60ae3a07d8b54e43b5ad750315b457d1` reached queue state `succeeded`; Herdr record state `done`. Herdr terminal `wf-acceptance` exposed project ID, worker name, `execution_engine=hermes`, and serial queue labels. Isolated terminal/Core were stopped and scratch data removed. This did not test the Android client.
- Targeted suites after the source changes: API package selection **13 PASS / 0 FAIL**; Python worker + Hermes adapter suites **21 PASS / 0 FAIL**; `git diff --check` PASS. The API suite includes actual local synthetic worker execution with mocked Herdr CLI. The isolated Core smoke is separate evidence; counts are not a new acceptance percentage.
- Existing worker inventory remains blocked by this execution's read-only process namespace and unavailable remote-machine list. Owner-reported Codex CLI and Hermes sessions outside Herdr are therefore classified **UNMANAGED / identity unknown** until read-only project/PID/session mapping is available. No worker was stopped, adopted, or restarted.
- New Herdr records were not independently opened in Android. Owner's prior `sanro-monitor-test` Spaces evidence remains OWNER-REPORTED and is not treated as proof of this job-record UI. Android visibility and Inbox lifecycle reporting: **NOT TESTED**.
- Status: **GO** for the isolated implementation candidate and Core smoke; **NO-GO** for shared runtime activation or the all-workers Android acceptance target. Shared activation requires the requested project-specific `worker:manage` approval after a safe target inventory; current write/read boundary did not authorize production activation.

## Owner-authorized VPS runtime pilot — 2026-11-25

- Base: branch `feature/hermes-workforce-foundation` at `adb69594673b9e070b323ec5cba75a1d5e74353c`; this entry supersedes the earlier runtime activation blocker for one pilot only.
- Executor: local VPS host `vmi3646685`, non-root `sanro`. Herdr Core `0.1.22`, core ID `a34519e633eb235f04a8f43db9ae7a30`, server PID `2844869`, current holder PID `2846008`. These are the two Core/holder processes, one Core instance; `hc machine ls` is empty. Owner's Android connection was not independently inspected.
- Read-only process inventory found two Hermes processes (PIDs `2007093`, `2054385`) and five Codex CLI processes (PIDs `707169`, `2338991`, `2537510`, `2928091`, `2928904`). Their process state was sleeping; project/session/work status is unknown. All remain **UNMANAGED** and untouched. Claude Code, Gemini CLI and OpenCode were not detected by process identity. No inference that each Codex PID is an independent worker.
- One project-scoped runtime fixture, with ephemeral token/auth file removed after initialization, submitted synthetic job `788abd731ec242509dc359df4d746f0b` for `sanro-ai-workforce`. Workforce/HermesAdapter queue observed queued → running → succeeded, exit `0`. The command was fixed `/usr/bin/sleep 2`; no AI provider or model was invoked.
- Herdr terminal `t3` is named `sanro-workforce-pilot`, PID `2933754`, project workspace isolated under `/home/sanro/.local/state/sanro-ai-workforce-herdr-pilot/workspace`, labels identify project, Hermes engine metadata and serial queue. It remains live/idle after the job. Herdr Core returned the Job ID as OSC 7501 `done`; `reported=true` is present in `hc get` output.
- Adapter correction from live evidence: `hc ls --json` filters by labels but omits labels from listed objects. Discovery now performs `hc get --json` for filtered candidates and verifies project/workforce labels before reporting status. Focused tests after correction: controller **9 PASS**, API Herdr cases **2 PASS**, `git diff --check` PASS. Prior valid Python **21 PASS** and broader Node **13 PASS** remain applicable; Python sources were unchanged.
- This is synthetic queue/worker-supervisor evidence with Hermes engine metadata, not proof of a live Hermes model session or AI response. Existing Codex/Hermes workers were not adopted. Herdr terminal protocol status is verified; Android Spaces and Inbox visual acceptance remain **NOT TESTED**. No claim that all workers are integrated.
- See [sanitized VPS pilot evidence](evidence/HERDR_VPS_RUNTIME_PILOT_20261125.json), [project registry](PROJECT_REGISTRY.md), [approval snapshot](APPROVAL_REGISTRY.md), and [job history](JOB_HISTORY.md).
- Status: **GO** for the one synthetic runtime pilot and terminal protocol. **NO-GO** for final Android acceptance pending Owner's single visual check of Spaces and Inbox; broader AI execution and adoption remain unverified.
