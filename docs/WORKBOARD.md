# SANRO AI Workforce — Workboard
Updated: 2026-11-24
Source plan: [BUILD_PLAN.md](BUILD_PLAN.md)
Scope: planning plus isolated source candidates; no runtime or production mutations.

## Current project status
| Category | Status | Evidence / qualification |
|---|---|---|
| Repo public and README | IMPLEMENTED | Commit `78fd2ab1f7cf4d77c01f5659e04c3217f489f5d2` on `main` |
| Full build plan | IMPLEMENTED (documentation only) | `docs/BUILD_PLAN.md`; original planning preserved from Draft PR #1 |
| Web App/API | PARTIAL / IMPLEMENTED CANDIDATE | Node API, private SQLite store, React UI source; React/Vite build NOT TESTED |
| Four Telegram identities/group | NOT IMPLEMENTED | Proposed, no bot tokens or group IDs collected |
| Director/orchestrator | PARTIAL / LOGICAL STATE MACHINE | Role-scoped task transitions; no AI inference or autonomous assignment |
| JD-03 approval gate candidate | IMPLEMENTED / VERIFIED (synthetic) | 11 characterization tests pass; false positives remain; native gate unchanged |
| JD-03 structured inspection candidate | IMPLEMENTED / VERIFIED (isolated synthetic) | 18 tests pass; inactive; live host identity/config NOT TESTED |
| JD-04 worker and process controls | IMPLEMENTED / VERIFIED (isolated synthetic) | 32 focused Python tests; FIFO, checkpoint, seccomp network denial, timeout, cancel and recovery pass; live activation BLOCKED |
| Free-only routing and protocol adapters | IMPLEMENTED / VERIFIED (mock transport only) | 8 tests; 429 fallback, cooldown, failback, pause/resume; no provider installed/called |
| API, project/task/activity/approval registries | IMPLEMENTED / VERIFIED (handler simulation) | 3 Node tests; project ACL, SQLite persistence, approval, workflow, jobs/resume |
| React web interface | IMPLEMENTED (source) / NOT TESTED (build) | Dependency install blocked by registry connection reset |
| Telegram identities/group and live Director | NOT IMPLEMENTED / NOT TESTED | Existing bots untouched; no multi-user group membership or AI Director |
| Autonomous E2E | NOT TESTED | No authenticated end-to-end pilot; conversation test was a simulation |

## Backlog — first five dependent tasks
| ID | Order | Deliverable | Acceptance | Status |
|---|---:|---|---|---|
| WF-001 | 1 | Hermes/Supervisor read-only reuse inventory | Source interfaces partially mapped; active service state and Supervisor reconciliation remain open | IN PROGRESS (PARTIAL) |
| WF-002 | 2 | Node API + React source + store and logical agents | API ACL/persistence tests PASS; React build NOT TESTED due registry access | PARTIAL (API VERIFIED) |
| WF-003 | 3 | Web UI source for project/thread/task/job view | JSX parses; Vite build and browser flow NOT TESTED; agent response and @mention dispatch NOT IMPLEMENTED | PARTIAL (SOURCE ONLY) |
| WF-004 | 4 | Four Telegram Bot identities and shared gateway | Distinct bot posts; Topic↔thread sync; anti-echo and owner authentication | NOT STARTED |
| WF-005 | 5 | Director + ledger + isolated worker bridge | SQLite task/job/audit/checkpoint API and fixed-profile bridge tested; no native Hermes approval bridge | PARTIAL (ISOLATED CANDIDATE) |

## After WF-005
Implement Developer → QA → bounded self-fix → Draft PR in an isolated approved development lane; verify one SANRO Studio end-to-end delivery with exact commit SHA and no manual terminal steps. Only then onboard other SANRO projects.

## Decision register (DECIDED, not automatically authorized for writes)
- **ADR-001** Public source repository; all secrets/mandates/raw private data stay outside Git.
- **ADR-002** Four agents: Director, Developer, QA, DevOps; optional specialist modes, default serial Codex.
- **ADR-003** One private Telegram group with project topics and **four distinct bot identities**; existing Hermes bots preserved.
- **ADR-004** One responsive web app with group and personal AI chat; unified message store/event ledger to avoid split-brain.
- **ADR-005** Autonomous by Default, Approval by Exception **only under active scoped mandate**. Owner approval for CRITICAL actions.
- **ADR-006** Reuse Hermes/Supervisor; no migrations, new infrastructure or paid API by default.
- **ADR-007** Development First; minor smoke gates during coding, comprehensive QA near feature completion.
- **ADR-008** Do not claim autonomous full-cycle before a real pilot is VERIFIED.

## Reporting template
1. Progress before→after, delta and calculation basis.
2. Stage/status table.
3. Features actually completed.
4. Repo/branch/SHA/PR/evidence.
5. PASS/FAIL/NOT TESTED and coverage.
6. Blocker + up to five next actions.
7. GO/NO-GO and any critical approval needed.

**Progress rule:** documentation-only planning does not count as software implementation. Candidate code is tracked separately from activated product capabilities; the full app and autonomous workflow remain unimplemented.

## Checkpoint — 2026-11-24 (JD-05 continuous development)
- API foundation, private SQLite, project ACL, owner-scoped threads, task transitions, approval read registry, activity log, job status/results/logs/cancel/checkpoint and explicit interrupted-job resume are implemented. Recovery does not auto-replay; resume requires reconciled side effects, new idempotency key, and scoped active approvals.
- The web source is React/Vite with project, thread/group label, task, job, approval and activity panels. Build dependency installation did not complete because the package registry connection reset; no browser session was launched.
- Worker children now inherit a reduced environment and receive Landlock plus an unprivileged seccomp filter denying network socket syscalls and process-group escape/inspection controls. Same UID/kernel remains a boundary; this is not a VM or container.
- Latest tests: 32 targeted Python JD-04/routing/provider tests PASS; 3 Node API/supervisor tests PASS. Synthetic API metrics: submit 0.2734 s, foreground read 0.00057 s. No live Hermes, provider, Telegram or external model test.


## Development checkpoint — 2026-11-24
- Integration branch `feature/hermes-workforce-foundation` is based on `main` at `78fd2ab1f7cf4d77c01f5659e04c3217f489f5d2`. Draft PR #1 remains open and unchanged.
- Separate commits preserve implementation boundaries: JD-03 `1d9c2e1`; JD-04 `eb2bdd2`.
- JD-03 tests: **29 PASS / 0 FAIL** in an isolated copy; source-specific protected path strings were generalized before publication.
- JD-04 tests: **27 PASS / 0 FAIL** in the imported candidate tree, including routing, worker, adapter, and native plugin tests.
- Public evidence is sanitized: no runtime credentials, private ACLs, session dumps, temporary paths, service metadata, or raw logs are included.
- Latest implementation remains **candidate-only**. No Hermes activation, Gateway/Telegram mutation, cron change, merge, or deployment.
