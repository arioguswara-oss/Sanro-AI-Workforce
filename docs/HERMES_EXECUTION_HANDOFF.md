# Consolidated Hermes execution handoff
Updated 25 November 2026 Jakarta. For an authorized Hermes executor, not a sequence of terminal tasks for Owner.

## Checkpoint and mandate
Repository `arioguswara-oss/Sanro-AI-Workforce`; branch `feature/hermes-workforce-foundation`; existing Draft PR #2. Tested source commit `44ed2cedb2f5d40829b3f215e1dd09026a91ed6d`; subsequent checkpoint/evidence changes are documentation only. Read current PR head and verify source before continuing. Do not use local Work-mode commit IDs as remote SHAs; connector publishing produces different commit identities with the same source tree.

No main/force push/merge, production, other-repository modification, new bots/services/paid APIs, live plugin activation or Gateway restart. Both autonomous cron jobs must remain PAUSED. Their actual remote state was not observed. This handoff does not authorize live activation.

Cloud browser inspection of Hermes Web UI reached Cloudflare Access sign-in. No credential was obtained, entered or bypassed. No authenticated VPS terminal/Gateway interface was available in this session. Continue through a legitimately authenticated existing interface; do not source credentials from logs/chat/GitHub.

## Five remaining host tasks

1. **Read-only capability and authority reconciliation.** Inspect installed Hermes SHA, actual bound actor/session/native approval interfaces, existing Codex CLI/Local CI, routing config and service/cron state. Use `scripts/check_hermes_interfaces.py --source <approved-Hermes-source>`; it parses source and never imports/activates Hermes. Keep sanitized SHA/status evidence only. Public upstream reference inspected here is `2506f5b0a4d310b96ec2eb6f2de4ea7349ba4d15`; it is not proof of installed version compatibility.
2. **Isolated worker acceptance.** Use an isolated feature worktree and private state. Run the consolidated candidate verifier below on a supported Linux environment. Verify real FIFO, timeout/cancel, dedup/content conflict, restart/recovery, foreground conversation responsiveness, filesystem/network/process/credential boundaries. Do not disable Landlock/seccomp or escalate privileges to make tests pass. Landlock ABI 0 here correctly blocked execution.
3. **Existing Codex executor admission.** Review project-scoped fixed Codex/Local CI wrappers and native approval/session binding in an isolated Hermes harness. Current restricted subprocess denies network and process creation, and does not receive Codex credentials; it is not qualified to run authenticated/networked Codex directly. Inspect/reuse an existing approved broker/executor rather than weakening confinement or copying credentials into a worktree. Verify approval expiry/revocation at dequeue and cancellation admission; backend private config is a snapshot, not an atomic native revocation mechanism. Keep activation blocked if these controls cannot be met.
4. **Authenticated integration acceptance.** Through isolated host interfaces, prove Owner → Director → actual Codex → Local CI QA → at most one self-fix → clean SHA candidate → checkpoint → existing Jack Telegram acknowledged report. Bind actor/session/project/branch/environment and zero-cost mandate. Verify two foreground requests while one engineering job runs. Test native pending/deny/expiry without altering native approval policy. Transport must deduplicate delivery keys. Do not create a bot, use another repository or claim outbox enqueue equals Telegram delivery. The current Director prepares candidates/reports; it does not create Draft PRs for individual jobs yet. Existing Draft PR #2 was updated by Work's authorized GitHub connector.
5. **Grouped activation decision after evidence.** Keep 9Router/FreeLLMAPI disabled until installed version, explicit free-only downstream routing, account quota/terms and capability evidence pass. FreeLLMAPI's experimentation scope remains unresolved. Present remaining host/security/approval/transport gates as one decision package. Only after those gates and separate Owner activation authorization may live services/plugins/cron be considered. Superadmin integration/deployment and production/merge require their own mandates.

## Single candidate verification entry point

From the approved isolated Workforce checkout, the executor runs:

```bash
python3 scripts/verify_candidate.py --require-worker --source-ref HEAD --output /absolute/private/evidence/workforce-acceptance.json
```

This runs Python suites, API/Director/HTTP/Git evidence tests, both existing/reusable frontend builds, compiled monitor render smoke test, secret-pattern scan and diff check. It installs locked web dependencies with scripts disabled only if missing. It never modifies live Hermes, submits production work, sends Telegram messages or calls model providers. Output path must be private until sanitized. Node.js >=22.13, npm, Python and supported Linux confinement are required. A missing confinement capability causes nonzero exit with `--require-worker`; without the flag, portable cases can PASS while worker acceptance remains BLOCKED.

No test restore, backup service, tunnel, database server or paid provider is added. Do not repeat already passing portable tests absent source/environment changes; focus on the missing host acceptance.
