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

The worker database persists FIFO jobs, status, logs, idempotency and interrupted checkpoints. Interrupted jobs are not replayed automatically. `/jobs/:id/resume` requires an interrupted parent, a new idempotency key, explicit `side_effects_reconciled`, and an active scoped recovery approval; the API stores only a hash of the review note.

## Verification limits

API route tests invoke the handler directly because this sandbox denies opening loopback listeners. They still run the Python adapter and synthetic worker processes. The React UI source is present, but a Vite build was not verified because package registry access reset during installation. No live model, Hermes, Telegram, or external network call was made.
