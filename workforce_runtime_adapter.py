"""Fixed-operation runtime adapter for the already-authorized Workforce bridge."""
from __future__ import annotations

import hashlib
import json
import pathlib

from project_runtime_executor import OPERATIONS, execute, _validate_policy

SANRO_QA_PILOT_ID = "sanro-browser-qa"


def prepare_runtime_profile(request: dict, admission: dict, state_root: str) -> tuple[dict, dict]:
    """Translate verified Workforce records into the narrow runtime wrapper contract."""
    profile = request.get("profile_config")
    project = request.get("project")
    mandate = request.get("mandate")
    principal = request.get("principal")
    operation = profile.get("runtime_operation") if isinstance(profile, dict) else None
    if not isinstance(profile, dict) or profile.get("executor") != "local-ci" or profile.get("role") != "qa" or profile.get("command") != ["/usr/bin/true"] or operation not in OPERATIONS:
        raise PermissionError("profile is not an allowlisted Local CI runtime operation")
    if not isinstance(project, dict) or not isinstance(mandate, dict) or not isinstance(principal, dict):
        raise PermissionError("verified Workforce project, mandate, and principal are required")
    if profile.get("role") != "qa" or project.get("id") not in profile.get("projects", []):
        raise PermissionError("runtime profile project or role mismatch")
    if not isinstance(request.get("approval_ref"), str) or request["approval_ref"] not in principal.get("projects", {}).get(project["id"], {}).get("approval_refs", []):
        raise PermissionError("runtime approval is not bound to the project principal")
    native = request.get("native_approval")
    if not isinstance(native, dict) or native.get("approved") is not True or not isinstance(native.get("evidence_sha256"), str) or len(native["evidence_sha256"]) != 64:
        raise PermissionError("verified native runtime approval evidence is required")
    if admission.get("project_id") != project.get("id") or admission.get("worker_id") != project.get("worker_id"):
        raise PermissionError("runtime admission identity mismatch")
    job_id = admission.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise PermissionError("runtime job identity is missing")

    capability, action, _ = OPERATIONS[operation]
    if action not in mandate.get("allowed_actions", []) or action in mandate.get("forbidden_actions", []):
        raise PermissionError("runtime operation is not explicitly allowed by the mandate")
    if mandate.get("status") != "APPROVED" or mandate.get("max_cost_usd") != 0:
        raise PermissionError("active zero-cost mandate is required")
    workspace = str(pathlib.Path(project["workspace"]).resolve(strict=True))
    state_path = pathlib.Path(state_root).resolve(strict=True) / "runtime-executor" / project["id"]
    approval_digest = hashlib.sha256(request["approval_ref"].encode()).hexdigest()
    mandate_id = (mandate.get("id") if project["id"] == SANRO_QA_PILOT_ID else
                  hashlib.sha256((project["id"] + "\0" + request["approval_ref"]).encode()).hexdigest()[:32])
    timeout = profile.get("runtime_timeout_seconds", 120)
    if type(timeout) is not int or not 1 <= timeout <= 300:
        raise ValueError("runtime profile timeout is outside the fixed bound")

    runtime_request = {
        "version": 1, "project_id": project["id"], "job_id": job_id,
        "worker_id": project["worker_id"], "workspace": workspace,
        "repository": project["repository"], "branch": project["branch"],
        "source_sha": admission["checkpoint_sha"], "checkpoint_sha": admission["checkpoint_sha"],
        "operation": operation, "required_capabilities": [capability],
        "mandate_id": mandate_id, "subject": principal["subject"],
        "approval_ref": approval_digest, "native_approval_sha256": request.get("native_approval", {}).get("evidence_sha256"),
        "timeout_seconds": timeout, "arguments": {},
    }
    runtime_policy = {
        "version": 1,
        "projects": {project["id"]: {"status": "AUTHORIZED", "workspace": workspace,
            "repository": project["repository"], "branch": project["branch"],
            "worker_id": project["worker_id"], "source_sha": admission["checkpoint_sha"],
            "permission_profile": project.get("permission_profile"), "state_root": str(state_path)}},
        "jobs": {job_id: {"status": "AUTHORIZED", "project_id": project["id"],
            "worker_id": project["worker_id"], "branch": project["branch"],
            "source_sha": admission["checkpoint_sha"], "operation": operation,
            "mandate_id": mandate_id, "subject": principal["subject"],
            "approval_ref": approval_digest,
            "native_approval_sha256": request["native_approval"]["evidence_sha256"]}},
        "mandates": {mandate_id: {"status": mandate["status"], "project_id": project["id"],
            "repository": project["repository"], "branch": project["branch"],
            "workspace": workspace, "subject": principal["subject"],
            "expires_at": mandate["expires_at"], "approval_refs": [approval_digest],
            "allowed_actions": list(mandate.get("allowed_actions", [])),
            "forbidden_actions": list(mandate.get("forbidden_actions", [])),
            "max_cost_usd": mandate["max_cost_usd"], "environment": mandate["environment"]}},
    }
    _validate_policy(runtime_policy, runtime_request)
    return runtime_request, runtime_policy


def execute_runtime_profile(request: dict, admission: dict, state_root: str, native_approval: dict | None = None) -> dict:
    if not isinstance(native_approval, dict) or native_approval.get("approved") is not True or not isinstance(native_approval.get("evidence_sha256"), str):
        raise PermissionError("native runtime approval is required")
    runtime_request, runtime_policy = prepare_runtime_profile(request, admission, state_root)
    return execute(runtime_request, runtime_policy)
