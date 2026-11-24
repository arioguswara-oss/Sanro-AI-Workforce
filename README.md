# SANRO AI Workforce

Internal orchestration extension for existing Hermes infrastructure. Development candidate on `feature/hermes-workforce-foundation`, Draft PR #2. No live activation.

Hermes remains the operational AI engine and conversation interface through its existing Web UI, SANRO AI Agent Android and Jack Developer Telegram. Workforce reuses the serial worker, Codex engineering, Local CI and GitHub; it adds durable orchestration, policy, registries, evidence and read-only monitoring. SANRO Supervisor remains an integration target. No replacement Hermes/chat app or new Telegram bots are being built.

## Implemented candidates

- JD-03 strict structured metadata inspection and JD-04 durable FIFO worker/native plugin shim. Native turn-bound actor/session identity, unchanged native approval gate, scoped commands and reduced process environment.
- Free-only OpenAI-compatible adapter, bounded fallback/failback/circuit, quota cooldown, metadata checkpoints, no silent replay, Codex/conversation separation. 9Router and FreeLLMAPI catalog entries remain disabled.
- Node.js/private SQLite project/agent/task/approval/capability registries and audit trail. Deterministic Director runs Developer → QA → one self-fix → committed candidate → checkpoint → report outbox, with explicit reviewed recovery.
- Dedicated `monitor:read` API: sanitized project-scoped DTO, freshness, heartbeat, job/queue/checkpoint/test/blocker data, no worker or task mutation. Future Superadmin Virtual Office component prepared. Superadmin is not modified.
- Existing React/Vite source is preserved; standalone chat development is deferred. Original build and reusable monitoring component build pass; compiled component render/security smoke test passes.

Source/GitHub verification, isolated synthetic execution and live runtime verification are distinct. Real engineering execution fails closed when Landlock is unavailable. Mock executor acceptance does not prove Codex delivery or autonomous Hermes operation. Cron jobs are not changed, and live runtime state is not asserted without access.

See [BUILD_PLAN](docs/BUILD_PLAN.md), [architecture decisions](docs/ARCHITECTURE_DECISIONS.md), [Director contract](docs/ORCHESTRATION_CONTRACT.md), [monitoring contract](docs/MONITORING_API.md), [provider qualification](docs/PROVIDER_QUALIFICATION.md), [checkpoint](docs/DEVELOPMENT_CHECKPOINT.md) and [consolidated host handoff](docs/HERMES_EXECUTION_HANDOFF.md).

No merge, production deployment, native approval bypass, paid API, new service, secret/credential publication or other-project repository change is authorized.
