# Functional acceptance matrix — isolated candidate only

Each of ten functional gates has equal weight. This is not a percentage of live autonomous readiness. Baseline source: `6efeba5b0e0985da2feb352ad5c8877c262743bc`; original accepted source: `44ed2cedb2f5d40829b3f215e1dd09026a91ed6d`; focused follow-up ran after upstream source through `f909923` plus the local Herdr candidate.

| Gate | Baseline | Current | Evidence |
|---|---|---|---|
| 1. Fixed-schema structured read-only inspection | PASS | PASS | 18 JD-03 synthetic tests |
| 2. Bound sender identity, native pending/deny and strict approval result | Missing stricter controls | PASS (synthetic + source contract) | Native plugin rejection tests; source AST probe |
| 3. Real confined worker FIFO/timeout/cancel/concurrency | BLOCKED in upstream acceptance run | PASS (current development host, synthetic isolated jobs) | The `f909923` run reported Landlock ABI 0; current host reports ABI 8 and the 10-test Python worker suite passes. Target VPS remains NOT TESTED. |
| 4. Mock provider quota/fallback/failback/pause | PASS | PASS | Original adapter tests passed before changes |
| 5. Disabled unverified routes, no silent replay, safe endpoint policy | Missing controls | PASS | New routing safety cases |
| 6. Automatic Developer → QA → bounded self-fix → candidate/report | Manual transitions only | PASS (synthetic executor) | Director acceptance with automatic stage progression |
| 7. Exact durable stage input, restart dedup and reviewed execution generation | Manual job recovery only | PASS (synthetic executor) | Restart/input checkpoint and explicit recovery cases |
| 8. Dedicated project-scoped read-only monitoring with zero mutations | Not implemented | PASS | Real HTTP + handler security tests; zero DB writes/executor calls |
| 9. Original frontend and reusable monitor build/render | NOT TESTED | PASS | Both Vite builds, compiled component render/escaping test |
| 10. Actual Hermes/Codex/native approval/Telegram autonomous cycle | NOT TESTED | NOT TESTED | Cloudflare login blocks browser; no authorized VPS interface |

Baseline **2/10 = 20%** → latest local candidate **9/10 = 90%**, delta **+70 percentage points**, scoped to these candidate gates. This follow-up supersedes the 80% snapshot in the `f909923` checkpoint. Architecture documentation is not counted. Gate 2 does not imply installed runtime verification; Gates 6–7 do not imply actual Codex execution. Gate 3 is verified only in the current isolated development host, not on the VPS. Gate 10 remains NOT TESTED; live autonomy is NOT VERIFIED and activation is NO-GO.

## Recorded acceptance totals (original accepted source)

| Suite | PASS | FAIL/ERROR | NOT TESTED |
|---|---:|---:|---:|
| Python (root + JD-03 directories) | 58 | 0 | 11 |
| Node API/Director/HTTP/Git/controller | 11 | 0 | 1 |
| Compiled monitoring component render/security smoke | 1 | 0 | 0 |
| **Total test cases** | **70** | **0** | **12** |

Both Vite builds, secret-pattern scan and `git diff --check` also PASS; these are commands, not added to test-case totals. Secret-pattern checks are not proof that all possible secret formats can be detected. No full browser interaction or live provider/account quota test is claimed.

The first combined acceptance run found two obsolete dedup test expectations plus an unsupported worker case that a test-name filter did not exclude. These were corrected: duplicate content remains idempotent, conflicting content raises an error, and unsupported worker acceptance is explicitly NOT TESTED. Initial evidence is retained as `HERMES_FIRST_INITIAL_ACCEPTANCE.json`; final authoritative result is `HERMES_FIRST_FINAL_ACCEPTANCE.json`. The earlier baseline full root run had 10 failures and 1 error caused by unavailable confinement; no protections were disabled.

## Herdr adapter code-delta tests — 2026-11-25

Changed adapter tests only: API **5/5 PASS**, Herdr controller **8/8 PASS**, bridge `--no-daemon` **4/4 PASS**. Total **17 PASS / 0 FAIL**. The API test's mock `hc` runner launches the actual synthetic Python queue consumer locally, confirms approved job completion, logs/result retrieval, worker status and test cleanup, and rejects another authorized project before enqueue. This is isolated simulation; the Herdr CLI is mocked. It does not establish VPS/Core/Android/Codex-model acceptance. Mocked Herdr submission **0.711 s**; foreground request during a synthetic background worker **0.000872 s**.

Progress delta is implementation scope: added project-specific worker identity/isolation, async post-approval startup, and Codex `--no-daemon` enforcement. The ten-gate functional coverage percentage above is not recomputed because these changes refine existing Herdr/worker gates and do not add a separately accepted live runtime gate. Live acceptance remains NOT TESTED.

## Focused follow-up after upstream reconciliation

The full `apps/api` suite passed **21/21**, including synthetic Git-snapshot, Director, monitoring, Herdr adapter wiring and worker-controller cases. The Python worker suite passed **10/10** with Landlock ABI 8. These focused totals overlap the historical 70-test evidence and are not additive. Latest simulated API submission latency was **0.220 s** and foreground read latency **0.000535 s**. Herdr CLI tests use a mock runner; Herdr Core, SSH target, VPS resources and Android app were not exercised.

## GDI-02R runtime remediation — 2026-11-26

