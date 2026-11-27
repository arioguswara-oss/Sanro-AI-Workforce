# SANRO QA Pilot Operational Activation V1

## Implemented source binding

This package adds the exact `sanro-browser-qa` identity to Workforce admission. It permits `main` only when every pinned field matches, request action is runtime, the profile is the single `local-ci` QA operation `private_browser_acceptance`, and permission profile is `{version:1, read_only:true, write_scope:"none", allow_network:false, allow_process_creation:true}`. `main` and `master` remain denied to all development-write jobs and every other project.

The project binding is repository `arioguswara-oss/SANRO-Browser-QA`, workspace `/home/sanro/workforce-dev/SANRO-Browser-QA-pilot`, source SHA `4436660bfc4dbdf11aadb0800b043c2c75ce6eaa`, worker `sanro-qa`. Owner approval `SANRO-QA-PILOT-OPS-V1` expires at `2026-12-28T23:59:59Z`, costs USD 0, allows `qa:execute` and `runtime:browser`, and denies engineering execution, Git writes, worker management, SSH, merge, production, paid APIs, and other-repository writes.

The fixed runner is `apps/web/scripts/sanro-qa-pilot-local-ci.mjs` in Workforce, outside the pilot checkout. It imports the existing verified Chromium MCP acceptance. The runtime controller supplies only the fixed root-owned Chromium executable, `chromiumSandbox=true`, private network namespace, bounded systemd user unit, `ProtectSystem=strict`, and per-job writable evidence under the host state directory. It does not install packages or write to the pilot repo. No new executor is introduced.

## Native host registration record

Merge the following values into the existing private authorization file designated by `WORKFORCE_AUTH_FILE` using the host's authorized private-config procedure. Do not replace unrelated projects, principals, approvals, or profiles. The Owner principal `subject` must be the existing authenticated Owner subject; do not create a new principal or token for this record.

```json
{
  "project": {
    "id": "sanro-browser-qa",
    "name": "SANRO Browser QA synthetic pilot",
    "repository": "arioguswara-oss/SANRO-Browser-QA",
    "workspace": "/home/sanro/workforce-dev/SANRO-Browser-QA-pilot",
    "branch": "main",
    "source_sha": "4436660bfc4dbdf11aadb0800b043c2c75ce6eaa",
    "worker_id": "sanro-qa",
    "mainline_qa_only": true,
    "environment": "isolated-development",
    "permission_profile": {
      "version": 1,
      "read_only": true,
      "write_scope": "none",
      "allow_network": false,
      "allow_process_creation": true
    }
  },
  "owner_principal_project_grant": {
    "project_id": "sanro-browser-qa",
    "scopes": ["read", "runtime:browser"],
    "approval_refs": ["SANRO-QA-PILOT-OPS-V1"]
  },
  "approval": {
    "id": "SANRO-QA-PILOT-OPS-V1",
    "project_id": "sanro-browser-qa",
    "subject": "<existing Owner principal subject>",
    "owner_actor": "<same existing Owner principal subject>",
    "status": "APPROVED",
    "repository": "arioguswara-oss/SANRO-Browser-QA",
    "branch": "main",
    "environment": "isolated-development",
    "max_cost_usd": 0,
    "scopes": ["runtime:browser"],
    "allowed_actions": ["qa:execute", "runtime:browser"],
    "forbidden_actions": ["engineering:execute", "git:write", "worker:manage", "ssh:staging", "merge", "production:deploy", "paid-api", "other-repository:write"],
    "expires_at": "2026-12-28T23:59:59Z"
  },
  "command_profile": {
    "id": "sanro_qa_browser",
    "executor": "local-ci",
    "role": "qa",
    "projects": ["sanro-browser-qa"],
    "command": ["/usr/bin/true"],
    "runtime_operation": "private_browser_acceptance",
    "runtime_timeout_seconds": 180
  }
}
```

The placeholders are references to the already existing Owner principal and must be resolved by the host's private-config procedure. The Owner mandate is not itself a native per-job approval. Keep the official host approval callback mandatory; it must independently approve the exact actor/project/job/operation tuple. Workforce returns 503/403 and launches nothing if that provider is absent, denies, or returns mismatched evidence. Do not substitute a test callback.

## Preflight, one acceptance, and rollback

1. Use the authorized host config mechanism to validate the existing auth file is canonical, current-user-owned, mode `0600`; preserve a private rollback snapshot outside Git. Confirm the pilot checkout remote/branch/SHA is exact and clean. Confirm profile key is unique, the Owner subject is existing, approval expires exactly as above, and no operational/write scope is granted.
2. Confirm the real native approval provider is already available through the supported `createApp({nativeApprovalProvider})` host seam. If absent, stop here with no registration activation or service change. This cycle does not add or fabricate a provider.
3. Load the project binding using the host's existing Workforce auth reload mechanism only after confirming no active Workforce job is in flight. Do not restart Hermes or any worker. If loading requires interrupting an active job, defer the whole activation.
4. Submit exactly one request to the existing `/api/projects/sanro-browser-qa/runtime-acceptance` route using profile `sanro_qa_browser`, approval reference `SANRO-QA-PILOT-OPS-V1`, and a unique ID `sanroqa-pilot-<date>-<random>`. The native provider must present a genuine per-job approval. Accept PASS only when the response includes the matching Job ID, Chromium 159, sandbox diagnostics PASS, DOM/JavaScript result, screenshot path+SHA-256, and resource cleanup PASS.
5. On any preflight or acceptance failure, remove only the new project, principal-project grant, approval, and profile records from the private auth file using the same host config mechanism. Restore only those exact entries from the rollback snapshot; preserve the failure evidence and all pre-existing records. Do not roll back the committed Workforce source binding.

## Current activation state

Source and synthetic regressions are prepared in Workforce. The private host file and genuine native approval callback are not exposed to this Codex runtime; no private binding was written, no service was reloaded, and no pilot job was started. Existing Chromium Runtime Recovery evidence remains locked and is reused. Therefore host registration and native acceptance are **BLOCKED / NOT TESTED** until this one handoff can run through the existing official host approval mechanism.
