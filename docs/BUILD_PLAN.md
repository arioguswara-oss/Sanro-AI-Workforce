# SANRO AI Workforce — Hermes-first execution plan
Updated: 25 November 2026 (Asia/Jakarta). Supersedes standalone chat/four-bot plans.

## Product and authority
Hermes remains the operational engine and conversation interface. Workforce supplies orchestration, registries, durable jobs/checkpoints, routing policy and sanitized monitoring. Reuse Hermes Web UI, SANRO AI Agent Android, Jack Developer Telegram, Codex CLI and Local CI. No new chat app, bots, VPS or paid APIs. Preserve `apps/web` source for future Superadmin component reuse; standalone chat development is DEFERRED.

Only `arioguswara-oss/Sanro-AI-Workforce`, branch `feature/hermes-workforce-foundation`, Draft PR #2 is writable. No main changes, force push, merge, other project repository writes, live Gateway/plugin activation, production deployment or native approval bypass. Both autonomous cron jobs remain PAUSED; their remote state cannot be asserted without access.

## Five sequential work packages
| Package | Engineering output | Acceptance |
|---|---|---|
| WP1 | Reconcile architecture, reuse map and ledger | No contradictory active chat/bot plan; existing source preserved |
| WP2 | Reuse JD-03 inspection and JD-04 worker; native session/approval bridge hardening | Isolated FIFO, timeout, cancellation, deduplication, recovery and foreground responsiveness |
| WP3 | Free-only 9Router/FreeLLMAPI adapter candidate | Mocked fallback/failback/circuit/pause/resume; unverified providers disabled; Codex engineering |
| WP4 | Durable Director pipeline and reporting outbox over existing executor | Developer → QA → bounded self-fix → candidate → checkpoint → report; restart and isolation |
| WP5 | Dedicated read-only monitoring contract | Project scope, sanitization, freshness, mutation denial and isolated acceptance |

## Reuse map
| Existing source | Reuse |
|---|---|
| `worker.py`, `hermes_adapter.py`, plugin shim | Serial subprocess executor, native approval, owner/session binding |
| `integrations/hermes/structured-inspection` | Fixed-schema metadata inspection; host UID authorization only, no arbitrary filesystem reads |
| `model_routing.py`, `provider_adapters.py` | Free conversation inference, cooldown and metadata checkpoints |
| `apps/api/src/store.js`, `auth.js`, `server.js` | Private SQLite, project ACL, registries and audit |
| `apps/web/src/main.jsx`, styles | Preserve source; extract monitoring component for future Superadmin integration |

## Release boundary
Source implementation, GitHub verification, isolated runtime verification and live runtime verification are separate. Synthetic executors do not prove real Codex delivery. Public upstream interface inspection does not establish installed VPS version compatibility. Consolidate remaining host checks in one handoff. Activation requires separate Owner authorization after the runtime/session/approval/security gates pass.
