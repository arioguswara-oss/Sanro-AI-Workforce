# SANRO AI Workforce

Internal multi-agent engineering workspace for the SANRO ecosystem.

**Status:** PLANNED / NOT IMPLEMENTED (initial repository documentation).

## Goal
One Owner instruction through a ChatGPT-style web app or a private Telegram group can be delegated by an AI Director to Developer, QA and DevOps workers, with traceable jobs, bounded self-fix, evidence and Draft PRs. High-risk actions require specific Owner approval.

## Architecture principles
- **Development First**, reuse existing Hermes/SANRO AI Supervisor capabilities; do not replace running workers.
- Four logical agent identities: **Director, Developer, QA Engineer, DevOps**; one central orchestrator and shared task ledger.
- **Two communication surfaces:** web chat (individual/group chats) and four separate Telegram bot identities in one private group with project topics.
- Conversations and tasks have unique IDs; the backend ledger is authoritative. Telegram is not an execution bus.
- **Approval by exception** under a scoped, expiring, recorded mandate. No blanket production, merge, billing, secrets or destructive access.
- Source repository is **public** by Owner decision; secrets, access control data, raw evidence and active mandates are kept out of GitHub.

## Delivery
See `docs/BUILD_PLAN.md` (to be proposed on a development branch) for implementation priorities, agent responsibilities, dependency order and acceptance tests.

## Existing systems
- [SANRO AI Supervisor](https://github.com/arioguswara-oss/Sanro-AI-Supervisor) — integration/reuse target; existing PRs are not assumed deployed.
- Hermes VPS — intended isolated execution runtime; inspect current state before any changes.
- [SANRO Studio pilot](https://github.com/arioguswara-oss/Plugin-Kaoscetak) — first autonomous-workflow validation target.

No service deployment, model API purchase, bot creation or active worker modification is authorized by this README.
