# Development task ledger — 2026-11-24

## Herdr integration checkpoint — 2026-11-25
- Recovered the authorized worktree at `6efeba5b0e0985da2feb352ad5c8877c262743bc`, then reconciled eight newer commits through `f909923` without dropping their Hermes-first Director, monitoring, acceptance, or host-handoff work. Draft PR #2 remains the authorized target.
- Fixed two non-blocking worker test defects: API test repo-root resolution depended on process CWD, and supervisor test did not wait for a child to survive startup.
- IMPLEMENTED CANDIDATE: opt-in Herdr CLI controller uses only documented `hc` argv calls and fixed Workforce supervisor command; scoped start/stop/status/output; pinned `0.1.22` from official release manifest; duplicate session reuse; no status-triggered Core autostart; OSC 7501 lifecycle status; one named serial terminal. Existing Workforce queue remains authoritative for durable jobs and approvals.
- SAFETY LIMIT: remote Herdr machine dispatch is rejected because queue database, API, workspace and code have no verified shared-state/synchronization path. Herdr Core itself is not a sandbox. Candidate remains disabled, and start requires explicit project scope plus manual core-environment attestation.
- TESTED after upstream reconciliation: full API suite **21 PASS / 0 FAIL**, Python worker suite **10 PASS / 0 FAIL**; focused subtotal **31 PASS / 0 FAIL** (overlaps earlier acceptance totals and is not additive). Current host reports Landlock ABI 8; synthetic worker tests execute under the existing sandbox. Node syntax, Python compilation, JSON parse and `git diff --check` pass. Latest synthetic API timing: submit **0.220 s**, foreground read **0.000535 s**. Mocked Herdr CLI and synthetic OSC tests are not live Herdr/VPS evidence.
- BLOCKED: Owner's Herdr public key was not included; SSH probe to `sanro@13.140.185.9` failed public-key authentication. No authorized_keys, VPS runtime, service, or Android state was changed/verified. Target CPU/RAM/storage and Herdr Core version remain unknown. Do not tell Owner to press Android “Check again” until registration and isolated Core startup are verified; Owner acceptance is still required afterward.
- Live Hermes, Telegram, approval gates, cron, production, SANRO Studio, and other projects remain untouched.

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

## Master execution mandate — 25 November 2026
Job group: `WF-HF-20261125`. Scope: authorized feature branch and Draft PR #2 only.

| ID | Dependency | Output | State |
|---|---|---|---|
| WF-HF-01 | checkpoint reconciliation | Hermes-first BUILD_PLAN, ADR, workboard, reuse mapping | IMPLEMENTED |
| WF-HF-02 | WF-HF-01 | JD-03/JD-04 session/approval integration and isolation regression | IN PROGRESS |
| WF-HF-03 | WF-HF-02 | Disabled provider catalog, safe routing/recovery | PLANNED |
| WF-HF-04 | WF-HF-03 | Durable automatic Director pipeline and existing-transport outbox | PLANNED |
| WF-HF-05 | WF-HF-04 | Sanitized monitor contract, reusable view and isolated E2E | PLANNED |

No remote worker delegation, live activation, cron changes or other-repository writes are authorized or claimed.

## WF-HF-20261125 — execution checkpoint

| ID | Result | Evidence / remaining boundary |
|---|---|---|
| WF-HF-01 | IMPLEMENTED | Hermes-first BUILD_PLAN, ADR, README; no new chat/bots |
| WF-HF-02 | IMPLEMENTED CANDIDATE / TARGET HOST BLOCKED | Native bound actor/strict approval; worker DB/dedup/ABI hardening; current development-host ABI 8 worker tests pass; target-host acceptance NOT TESTED |
| WF-HF-03 | IMPLEMENTED / MOCK VERIFIED | Disabled catalog, free-only routing safety; no provider calls/cost |
| WF-HF-04 | IMPLEMENTED / SYNTHETIC VERIFIED | Automatic Director, exact input checkpoints, one self-fix, recovery generations and consolidated outbox |
| WF-HF-05 | IMPLEMENTED / ISOLATED VERIFIED | Real HTTP monitoring, zero mutations, private scope, freshness, builds/render; Superadmin untouched |

Tested remote source `44ed2cedb2f5d40829b3f215e1dd09026a91ed6d`; 70 PASS / 0 FAIL / 12 NOT TESTED. GitHub source tree matched local before testing. Source/GitHub and isolated verification do not imply live operation. Final evidence and one host handoff are committed with this checkpoint. No remote worker was delegated or activated.


