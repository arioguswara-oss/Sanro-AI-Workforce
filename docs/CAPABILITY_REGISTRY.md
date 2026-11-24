# Capability registry — 2026-11-24

| Capability | Status | Verification | Boundary / gap |
|---|---|---|---|
| JD-03 approval classifier candidate | IMPLEMENTED / VERIFIED | 11 synthetic tests pass | Characterization regex only; known false positives; native approval unchanged; no production use. |
| JD-03 structured metadata inspection | IMPLEMENTED / VERIFIED | 18 synthetic tests pass, including plugin registration contract | Inactive; real host identity, metadata source, and approval integration NOT TESTED. |
| JD-04 serial FIFO worker | IMPLEMENTED / VERIFIED | 27 imported-tree synthetic tests pass | Local worker; no live service, Gateway, or Telegram concurrency verification. |
| JD-04 native project-plugin shim | IMPLEMENTED / VERIFIED (isolated pilot) | Installed Hermes PluginManager loaded/registers tool; synthetic jobs completed FIFO with checkpoint recovery | Live approval flow NOT TESTED; no plugin activation. |
| Job ACL, idempotency, cancellation, status, logs/results | IMPLEMENTED / VERIFIED (synthetic) | Adapter tests cover project/session authorization, duplicate prevention, cancellation, and results | Real ACL/user mapping NOT TESTED. |
| Filesystem confinement | IMPLEMENTED / VERIFIED (synthetic) | Landlock denies selected out-of-workspace reads and permits project writes | Not process, network, or complete credential isolation; live activation BLOCKED. |
| Free-only routing policy | IMPLEMENTED / VERIFIED (policy tests) | Five tests cover cost denial, cooldown, recovery/failback, tool eligibility | No provider installed/called; no live quota, cost, model quality, or engineering tool qualification. |
| Web application and API | NOT IMPLEMENTED | NOT TESTED | No app source in current candidate. |
| New Telegram bots/group and message sync | NOT IMPLEMENTED | NOT TESTED | No bot tokens/group IDs or live integration. |
| Director/orchestrator and autonomous E2E | NOT IMPLEMENTED | NOT TESTED | No authenticated end-to-end runtime. |
