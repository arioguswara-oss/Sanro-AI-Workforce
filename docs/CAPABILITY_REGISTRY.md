# Capability registry — 25 November 2026 Jakarta

| Capability | Implemented source | Isolated verification | Live status |
|---|---|---|---|
| Structured metadata inspection | JD-03 strict schema/host UID | 18 synthetic cases PASS | NOT TESTED |
| Native session/approval shim | Turn-bound actor/session; literal approval true; scope before gate | Denial/pending/route-vs-actor tests PASS; upstream AST signature checked | Installed Hermes version and human approval NOT TESTED |
| FIFO worker | Durable SQLite, finite timeout, content-bound dedup, cancel/recovery | Current host Landlock ABI 8; 10 synthetic worker tests PASS, including the fail-closed boundary | Herdr VPS runtime and host-specific acceptance NOT TESTED |
| Process/network/filesystem boundary | Landlock + seccomp ABI/x32 checks; reduced env; unsafe DB rejection | Real job rejected when confinement unavailable | Same UID/kernel; credential and Codex broker review required |
| Free conversation routing | OpenAI-compatible adapter; circuit/cooldown/fallback/failback; replay guard | 11 routing/provider tests PASS | 9Router/FreeLLMAPI disabled; quota/cost/terms not account-verified |
| Project Registry | Private config binds workspace/repo/branch/environment; Git snapshot checks scope | Real synthetic Git repo tests PASS | No other repository modified |
| Agent Registry | Director/Developer/QA/DevOps + marketing/content/service/support profiles | Fixed logical profiles and persisted observations | Profiles do not prove running remote agents |
| Approval Registry | Subject/project/scope/expiry; Director repo/branch/env/zero-cost actions/forbidden actions | Scoped rejection cases PASS | Private snapshot; native dequeue/revocation remains host gate |
| Task Ledger/Director | Automatic fixed-profile stages; one self-fix; clean QA SHA evidence | Synthetic executor pipeline PASS | Actual Codex delivery NOT TESTED |
| Durable checkpoint/audit/isolation | Exact stage input before enqueue; reviewed recovery generation; project/owner ACL | Restart/dedup/cross-scope cases PASS | No live autonomy claim |
| Reporting | Durable consolidated release/blocker/critical-approval outbox; existing transport injection | Synthetic acknowledgement/dedup PASS | Existing Telegram transport not connected here |
| Monitoring | Dedicated `monitor:read`, GET-only fixed projection, freshness/zero mutations | Handler and real HTTP security tests PASS | Hermes health UNAVAILABLE; Superadmin untouched |
| Reusable UI | Preserve React/Vite; presentation-only Virtual Office table | Both builds and compiled render/escaping PASS | Standalone chat deferred; browser flow NOT TESTED |
| Herdr supervisor adapter | Fixed co-located serial Workforce consumer; project/workspace scoped start-stop; reduced environment; OSC 7501 status | Mocked `hc` CLI tests and synthetic lifecycle test PASS | Core not installed; SSH/VPS resources/Android NOT TESTED; remote machine rejected; Herdr is not a sandbox |
| TokenEconomizer isolated pilot | v0.1.0 in separate Codex home; conservative per-repo config active for hook loader | Effective config PASS; synthetic fixture and Landlock ABI 8 filesystem/TCP-443-only preflight PASS | Five-hook trust and smoke pending Owner; token savings not measured; global activation NO-GO |

Current test-case totals: 70 PASS, 0 FAIL, 12 NOT TESTED. See [acceptance matrix](ACCEPTANCE_MATRIX.md) and [final evidence](evidence/HERMES_FIRST_FINAL_ACCEPTANCE.json). Service activation remains NO-GO.
