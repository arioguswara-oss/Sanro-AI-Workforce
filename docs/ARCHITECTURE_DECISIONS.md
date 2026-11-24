# Active architecture decisions — 25 November 2026

- ADR-001: Public source only; private ACL, credentials, chat, runtime logs and approvals stay outside Git.
- ADR-002: Hermes-first. Existing Hermes Web UI, Android and Jack Developer Telegram are conversation surfaces. Workforce is an internal orchestration extension.
- ADR-003: Supersedes earlier four-bot proposal. Use existing Telegram transport only, consolidated result/blocker/critical-approval reports; no bots created.
- ADR-004: Supersedes standalone Workforce chat MVP. Existing React/Vite source is preserved, standalone development deferred; dashboard components may later move into Superadmin under a separate mandate.
- ADR-005: Codex is the preferred engineering executor. Free conversational routes never receive engineering tools. Unknown or paid cost and unverified routes remain disabled.
- ADR-006: Serial FIFO by default, durable checkpoints, idempotent stage submission, no automatic replay after uncertain side effects. Native Hermes approvals remain authoritative.
- ADR-007: Dedicated `monitor:read` scope, GET-only fixed projection. Monitoring reads persisted evidence; never calls worker lifecycle, native tools or side-effecting job status adapters.
- ADR-008: No live activation under this mandate. Both autonomous cron jobs remain PAUSED. No Superadmin code changes.
