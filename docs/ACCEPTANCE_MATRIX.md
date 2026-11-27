# Functional acceptance matrix — isolated candidate only

## Chromium 159 native sandbox acceptance — 2026-11-28

| Check | Result | Evidence |
|---|---|---|
| Prior native browser launch with Playwright `chromiumSandbox=true` | PASS (Owner-reported runtime) | Chromium `159.0.8154.6`; synthetic DOM/JavaScript and screenshots in `docs/evidence/SANRO_CHROMIUM_NATIVE_QA_20261128.tBNs4p/` |
| `Layer 1 Sandbox=Namespace` | PASS (re-evaluated preserved actual diagnostics) | `sandbox-diagnostics.json`, SHA-256 `70e7afdca7786a95f41519a2c9b9701be6cc69b440e89ead9f189a8c8203c10d` |
| PID namespaces, Network namespaces, Seccomp-BPF, TSYNC | PASS (each explicitly `Yes`) | Chromium 159 diagnostics parsed by current fail-closed parser |
| Yama Non-broker | WARNING (`No`) | Recorded, not treated as mandatory sandbox control; no profile change |
| Parser regression suite | PASS, 5 cases | Actual format, tab-separated text, negative required controls, malformed/missing/conflicting/legacy-only data, Yama warning |
| Native runtime rerun after parser fix | NOT TESTED | No host activation or browser relaunch from Codex |

The prior native acceptance returned FAIL because the parser expected a `Namespace Sandbox` row. The current parser recognizes Chromium 159's `Layer 1 Sandbox: Namespace` and fails closed unless the four additional required controls are explicitly `Yes`. See [final sandbox evidence](evidence/SANRO_CHROMIUM_FINAL_SANDBOX_ACCEPTANCE_20261128.json) and [preserved native run](evidence/SANRO_CHROMIUM_NATIVE_QA_20261128.tBNs4p/sandbox-diagnostics.json).

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

## Development policy and isolated executor candidate — 2026-11-26

| Gate | Result | Evidence |
|---|---|---|
| Synthetic Backup/DR vs Dev/QA gate characterization | PASS | Candidate hook tests; live installed hook invoked read-only with synthetic payloads. `.backup.enabled` metadata triggered approval; a test filename containing `backup` alone did not. Archive, database dump and protected `.hermes` path also triggered approval. |
| Project/job/worker/scope/mandate authorization | PASS (synthetic) | Existing fixed executor policy tests; exact registry identity, job scope, mandate expiry/zero-cost, approval reference and native-approval evidence required. |
| Fixed isolated execution and protected path denial | PASS (synthetic) | Arbitrary shell/backup/restore denied; `.hermes`, `.ssh`, `.aws`, `.gnupg`, `credentials`, `secrets`, and `.local/share` workspace roots rejected before launch. Existing Landlock/seccomp is retained. |
| Focused policy/runtime regression | PASS | 24 policy/executor/gate tests plus 26 worker/Hermes adapter regressions; 50 PASS / 0 failures. |
| Live Hermes profile registration and Local CI invocation | NOT TESTED | No verified native registration interface or host executor available; live hook remains unchanged. |
| Chromium/browser and live runtime acceptance | NOT TESTED | No browser launch attempted. No sandbox workaround. |

This is a source candidate, not a live activation claim. Registration is NO-GO pending explicit Owner approval of a verified native Hermes interface. Detailed review/rollback procedure is in `integrations/HERMES_DEVELOPMENT_POLICY_CANDIDATE_V1.md`.

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

### SANRO runtime integration completion continuation — 2026-11-26

