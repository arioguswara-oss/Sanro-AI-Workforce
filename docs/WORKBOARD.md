# Workboard — Hermes-first mandate
Updated 25 November 2026 Jakarta. Baseline `6efeba5`; tested source `44ed2cedb2f5d40829b3f215e1dd09026a91ed6d`; Draft PR #2.

| Package | Source status | Isolated verification | Live verification |
|---|---|---|---|
| WP1 architecture reconciliation | IMPLEMENTED | BUILD_PLAN/ADR/README aligned; React preserved | No activation needed |
| WP2 JD-03/JD-04 stabilization | IMPLEMENTED CANDIDATE | Inspection, actor/approval rejection, dedup/boundary PASS; actual worker tests blocked by Landlock ABI 0 | NOT TESTED; installed host approval/session/executor/isolation required |
| WP3 multi-model routing | IMPLEMENTED CANDIDATE | Free-only/fallback/failback/circuit/checkpoint safety PASS with mocks | Providers DISABLED; account quota/terms/config NOT TESTED |
| WP4 Director and registries | IMPLEMENTED CANDIDATE | Automatic pipeline, bounded self-fix, durable input/recovery/outbox PASS with synthetic executor | Codex/native admission/revocation/Telegram acknowledgement NOT TESTED |
| WP5 read-only monitoring | IMPLEMENTED CANDIDATE | Real local HTTP, authorization, zero mutations, freshness and component builds/render PASS | Superadmin untouched; Hermes health UNAVAILABLE |

Functional candidate acceptance **20% → 80% (+60 percentage points)** over ten explicit gates in [ACCEPTANCE_MATRIX](ACCEPTANCE_MATRIX.md); not live readiness. 70 PASS / 0 FAIL / 12 NOT TESTED, both builds PASS. No autonomous end-to-end live claim.

Next host tasks are consolidated in [HERMES_EXECUTION_HANDOFF](HERMES_EXECUTION_HANDOFF.md). Worker source and API/UI changes are preserved; no new chat development, bots, production, merge, Gateway restart, plugin activation or cron change. Both cron jobs must remain PAUSED; actual remote state unobserved.
