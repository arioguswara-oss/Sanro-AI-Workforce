# Functional acceptance matrix — isolated candidate only

Each of ten functional gates has equal weight. This is not a percentage of live autonomous readiness. Baseline source: `6efeba5b0e0985da2feb352ad5c8877c262743bc`; tested new source: `44ed2cedb2f5d40829b3f215e1dd09026a91ed6d`.

| Gate | Baseline | Current | Evidence |
|---|---|---|---|
| 1. Fixed-schema structured read-only inspection | PASS | PASS | 18 JD-03 synthetic tests |
| 2. Bound sender identity, native pending/deny and strict approval result | Missing stricter controls | PASS (synthetic + source contract) | Native plugin rejection tests; source AST probe |
| 3. Real confined worker FIFO/timeout/cancel/concurrency | BLOCKED in current environment | BLOCKED | Landlock ABI 0; boundary fail-closed PASS; 12 worker-dependent cases NOT TESTED |
| 4. Mock provider quota/fallback/failback/pause | PASS | PASS | Original adapter tests passed before changes |
| 5. Disabled unverified routes, no silent replay, safe endpoint policy | Missing controls | PASS | New routing safety cases |
| 6. Automatic Developer → QA → bounded self-fix → candidate/report | Manual transitions only | PASS (synthetic executor) | Director acceptance with automatic stage progression |
| 7. Exact durable stage input, restart dedup and reviewed execution generation | Manual job recovery only | PASS (synthetic executor) | Restart/input checkpoint and explicit recovery cases |
| 8. Dedicated project-scoped read-only monitoring with zero mutations | Not implemented | PASS | Real HTTP + handler security tests; zero DB writes/executor calls |
| 9. Original frontend and reusable monitor build/render | NOT TESTED | PASS | Both Vite builds, compiled component render/escaping test |
| 10. Actual Hermes/Codex/native approval/Telegram autonomous cycle | NOT TESTED | NOT TESTED | Cloudflare login blocks browser; no authorized VPS interface |

Baseline **2/10 = 20%** → current **8/10 = 80%**, delta **+60 percentage points**, scoped to these candidate gates. Architecture documentation is not counted. Gate 2 does not imply installed runtime verification; Gates 6–7 do not imply actual Codex execution. Live autonomy is NOT VERIFIED and activation is NO-GO.

## Current verification totals

| Suite | PASS | FAIL/ERROR | NOT TESTED |
|---|---:|---:|---:|
| Python (root + JD-03 directories) | 58 | 0 | 11 |
| Node API/Director/HTTP/Git/controller | 11 | 0 | 1 |
| Compiled monitoring component render/security smoke | 1 | 0 | 0 |
| **Total test cases** | **70** | **0** | **12** |

Both Vite builds, secret-pattern scan and `git diff --check` also PASS; these are commands, not added to test-case totals. Secret-pattern checks are not proof that all possible secret formats can be detected. No full browser interaction or live provider/account quota test is claimed.

The first combined acceptance run found two obsolete dedup test expectations plus an unsupported worker case that a test-name filter did not exclude. These were corrected: duplicate content remains idempotent, conflicting content raises an error, and unsupported worker acceptance is explicitly NOT TESTED. Initial evidence is retained as `HERMES_FIRST_INITIAL_ACCEPTANCE.json`; final authoritative result is `HERMES_FIRST_FINAL_ACCEPTANCE.json`. The earlier baseline full root run had 10 failures and 1 error caused by unavailable confinement; no protections were disabled.