| Gate | Result | Evidence |
|---|---|---|
| Workforce native adapter seam | IMPLEMENTED / synthetic tests | `createApp({ nativeApprovalProvider })` registers a fixed adapter; actor/project/job/operation are bound and denied/mismatched approvals do not reach execution |
| Native Hermes per-job approval source | BLOCKED | Hermes v0.22 source evidence documents approval transport for already-created approvals, not a per-job policy/callback provider. No host provider is available |
| Hermes secret manifest | IMPLEMENTED / source test | Plugin declares token and approval reference via `requires_env` with secret prompting; no profile values provisioned |
| Pilot project binding | PARTIAL / fail-closed | Plugin targets only `sanro-browser-qa` and pilot-specific profiles; host auth registry workspace/repository/branch/worker/mandate and matching fixed entrypoint were not available to verify |
| Integrated host activation | BLOCKED before mutation | `bash scripts/sanro-qa-runtime-activation.sh` performs read-only checks then exits 3 with the missing native provider blocker |
| Actual Local CI / Chromium / screenshot | NOT TESTED | No authorized host executor, native approval provider, pilot checkout binding, or browser job was available. No runtime PASS claimed |

Tested implementation SHA: `2d7c5b79530d6eaa22b606f7862dd5e2237c89e7`. Existing worker seccomp denies socket syscalls; wrapper retains that policy, so runtime results remain NOT TESTED here and require an approved compatible runtime executor.

These fixture tests verify admission and integration plumbing only. They do not claim runtime PASS. See `evidence/GDI02R_RUNTIME_ACCEPTANCE_20261126.json` and `integrations/GDI02R_RUNTIME_EXECUTOR.md`.

### Executor continuation

At checkpoint `28d692c42739e71558a3cb18b326b6d3e29fa7d3`, available connected tools exposed no callable official Hermes native executor or Local CI runtime interface. The orchestration contract confirms the reviewed wrapper is not installed into Hermes. Runtime acceptance was therefore **BLOCKED before invocation**; no mock was substituted, no browser/database/SSH attempt repeated, and no runtime PASS added. See the continuation record in `evidence/GDI02R_RUNTIME_ACCEPTANCE_20261126.json`.

### Microsoft Playwright MCP integration — 2026-11-26

| Area | Result | Evidence |
|---|---|---|
| Official package installation | PASS | `@playwright/mcp@0.0.86` pinned in `apps/web`; npm integrity recorded in lockfile; audit 0 vulnerabilities; Node 22.22.1 satisfies package Node >=20 requirement |
| Project-scoped Codex registration | PASS (config discovery; path corrected) | `.codex/config.toml`; inherited cwd is project root, so config argument now names `apps/web/playwright-mcp.config.json`; seven browser-only tools remain allowlisted; Hostinger unchanged |
| MCP initialization and tool discovery | BLOCKED | Prior stdio child exited 0 without stdout/stderr before `tools/list`; initiating closure cause remains unconfirmed. One official loopback Streamable HTTP attempt failed bind with `listen EPERM` on `127.0.0.1:18765`; no live tools discovered |
| Chromium synthetic browser acceptance | BLOCKED before MCP initialize/browser launch | No MCP tool call reached Chromium; DOM/click/fill/JavaScript and screenshot are NOT TESTED. Chromium sandbox remains enabled; no network/sandbox boundary changed |
| Hermes MCP registration | NOT TESTED | Conditional on Codex browser acceptance succeeding; no Hermes config or service touched |
| Build and dependency check | PASS | `npm ls @playwright/mcp playwright --depth=0`; `npm run build` (Vite 8.4.0) |

The MCP package's transitive Playwright `1.66.0-alpha-2026-11-18` expects Chromium revision 1255, matching the existing cached Chromium Headless Shell `159.0.8154.6`. Package README tool names are not counted as runtime tool discovery. A fresh Codex session is required to load the corrected project entry: `cd /home/sanro/workforce-dev/Sanro-AI-Workforce-gdi02 && codex`. See the detailed probe and approval observations in `evidence/GDI02R_RUNTIME_ACCEPTANCE_20261126.json`.

### Fresh Codex session result — 2026-11-26

| Area | Result | Evidence |
|---|---|---|
| Project MCP initialize and actual tool discovery | PASS | Fresh session exposed all seven scoped Playwright tools; navigation entered the MCP server |
| Chromium navigation and synthetic browser flow | BLOCKED | Browser launch failed before page creation: Chromium fatal `No usable sandbox`, then `SIGTRAP`; sandbox remains enabled |
| DOM inspection, click, input, JavaScript state, screenshot | NOT TESTED | No page was created; no screenshot produced |
| Hermes isolated integration | NOT RUN | Browser acceptance prerequisite failed; no Hermes process/config touched |
| Python regressions | PASS | 35 tests across project runtime executor, Hermes adapter, worker |
| Selected Node API regressions | BLOCKED | Test processes exited before registration; `apps/api/node_modules` absent; no reinstall attempted |
| Resource cleanup | PASS | No Chromium/MCP/profile process remained; no screenshot or temporary page |

