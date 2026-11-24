# SANRO AI Workforce — Initial Workboard
Updated: 2026-11-24
Source plan: [BUILD_PLAN.md](BUILD_PLAN.md)
Scope: planning plus isolated source candidates; no runtime or production mutations.

## Current project status
| Category | Status | Evidence / qualification |
|---|---|---|
| Repo public and README | IMPLEMENTED | Commit `78fd2ab1f7cf4d77c01f5659e04c3217f489f5d2` on `main` |
| Full build plan | IMPLEMENTED (documentation only) | `docs/BUILD_PLAN.md`; original planning preserved from Draft PR #1 |
| Web App/API | NOT IMPLEMENTED | No application source in Workforce repo |
| Four Telegram identities/group | NOT IMPLEMENTED | Proposed, no bot tokens or group IDs collected |
| Director/orchestrator | NOT IMPLEMENTED | Needs policy + ledger + routing |
| JD-03 approval gate candidate | IMPLEMENTED / VERIFIED (synthetic) | 11 characterization tests pass; false positives remain; native gate unchanged |
| JD-03 structured inspection candidate | IMPLEMENTED / VERIFIED (isolated synthetic) | 18 tests pass; inactive; live host identity/config NOT TESTED |
| JD-04 Hermes worker candidate | IMPLEMENTED / VERIFIED (isolated synthetic) | 27 tests pass; native plugin loaded in isolated pilot; live activation BLOCKED |
| Free-only routing policy candidate | IMPLEMENTED / VERIFIED (local policy tests) | 5 routing tests; provider calls and real quota validation NOT TESTED |
| Web App/API, four Telegram identities/group, Director | NOT IMPLEMENTED | No application source or new bot/group runtime |
| Autonomous E2E | NOT TESTED | No authenticated end-to-end pilot; conversation test was a simulation |

## Backlog — first five dependent tasks
| ID | Order | Deliverable | Acceptance | Status |
|---|---:|---|---|---|
| WF-001 | 1 | Hermes/Supervisor read-only reuse inventory | Source interfaces partially mapped; active service state and Supervisor reconciliation remain open | IN PROGRESS (PARTIAL) |
| WF-002 | 2 | Node.js API + React scaffold + store and logical agents | Build/lint smoke; durable threads; project isolation | NOT STARTED |
| WF-003 | 3 | ChatGPT-style web UI for private/group chat | Login, project switch, @mention, persistent history, real status vs demo | NOT STARTED |
| WF-004 | 4 | Four Telegram Bot identities and shared gateway | Distinct bot posts; Topic↔thread sync; anti-echo and owner authentication | NOT STARTED |
| WF-005 | 5 | Director + ledger + Hermes read-only bridge | Candidate job ledger/adapter exists; Director and full bridge remain incomplete | PARTIAL (CANDIDATE) |

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


## Development checkpoint — 2026-11-24
- Integration branch `feature/hermes-workforce-foundation` is based on `main` at `78fd2ab1f7cf4d77c01f5659e04c3217f489f5d2`. Draft PR #1 remains open and unchanged.
- Separate commits preserve implementation boundaries: JD-03 `1d9c2e1`; JD-04 `eb2bdd2`.
- JD-03 tests: **29 PASS / 0 FAIL** in an isolated copy; source-specific protected path strings were generalized before publication.
- JD-04 tests: **27 PASS / 0 FAIL** in the imported candidate tree, including routing, worker, adapter, and native plugin tests.
- Public evidence is sanitized: no runtime credentials, private ACLs, session dumps, temporary paths, service metadata, or raw logs are included.
- Latest implementation remains **candidate-only**. No Hermes activation, Gateway/Telegram mutation, cron change, merge, or deployment.
