# SANRO AI Workforce — Initial Workboard
Updated: 2026-11-22
Source plan: [BUILD_PLAN.md](BUILD_PLAN.md)
Scope: source planning only; no VPS or production mutations.

## Current project status
| Category | Status | Evidence / qualification |
|---|---|---|
| Repo public and README | IMPLEMENTED | Commit `78fd2ab1f7cf4d77c01f5659e04c3217f489f5d2` on `main` |
| Full build plan | IMPLEMENTED (documentation only) | `docs/BUILD_PLAN.md` on planning branch |
| Web App/API | NOT IMPLEMENTED | No application source in Workforce repo |
| Four Telegram identities/group | NOT IMPLEMENTED | Proposed, no bot tokens or group IDs collected |
| Director/orchestrator | NOT IMPLEMENTED | Needs policy + ledger + routing |
| Hermes adapter | NOT IMPLEMENTED | Reuse candidate from Supervisor; runtime readback required |
| Autonomous E2E | NOT TESTED | No authenticated end-to-end pilot |

## Backlog — first five dependent tasks
| ID | Order | Deliverable | Acceptance | Status |
|---|---:|---|---|---|
| WF-001 | 1 | Hermes/Supervisor read-only reuse inventory | Current SHA, services, access and candidate status mapped; no restarts | PLANNED |
| WF-002 | 2 | Node.js API + React scaffold + store and logical agents | Build/lint smoke; write/read durable threads; project isolation | PLANNED |
| WF-003 | 3 | ChatGPT-style web UI for private/group chat | Login, project switch, @mention, persistent history, real status vs demo | PLANNED |
| WF-004 | 4 | Four Telegram Bot identities and shared gateway | Distinct bot posts; Topic↔thread sync; anti-echo and owner authentication | PLANNED |
| WF-005 | 5 | Director + ledger + Hermes read-only bridge | Job transitions logged, denied actions cannot execute | PLANNED |

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

**Progress rule:** documentation-only planning means software implementation delta = 0%.
