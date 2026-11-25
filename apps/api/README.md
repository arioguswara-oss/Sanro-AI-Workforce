# Isolated API foundation

The API uses Node.js built-ins and `node:sqlite` (Node.js 22.13+; SQLite is still marked experimental by the current Node runtime). It is a development candidate; no API listener or worker is active by default.

## Local authorization input

Provide a private JSON file outside the public repository, owned by the API user with mode `0600`. The API rejects missing, symlinked, group-readable, or world-readable authorization files. This schema is intentionally not committed with real workspaces or identities:

```json
{
  "version": 1,
  "projects": [{"id":"sample-project","name":"Sample","workspace":"/absolute/path/to/approved/worktree"}],
  "principals": [{
    "subject":"owner-id",
    "token_sha256":"<64 lowercase hex SHA-256 characters>",
    "projects": {"sample-project": {
      "workspace":"/absolute/path/to/approved/worktree",
      "scopes":["read","thread:write","task:create","workflow:director","workflow:developer","workflow:qa","engineering:execute","engineering:read","engineering:cancel","engineering:recover"],
      "approval_refs":["approval-id"]
    }}
  }],
  "approvals": {"approval-id": {
    "project_id":"sample-project","subject":"owner-id","status":"APPROVED",
    "scopes":["engineering:execute","engineering:recover"],"expires_at":"<future ISO-8601 timestamp>"
  }},
  "command_profiles": {"synthetic-check": {
    "projects":["sample-project"],"approval_required":true,
    "command":["/usr/bin/printf","synthetic job\\n"]
  }}
}
```

Approval records are read-only to the application. A trusted host must provide a reference from its already verified approval path; this candidate does not mint or replace Hermes/native approvals. The command is selected by profile ID, never accepted as shell text from an API request. A matching approval, project, subject, scope, workspace, and expiry are required for execution; recovery additionally requires `engineering:recover` and an explicit side-effect reconciliation statement.

## Local launch

Set `WORKFORCE_AUTH_FILE` and `WORKFORCE_STATE_DIR` in the local process environment, then run `node apps/api/src/server.js`. The state directory must be user-owned mode `0700`; SQLite state/checkpoints are private. The API binds to loopback only. `WORKFORCE_WORKER_AUTOSTART=1` starts a process-local worker supervisor; otherwise worker start/stop requires both `WORKFORCE_ALLOW_WORKER_CONTROL=1` and a scoped `worker:manage` grant. No systemd, cron, live Hermes, Telegram, or model configuration is activated.

Worker commands inherit only a small environment. Each job is confined to the configured worktree and private temporary directory by Landlock, and an unprivileged seccomp filter denies socket/network syscalls, process-group escape, process inspection, and external signals. Jobs remain same-UID processes on the same kernel; this is not a VM/container boundary, does not isolate kernel vulnerabilities, and cannot certify that an approved worktree contains no secrets. Live activation remains blocked pending independent security review and actual native approval verification.

## Optional Herdr supervisor candidate

The default backend remains the local Workforce controller. The inactive candidate can select Herdr with `WORKFORCE_WORKER_BACKEND=herdr`, `WORKFORCE_HERDR_PROJECT_ID=<one authorized project>`, and the existing scoped `WORKFORCE_ALLOW_WORKER_CONTROL=1`; start also requires `WORKFORCE_HERDR_CORE_ENV_ATTESTED=1` after an operator verifies the isolated host and pinned Herdr Core `0.1.22`. `WORKFORCE_WORKER_AUTOSTART=1` is rejected for this backend. Status polling does not start Core. The adapter uses the documented `hc` CLI with argv (no shell), and starts only the fixed serial Workforce queue consumer. Job dispatch, durable state, ACL, approvals, checkpoint and recovery continue through the Workforce SQLite queue. Optional OSC 7501 worker status is emitted only in this supervisor process and contains no job/user data.

This adapter currently supports only a **co-located** Herdr Core, API, worker code, workspace and durable queue. Remote `hc --on` machines are rejected because this prototype has no shared transaction store or verified code/state synchronization across machines. No Herdr service is installed, started, or exposed by this repository. Do not set the attestation flag until host identity, filesystem ownership, runtime version, workspace and resource limits are independently checked. Herdr terminals execute with the account's host permissions; a session is not a sandbox or an approval boundary. The Android app connects to the machine over SSH, and the corresponding account/key must be treated as shell-level worker control, not read-only telemetry. Never use an account containing unrelated credentials or production access for this pilot.

Recovery is conservative: an exited Herdr terminal is reported as completed/failed/cancelled/interrupted from its terminal record; it is never relaunched automatically. An interrupted job requires the existing Workforce explicit recovery approval and side-effect reconciliation flow. Herdr `kill` is only issued by the authorized worker-management route.

The worker database persists FIFO jobs, status, logs, idempotency and interrupted checkpoints. Interrupted jobs are not replayed automatically. `/jobs/:id/resume` requires an interrupted parent, a new idempotency key, explicit `side_effects_reconciled`, and an active scoped recovery approval; the API stores only a hash of the review note.

## Hermes-first orchestration and monitoring

See [Director contract](../../docs/ORCHESTRATION_CONTRACT.md) for fixed Codex/Local CI profiles, native approval boundary, durable automatic stages, reviewed recovery and existing-transport report outbox. The Director timer is OFF unless explicitly enabled by an authorized integrating host.

See [monitoring contract](../../docs/MONITORING_API.md) for dedicated `monitor:read` credentials and GET-only sanitized data. This interface has no task, worker, approval or terminal control. Future Superadmin integration is outside this repository's mandate.

## Verification limits

The `f909923` checkpoint recorded Landlock ABI 0; the current development host reports ABI 8. The post-reconciliation API and worker suites now pass synthetically under this host. Original React/Vite and reusable monitoring component builds pass; API/Director and isolated HTTP monitoring acceptance pass. This does not verify the target VPS. Native Herdr Core/Android, live Hermes/Telegram/Codex, and provider account/quota remain NOT TESTED. No services are activated by tests.

Herdr controller and OSC status tests use a mocked CLI and synthetic worker only. No installed `hc`, SSH authentication, VPS inventory, Herdr session, or Android connection was verified.