Observed approval prompts: **0**. Tested source SHA: `1a35dcb910602d39d8efd0a1e26470688d05dd3e`; delivery SHA is recorded in the follow-up commit. No sandbox relaxation, alternate browser transport, global configuration change, Hermes access, or production access occurred.

## Private Cloud Browser V1 — host execution package — 2026-11-26

| Area | Result | Evidence |
|---|---|---|
| Reuse pinned Playwright MCP and project browser configuration | PASS (source package) | Reuses `@playwright/mcp@0.0.86`, seven-tool config, cached Chromium; no dependencies added |
| Host authorization and sandbox/capacity validation | PARTIAL | Owner reports UID 1001, 4 vCPU, 7.8 GiB RAM, 3.2 GiB available, 1.7 GiB swap in use, Node 22.22.1 and userns/AppArmor values; transient systemd capability not host-tested |
| Workforce project/job admission and authenticated runtime API | IMPLEMENTED, NOT HOST-REGISTERED | Fixed private-browser operation uses existing bearer auth, project scopes, `runtime:browser` approval, mandate/native-approval callback, project/SHA/job checks and bounded single-active FIFO |
| MCP and synthetic browser flow on the authorized host | NOT RUN | Runner now refuses launch without a verified private netns, cgroup caps, non-root UID and sandbox config; no host invocation or sandbox retry |
| Per-job resource boundary and cleanup | IMPLEMENTED IN SOURCE, NOT RUNTIME-VERIFIED | systemd transient user unit specifies 1 CPU, 2 GiB RAM, 128 tasks, hard timeout, `KillMode=control-group`, private tmp, strict filesystem defaults and private job artifacts |
| Default-deny egress and MCP listener isolation | IMPLEMENTED IN SOURCE, NOT RUNTIME-VERIFIED | `PrivateNetwork=yes`; runner checks private netns/loopback-only/no default route and rejects external, metadata and unrelated localhost connection probes |
| Codex/Hermes registration | NOT ACTIVE | Official native runtime callback and private host profile are not registered; no Codex HTTP or isolated Hermes registration |

Focused source checks are recorded in `docs/evidence/PRIVATE_CLOUD_BROWSER_V1_20261126.json`. Current readiness is **NO-GO** for host activation until the official native runtime callback/profile is registered and the target confirms systemd delegated network/cgroup controls. No kernel or AppArmor change is authorized.

## SANRO QA native Hermes profile candidate — 2026-11-26

| Gate | Result | Evidence |
|---|---|---|
| Hermes v0.22 plugin contract and exact tool registration | PASS (synthetic) | Fake context verifies exactly two fixed-schema tools and zero hooks |
| Project/operation binding and fail-closed authorization | PASS (synthetic) | Fixed Workforce project/operation mapping; missing auth, redirect, API failure, mismatch and malformed-result tests |
| Safe profile staging helper | PASS (synthetic/source) | Idempotency, file allowlist, target conflict and exact profile path checks; helper not run on host |
| Plugin/activation tests | PASS | 10 tests |
| Existing policy/executor/worker/Hermes regression | PASS | 39 tests |
| Backup/DR security gate regression | PASS | 11 tests; active hook/config unchanged |
| Installed-profile doctor/activation/rollback | NOT TESTED | No host execution or live-profile mutation |
| Local CI Playwright, Chromium, screenshot, cleanup | NOT TESTED | Native callback and QA profile authorization not activated |

Candidate acceptance **NO-GO for runtime activation**. Total targeted result: 60 PASS / 0 FAIL. Both profiles use OS user `sanro`; profile scoping does not provide OS isolation. See [native profile integration and activation procedure](integrations/SANRO_QA_NATIVE_HERMES_PROFILE_V1.md) and [sanitized evidence](evidence/SANRO_QA_NATIVE_HERMES_PROFILE_V1_20261126.json).

