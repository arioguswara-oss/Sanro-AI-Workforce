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

`createApp({ runtimeExecutor })` accepts an explicit host adapter. The adapter receives the already validated project, profile, mandate, admission and an `invokeAfterNativeApproval` callback. `createApp({ nativeApprovalProvider })` now registers the fixed adapter from `apps/api/src/native-runtime-executor.js`; the provider receives only actor/project/job/operation and must return a literal approved record bound to that tuple. A pending, denied, absent, stale or mismatched result must not invoke execution. The Workforce API business approval by itself does not satisfy this native gate. The default `node src/server.js` startup supplies neither adapter and remains fail-closed.

The provider parameter is an application integration seam, not a claim that Hermes v0.22 exposes such a provider. Hermes approval transports route a human approval that another supported runtime has already created; they are not an approval policy/callback API. No native provider was found in the installed-runtime evidence for this checkpoint. Do not pass a guessed Hermes function or synthesize an approval.

Example registration shape after a real supported provider is available:

```js
createApp({
  nativeApprovalProvider: verifiedNativeApprovalProvider
});
```

`verifiedNativeApprovalProvider` must be a real installed host mechanism bound to the active actor/session and exact pending job. The API validates those bindings and stores only a SHA256 of the native approval ID. This function is intentionally not supplied by this repository. With no provider registered, the endpoint fails closed with 503.

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

## Consolidated host preflight and activation blocker

Run the single read-only preflight from the authorized non-root VPS checkout:

```bash
bash scripts/sanro-qa-runtime-activation.sh
```

It verifies the existing `sanro-qa` profile/plugin prerequisites, then exits `3` with the exact blocker. It never installs/enables the plugin, reads secrets, starts a job, or restarts Hermes. This is the safe procedure for the current runtime contract. There is no supported activation command until Hermes/Local CI provides a documented native per-job approval provider bound to actor/session and job/operation, and the installed API is started with that provider. Merely approving plugin activation cannot manufacture that missing callback. Once that interface exists, the host activation must separately validate the SANRO-Browser-QA project/workspace/repository/branch/worker and operation scopes, provision profile-local env values through Hermes `requires_env`, and run one authorized synthetic job. The current API worker sandbox also denies socket syscalls; Chromium/MCP cannot be declared ready until a supported isolated executor path preserves the security boundaries and passes actual acceptance.
