# GDI-02R project runtime executor integration

This artifact adds a fixed-operation wrapper to the existing Workforce project admission path. It does not install or activate a Hermes plugin, start a service, or grant a runtime permission.

## Supported profiles

Create a private, project-scoped Local CI profile in the existing Workforce authorization registry. The inert command is required by the current profile schema; the runtime endpoint never submits or executes it.

```json
{
  "command": ["/usr/bin/true"],
  "projects": ["<project-id>"],
  "role": "qa",
  "executor": "local-ci",
  "runtime_operation": "browser_smoke",
  "runtime_timeout_seconds": 120
}
```

Use `mariadb_synthetic` for the isolated MariaDB acceptance. The profile loader rejects any other operation, role, executor, command, or timeout. Generic `/jobs` submission rejects runtime profiles; only `POST /api/projects/{project-id}/runtime-acceptance` can select one, and the operation is taken from the private profile, never from the HTTP body.

The project principal and active mandate must both carry the matching operation scope (`runtime:browser` or `runtime:mariadb`). The mandate also remains bound to project, repository, branch, isolated-development environment, owner and zero cost. SSH has no profile, operation or capability in this wrapper.

## Native approval and host registration

`createApp({ runtimeExecutor })` accepts an explicit host adapter. The adapter receives the already validated project, profile, mandate, admission and an `invokeAfterNativeApproval` callback. It must request approval through the installed Hermes/Local CI native approval mechanism and invoke that callback only after its native result is literally `approved === true`. A pending, denied, absent, stale or mismatched result must not invoke it. The Workforce API business approval by itself does not satisfy this native gate.

Example registration shape for a reviewed host adapter:

```js
createApp({
  runtimeExecutor: async context => {
    const native = await existingHermesNativeApproval(context);
    if (!native || native.approved !== true) return { status: 'BLOCKED' };
    return context.invokeAfterNativeApproval({
      approved: true,
      actor: native.actor,
      project_id: native.project_id,
      job_id: native.job_id,
      operation: context.profile.runtime_operation,
      id: native.id
    });
  }
});
```

`existingHermesNativeApproval` is a host-provided integration point, not a new service or a function implemented here. The callback must return actor, project, job, operation and native approval ID bound to that exact pending request. The API validates those bindings and stores only a SHA256 of the native approval ID. Do not register this callback until it is bound to the real host actor/session and native approval evidence. With no callback registered, the endpoint fails closed with 503.

After the native gate, the existing Workforce bridge revalidates project registry, repository, branch, clean source SHA, current mandate, approval reference and Local CI identity. `workforce_runtime_adapter.py` maps only the fixed operation to `project_runtime_executor.py`. The wrapper takes the existing per-worktree lock, uses a unique temporary directory, caps execution at 300 seconds, creates private durable job/audit records, and rejects duplicate replay. Its child inherits the existing Landlock and seccomp worker policy through `apply_job_sandbox`; there is no sandbox downgrade or fallback. Network and SSH remain unavailable.

The Chromium and MariaDB operations are real entrypoints, but executing them under the present seccomp profile can still fail because that profile denies socket syscalls. This implementation does not change the profile. Runtime PASS requires an actual child execution and successful operation output; API or fixture mocks do not count.

## Operator call after reviewed host registration

```http
POST /api/projects/<project-id>/runtime-acceptance
Authorization: Bearer <project token>
Content-Type: application/json

{"profile":"<private-fixed-profile-id>","approval_ref":"<current-approval-ref>","idempotency_key":"<unique-job-id>"}
```

The HTTP request cannot supply a shell command, arguments, executable, workspace, branch, timeout, operation or capability. A retry with the same job id is rejected by the durable checkpoint. A blocked or failed checkpoint is not automatically resumed; use a separately reviewed new job id after investigating the evidence.

Registration and execution remain inactive until the Owner-authorized host integrator wires the official native approval callback and verifies the executor’s inherited sandbox. No Hermes configuration was changed by this implementation.

## Consolidated activation proposal

The host administrator should register this callback for the single authorized Workforce project, bind it to native actor/session and job/operation approval, and provide a project-scoped Local CI execution profile that supports Chromium and isolated MariaDB while preserving network denial, workspace boundaries, timeouts and audit. The current seccomp profile denies all socket syscalls, so these operations cannot pass under it; any compatible executor policy must receive security review and must not be implemented as an unrestricted shell or global sandbox change. Then run one synthetic browser and MariaDB acceptance and capture the evidence before considering any live activation. Hermes config registration and any host policy change remain outside this source-only implementation.