## SANRO Chromium AppArmor runtime recovery — 2026-11-27

| Gate | Result | Evidence |
|---|---|---|
| Executable trust | CORRECTED IN SOURCE; HOST BLOCKED | Previous cache executable and containing directory are owned/writable by `sanro`; workers could replace it. No system executable was found in the Codex-visible environment. New profile target is a separately staged root-owned tree under `/usr/local/lib/sanro-playwright`; native presence/ownership remains unverified. |
| Minimal recovery | VERIFIED SYNTHETIC; NOT ACTIVATED | Source rejects non-root-owned or group/world-writable path components. Control harness covers preflight, repeated apply, rollback, repeat rollback, and failed-load cleanup. `apparmor_parser -K -Q` passes syntax without loading a profile or touching cache. No sysctl/global permission change. |
| Playwright sandbox acceptance | BLOCKED BEFORE BROWSER LAUNCH | Acceptance requires explicit `SANRO_CHROMIUM_EXECUTABLE` at the approved root-owned path, asserts Chromium `159.0.8154.6`, and uses `chromiumSandbox: true`. Guard exits before page creation when the trusted staged binary is absent. DOM/JS, sandbox diagnostics, screenshot and browser cleanup were not runtime-tested. |
| Native VPS runtime | NOT TESTED | No profile activation, Chromium launch, screenshot or native Local CI run. The one-shot Owner-approved copy/profile/test/rollback package is documented at `integrations/SANRO_CHROMIUM_NATIVE_ACTIVATION_20261127.md`. |

The staged tree SHA observed in this environment is `cdc517739626c4ce3b79194009447da47d4a4420944be45324b49c49c0c93461`; it binds bytes but is not a vendor signature. Owner approval must accept that trust basis. Chromium's browser sandbox remains enabled. See [Chromium AppArmor user namespace guidance](https://chromium.googlesource.com/chromium/src/+/main/docs/security/apparmor-userns-restrictions.md), [Playwright BrowserType API](https://playwright.dev/docs/api/class-browsertype), and [recovery evidence](evidence/SANRO_CHROMIUM_APPARMOR_RECOVERY_20261127.json).

One Owner approval is required for copy, profile load, and synthetic acceptance. Runtime status remains **NO-GO / NOT TESTED**. See [recovery evidence](evidence/SANRO_CHROMIUM_APPARMOR_RECOVERY_20261127.json).

## Final functional activation preflight — 2026-11-26

| Gate | Result | Evidence |
|---|---|---|
| Hermes plugin contract | SOURCE REVIEW PASS | v0.22.0 supports directory plugins, tool registration, profile-scoped plugin enable, and `requires_env` secret prompting during install |
| Candidate secure token provisioning | BLOCKED | `plugin.yaml` does not declare `requires_env`; the activation helper only stages and enables; no profile secret was created or copied |
| Native per-job approval | BLOCKED | Hermes approval transport routes an existing human request but does not create approval policy; Workforce requires an injected native callback bound to project/job/operation |
| Authorized executor registration | BLOCKED | API `createApp` accepts `runtimeExecutor`, but default server startup supplies none and runtime route fails closed with 503 |
| Pilot repository authorization | BLOCKED | Candidate binds `sanro-ai-workforce`; `SANRO-Browser-QA` has no verified Project Registry/host auth binding in this checkout |
| Host execution availability | BLOCKED | No callable VPS executor is exposed in this session; no sandbox escape or repeated host attempt was made |
| Chromium/Playwright functional acceptance | NOT TESTED | No valid authorized end-to-end execution path or Job ID |

Prior 60/60 source suite and 11/11 Backup/DR regressions remain reused evidence from SHA `5f465facc3a77dd3237f3f171ace1783a6e07d4f`; they were not rerun. Current functional status is **NO-GO**. See [activation preflight evidence](evidence/SANRO_FINAL_FUNCTIONAL_ACTIVATION_PREFLIGHT_20261126.json).
