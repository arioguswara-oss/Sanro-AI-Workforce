# Hermes Development Policy and Isolated Executor — Candidate V1

## Status

The candidate is implemented and synthetically tested in the Workforce checkout. It is **not registered or active in Hermes**. The live approval hook remains unchanged. No Hermes restart or worker interaction is part of this package.

The live Backup/DR hook uses whole-command text matching. Read-only synthetic probes confirmed that `cat config.json | jq .backup.enabled` requests approval, while `pytest -q tests/test_backup_parser.py` does not. Synthetic archive creation, database dump, and access beneath the protected Hermes path requested approval. These are classification observations, not proof of an authorization bypass: the gate escalates to the native exact-call approval flow and does not execute commands.

## Candidate authorization boundary

The existing `project_runtime_executor.py` remains the execution boundary. Requests are accepted only for fixed operations in `OPERATIONS`, with empty arguments, a canonical clean Git workspace, an exact repository/branch/source SHA, matching Project Registry and worker identity, a private job record bound to project/worker/branch/SHA/operation/mandate/subject/approval evidence, an unexpired zero-cost mandate, bound approval reference, required action scope, and native approval evidence. The executor rejects generic shell, backup, restore, credential/runtime workspaces, replayed jobs and timeouts above 300 seconds. Children retain the existing worker Landlock/seccomp policy; there is no fallback that weakens it.

The workspace-path deny check is defense in depth. It rejects workspace roots containing `.hermes`, `.ssh`, `.aws`, `.gnupg`, `credentials`, or `secrets`, roots beneath `.local/share`, and `/opt/*/worktrees/*` protected roots. It does not replace the private registry, worker sandbox, or native approval.

## Synthetic verification

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_project_runtime_executor integrations.hermes.approval-gate.test_approval_gate
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_worker test_hermes_adapter
```

Expected results for the reviewed candidate: 24 policy/executor/gate tests and 26 worker/Hermes adapter regressions pass. These fixtures use temporary Git repositories and synthetic hook payloads; they do not launch Chromium or execute Backup/DR commands.

## Single activation review procedure

Activation is intentionally pending a separate, explicit Owner approval. Before activation, the authorized Hermes administrator must verify the installed Hermes version's documented native hook/profile registration interface and confirm it supports an isolated project/profile registration. Do not infer a command or config schema from this document.

If the Owner approves that exact registration after review:

1. Stage this candidate as a separate, project-scoped profile while retaining the current Backup/DR gate unchanged and enabled.
2. Bind the profile to the Workforce project/repository/branch, QA worker identity, fixed `local-ci` executor, operation and mandate expiry; require Hermes native exact-call approval for every admitted job.
3. Run the synthetic policy and executor tests above through the registered profile. Verify denial for expired/mismatched mandates, other projects/workers, arbitrary shell, backup/restore, protected paths, credentials, and missing native approval. Verify one allowed synthetic QA fixture and confirm no runtime/browser child was started.
4. Review redacted audit/job records and confirm no secret values, filesystem paths outside the authorized project, or command text are emitted.
5. If any check differs from expected, disable only the candidate profile through Hermes' documented interface, retain the existing hook, and record rollback evidence. Do not restart the live Hermes service unless the documented registration mechanism requires it and a separately approved maintenance window explicitly permits it.

No activation command is supplied because the installed native registration interface has not been verified in this execution, and inventing one would risk modifying the live gate. The current safe action is to review the committed source and this single procedure; registration remains **NO-GO** until the Owner approves a concrete, documented interface and exact scope.