## Herdr runtime activation continuation — 2026-11-25
- IMPLEMENTED earlier: opt-in co-located Herdr controller candidate, version pin 0.1.22, project/workspace ACL, fixed serial consumer, cancellation/status/output, duplicate-session reuse, no automatic replay; test totals remain the previously recorded 21 Node + 10 Python PASS, not rerun because source is unchanged.
- VERIFIED now: supplied Android public key is syntactically valid; fingerprint `SHA256:4VZviw2bb9DF6F1n0axjEQzeKug3yD/7DG0MrdEese0`. Strict SSH host-key check matched known-hosts fingerprint `SHA256:Y2QmgEV3aB9cc7lUrMOynkLWVQ5FTl2rTOUYyQXFYSM`.
- BLOCKED: SSH account authentication for `sanro@13.140.185.9:22` returned `Permission denied (publickey)`; the supplied key was not registered. No authorized_keys, permissions, VPS packages, services, or worker processes changed. No private key was accessed.
- NOT TESTED: VPS resources, Core installation/checksum, Herdr terminal/session, Workforce-connected Codex worker, Android session visibility, live TokenEconomizer hooks. Herdr adapter only covers the co-located queue; remote dispatch is intentionally rejected.
- PR #2 is open/draft, current readback says mergeable; earlier false result was inconsistent/transient. No merge or force push.
- Owner-facing readiness: **HERDR ANDROID NOT READY**. Wait for confirmation that key registration, pinned Core, and isolated session are verified before pressing **Check again**.

## Herdr Workforce adapter continuation — 2026-11-25

Job group: `WF-HF-20261125`; based on remote feature checkpoint `bcaf43feb31af4c17d39c39d49ebba9d9178cbe4`.
Implementation commit: `d7b945ee1d2f882f82d41abd6bdea8832e7f373a`. It remains an ancestor of the latest branch head `e30036f01c3637a7bc1d0b83d554bc706ef0dbb9`; four concurrent TokenEconomizer documentation commits were preserved.

| Work | State | Evidence |
|---|---|---|
| Project-specific terminal identity and discovery | IMPLEMENTED | Stable hashed project tag/name; exact project/workforce label filtering; scoped workspace and cleanup |
| Automatic terminal start after approved job submit | IMPLEMENTED CANDIDATE | API queues the job then starts the fixed supervisor asynchronously; gated by Herdr opt-in, `worker:manage`, command profile, project ACL and approval |
| Codex foreground mode | IMPLEMENTED | Bridge ensures direct Codex CLI with one `--no-daemon`; rejects wrapper executables; four focused Python cases |
| End-to-end worker dispatch/status/logs/result | VERIFIED SYNTHETIC | Mock `hc` created a local synthetic supervisor; API job reached COMPLETED, logs/result retrieved, status read; fixture stopped child during cleanup |
| Herdr Core/VPS/Android/Codex model execution | NOT TESTED HERE | SSH denied public-key authentication; no live process or `t1` session touched. Owner-supplied runtime pilot remains OWNER-REPORTED, not independently verified. |
| TokenEconomizer hooks | BLOCKED / UNTRUSTED | No hook activation or invocation; compatibility with a Herdr Codex child remains unverified. |

Focused results for changed code: API **5 PASS / 0 FAIL**, Herdr controller **8 PASS / 0 FAIL**, Codex bridge **4 PASS / 0 FAIL** (total **17 PASS / 0 FAIL**, disjoint focused suites). Mocked Herdr-path submission **0.711 s**; separate FIFO simulation foreground read **0.000872 s**. Runtime acceptance remains NO-GO pending authenticated isolated host verification and Android Owner confirmation. No live Hermes/Codex process or service was changed.

## Herdr runtime discovery continuation — 2026-11-25

| Work | State | Evidence |
|---|---|---|
| Authorized source and PR checkpoint | VERIFIED | Isolated clone at `4e6634a4b6bbceb2cfc9d93f8b5bb388c4764c92`; PR #2 OPEN/DRAFT, CLEAN; no local concurrent changes |
| Current Herdr Core and pilot terminal | VERIFIED VIA HC | Core `0.1.22`, `vmi3646685`; `t2` `sanro-monitor-test` currently LIVE in Herdr registry, parentless; process-table corroboration unavailable |
| Existing VPS worker inventory | NOT TESTED | `hc machine ls` empty; execution namespace did not expose target process table; do not infer worker absence |
| Per-job/worker terminal registration | NOT IMPLEMENTED | Existing code manages one project queue-consumer terminal; worker/job metadata is not individually registered in Herdr |
| Existing Codex/Hermes adoption and Android lifecycle reporting | NOT TESTED | No authenticated inventory or Inbox reporting evidence; Spaces visibility alone is insufficient |
| Candidate focused tests | PASS | API Herdr acceptance 2/2; controller 8/8; Codex bridge 4/4; diff check PASS |

Runtime/shared activation remains NO-GO. Do not dispatch per-job terminals until each terminal remains attached to the authorized serial queue, approval, deduplication and recovery path. No worker, service or terminal was changed.
