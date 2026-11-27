# Workboard — Hermes-first mandate
Updated 25 November 2026 Jakarta. Reconciled upstream through `f909923`; previous acceptance source `44ed2cedb2f5d40829b3f215e1dd09026a91ed6d`; Draft PR #2.

| Package | Source status | Isolated verification | Live verification |
|---|---|---|---|
| WP1 architecture reconciliation | IMPLEMENTED | BUILD_PLAN/ADR/README aligned; React preserved | No activation needed |
| WP2 JD-03/JD-04 stabilization | IMPLEMENTED CANDIDATE | Current host Landlock ABI 8; current synthetic API/worker tests PASS; upstream checkpoint's earlier ABI 0 status was environment-specific | Target VPS approval/session/executor/isolation NOT TESTED |
| WP3 multi-model routing | IMPLEMENTED CANDIDATE | Free-only/fallback/failback/circuit/checkpoint safety PASS with mocks | Providers DISABLED; account quota/terms/config NOT TESTED |
| WP4 Director and registries | IMPLEMENTED CANDIDATE | Automatic pipeline, bounded self-fix, durable input/recovery/outbox PASS with synthetic executor | Codex/native admission/revocation/Telegram acknowledgement NOT TESTED |
| WP5 read-only monitoring | IMPLEMENTED CANDIDATE | Real local HTTP, authorization, zero mutations, freshness and component builds/render PASS | Superadmin untouched; Hermes health UNAVAILABLE |
| Herdr supervisor adapter | IMPLEMENTED CANDIDATE | Mocked CLI authorization, fixed local queue consumer, lifecycle/status/output/cancel and no-auto-replay tests | No Core install, VPS/SSH, Android acceptance; remote machine rejected |

Functional candidate acceptance **20% → 90% (+70 percentage points)** over ten explicit gates in [ACCEPTANCE_MATRIX](ACCEPTANCE_MATRIX.md); not live readiness. The earlier 70 PASS / 0 FAIL / 12 NOT TESTED total is tied to its recorded source SHA; latest focused tests are 31 PASS / 0 FAIL, overlapping that evidence. No autonomous end-to-end live claim.

Next host tasks are consolidated in [HERMES_EXECUTION_HANDOFF](HERMES_EXECUTION_HANDOFF.md). Worker source and API/UI changes are preserved; no new chat development, bots, production, merge, Gateway restart, plugin activation or cron change. Both cron jobs must remain PAUSED; actual remote state unobserved.

## Herdr integration checkpoint — 2026-11-25

- Added a disabled adapter candidate and OSC 7501 worker lifecycle signal; the Workforce queue remains authoritative. Herdr Core `0.1.22` is pinned from the official release manifest, but no target artifact was downloaded or installed.
- The adapter is co-located only; `WORKFORCE_HERDR_MACHINE` is rejected until a verified shared queue/code path exists. It does not treat Herdr as a sandbox. Current development host reports Landlock ABI 8; this does not attest the target VPS or establish a VM/kernel boundary.
- Current post-reconciliation tests: **31 PASS / 0 FAIL** (21 Node API package tests, 10 Python worker tests), overlapping the historical 70-pass acceptance evidence above. Mocked adapter tests and synthetic worker status do not imply VPS or Android acceptance. Latest synthetic timing: submit **0.220 s**, foreground **0.000535 s**.
- The Owner key was absent from the request and the current batch SSH key was rejected. No VPS files or services were modified. Android “Check again” should wait until key registration, target identity and isolation/resource checks, and isolated Core session startup have been verified.