| Acceptance area | Result | Evidence |
|---|---|---|
| Project source editing, lint/build | PASS | Runtime preflight and capability routing changes; 64 Python tests; Vite 8.4.0 build PASS |
| Director/admission/worker/QA/checkpoint orchestration | VERIFIED SYNTHETIC | Full API suite 33 PASS, including GDI-03 and GDI-04 acceptance |
| Capability-aware support-model fallback | VERIFIED SYNTHETIC | 9Router/FreeLLMAPI fixtures: workload filtering, quota cooldown, malformed tool-call rejection, temporary network fallback and pause/resume |
| MariaDB isolated server/SQL | BLOCKED | Temporary datadir initialized; isolated server Unix socket bind failed with `Operation not permitted`; no schema/data query ran |
| Playwright/Chromium DOM/screenshot | BLOCKED | Playwright 1.65.1 and Chromium headless shell 159.0.8154.6 installed project-scoped; runtime sandbox terminated launch with `Operation not permitted`; no screenshot |
| Git metadata and delivery | PASS | Normal process cannot write `.git`; scoped native reviewer approved commits/push. Tested source `5c986863f6dc2e6d4f25b1701d050c90c9e1cc5e`; checkpoint commit `1471ba3dcd6a249fe6dedfb4f2baa2d99759491d`; pushed fast-forward to same branch |
| SSH staging | BLOCKED | SSH agent socket unavailable in inherited context and no project staging target allowlist; no connection attempted |
| Production/live Hermes | NOT TESTED | No live service, database, provider, Studio workspace, staging target or production resource was accessed |

Counts are not added to the historical ten-gate matrix; this runtime-focused follow-up is a separate evidence set. See `evidence/GDI02R_RUNTIME_ACCEPTANCE_20261126.json`.

### Fixed-operation wrapper continuation — 2026-11-26

| Area | Result | Evidence |
|---|---|---|
| Wrapper policy, project/mandate/checkpoint admission | VERIFIED SYNTHETIC | Python wrapper/adaptor/preflight/launcher tests: 17 PASS / 0 FAIL; expiry, mismatch, scope, timeout, evidence shape, replay and fixed argv rejection |
| Workforce API admission and native approval handoff | VERIFIED SYNTHETIC | Full Node API suite: 36 PASS / 0 FAIL; operation-specific approval and rejection of boolean-only native approval |
| Browser DOM/JavaScript/screenshot | NOT TESTED | No browser launch this continuation; wrapper keeps existing seccomp and browser sandbox |
| Isolated MariaDB SQL | NOT TESTED | No database launch this continuation; wrapper keeps existing seccomp/network denial |
| Host registration / live Hermes | NOT TESTED | Registration artifact ready; host callback not injected or activated |
| SSH | DISABLED | No profile, target, or authentication mechanism |

Tested implementation SHA: `2d7c5b79530d6eaa22b606f7862dd5e2237c89e7`. Existing worker seccomp denies socket syscalls; wrapper retains that policy, so runtime results remain NOT TESTED here and require an approved compatible runtime executor.

These fixture tests verify admission and integration plumbing only. They do not claim runtime PASS. See `evidence/GDI02R_RUNTIME_ACCEPTANCE_20261126.json` and `integrations/GDI02R_RUNTIME_EXECUTOR.md`.

### Executor continuation

At checkpoint `28d692c42739e71558a3cb18b326b6d3e29fa7d3`, available connected tools exposed no callable official Hermes native executor or Local CI runtime interface. The orchestration contract confirms the reviewed wrapper is not installed into Hermes. Runtime acceptance was therefore **BLOCKED before invocation**; no mock was substituted, no browser/database/SSH attempt repeated, and no runtime PASS added. See the continuation record in `evidence/GDI02R_RUNTIME_ACCEPTANCE_20261126.json`.

### Microsoft Playwright MCP integration — 2026-11-26

| Area | Result | Evidence |
|---|---|---|
| Official package installation | PASS | `@playwright/mcp@0.0.86` pinned in `apps/web`; npm integrity recorded in lockfile; audit 0 vulnerabilities; Node 22.22.1 satisfies package Node >=20 requirement |
| Project-scoped Codex registration | PASS (config discovery) | `.codex/config.toml`; `codex mcp list/get` reports enabled; tool allowlist contains seven browser-only operations; existing Hostinger entry remains enabled |
| MCP initialization and tool discovery | BLOCKED | Stdio MCP initialize closed before `tools/list`; subprocess exited 0 without a response or stderr. Registration is not treated as tool discovery |
| Chromium synthetic browser acceptance | BLOCKED before browser launch | No MCP tool call reached the browser; no DOM/click/fill/JavaScript result or screenshot. Chromium sandbox was not disabled and no socket/security boundary was changed |
| Hermes MCP registration | NOT TESTED | Conditional on Codex browser acceptance succeeding; no Hermes config or service touched |
| Build and dependency check | PASS | `npm ls @playwright/mcp playwright --depth=0`; `npm run build` (Vite 8.4.0) |

The MCP package's transitive Playwright `1.66.0-alpha-2026-11-18` expects Chromium revision 1255, matching the existing cached Chromium Headless Shell `159.0.8154.6`. Package README tool names are not counted as runtime tool discovery. See the detailed probe and approval observations in `evidence/GDI02R_RUNTIME_ACCEPTANCE_20261126.json`.
