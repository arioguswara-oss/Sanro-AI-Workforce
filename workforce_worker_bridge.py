"""Private stdio bridge from the local Workforce API to the JD-04 adapter."""
import json
import os
import math
import pathlib
import subprocess
import sys

from hermes_adapter import Authorization, HermesAdapter
from codex_job_launcher import build_codex_argv
from runtime_preflight import CapabilityPreflightError, collect_runtime_preflight, require_capabilities
from workforce_runtime_adapter import execute_runtime_profile
from project_runtime_executor import SANRO_QA_PILOT


def verify_bridge_admission(request):
    project = request["project"]
    registered = request["projects"].get(project["id"])
    admission = request.get("admission")
    mandate = request.get("mandate")
    if not isinstance(admission, dict) or not isinstance(registered, dict) or not isinstance(mandate, dict):
        raise PermissionError("validated project admission required")
    workspace = pathlib.Path(project["workspace"])
    if not workspace.is_absolute() or ".." in workspace.parts or workspace.resolve(strict=True) != workspace:
        raise PermissionError("canonical workspace required")
    for parent in [workspace, *workspace.parents]:
        if parent.is_symlink():
            raise PermissionError("workspace symlinks are not permitted")
    fields = {"project_id": project["id"], "repository": project.get("repository"), "branch": project.get("branch"), "environment": project.get("environment"), "workspace": str(workspace), "worker_id": project.get("worker_id"), "permission_profile": project.get("permission_profile")}
    if any(admission.get(key) != value for key, value in fields.items()):
        raise PermissionError("project admission does not match the workspace registry")
    if admission.get("command_profile") != (request.get("profile_config") or {}).get("executor", "local"):
        raise PermissionError("executor identity does not match admission")
    profile=request.get("profile_config") or {}
    pilot_qa=(request.get("action")=="runtime" and project.get("id")==SANRO_QA_PILOT["project_id"]
              and profile.get("runtime_operation")==SANRO_QA_PILOT["operation"]
              and project.get("repository")==SANRO_QA_PILOT["repository"]
              and project.get("workspace")==SANRO_QA_PILOT["workspace"]
              and project.get("branch")==SANRO_QA_PILOT["branch"]
              and project.get("source_sha")==SANRO_QA_PILOT["source_sha"]
              and project.get("worker_id")==SANRO_QA_PILOT["worker_id"]
              and project.get("mainline_qa_only") is True
              and project.get("permission_profile")=={"version":1,"read_only":True,"write_scope":"none","allow_network":False,"allow_process_creation":True})
    if mandate.get("status") != "APPROVED" or mandate.get("project_id") != project["id"] or mandate.get("repository") != project.get("repository") or mandate.get("branch") != project.get("branch") or mandate.get("environment") != "isolated-development" or mandate.get("owner_actor") != request["principal"].get("subject") or mandate.get("max_cost_usd") != 0:
        raise PermissionError("mandate does not match admission")
    grants = request["principal"].get("projects", {}).get(project["id"], {})
    required_scope=SANRO_QA_PILOT["scope"] if pilot_qa else "engineering:execute"
    if required_scope not in grants.get("scopes", []) or request.get("approval_ref") not in grants.get("approval_refs", []) or required_scope not in mandate.get("scopes", []):
        raise PermissionError("approval is not bound to the project principal")
    required_actions=("qa:execute", "runtime:browser") if pilot_qa else ("engineering:execute", "qa:execute")
    required_denies=("engineering:execute", "git:write", "worker:manage", "ssh:staging", "merge", "production:deploy", "paid-api", "other-repository:write") if pilot_qa else ("merge", "production:deploy", "paid-api", "other-repository:write")
    if not all(x in mandate.get("allowed_actions", []) for x in required_actions) or not all(x in mandate.get("forbidden_actions", []) for x in required_denies):
        raise PermissionError("mandate action scope is incomplete")
    if pilot_qa and set(mandate.get("allowed_actions", []))!={"qa:execute","runtime:browser"}:
        raise PermissionError("pilot mandate action scope is broader than read-only QA")
    if pilot_qa and (mandate.get("id")!=SANRO_QA_PILOT["approval_id"] or mandate.get("expires_at")!=SANRO_QA_PILOT["expires_at"]):
        raise PermissionError("SANRO QA pilot Owner mandate is not the pinned approval")
    if mandate.get("expires_at") is None:
        raise PermissionError("mandate expiration is required")
    from datetime import datetime
    expires = datetime.fromisoformat(mandate["expires_at"].replace("Z", "+00:00"))
    if expires.timestamp() <= __import__("time").time() or admission.get("mandate_expires_at") != mandate["expires_at"]:
        raise PermissionError("mandate expired")
    if request.get("instruction"):
        manifest = json.loads(request["instruction"])
        if manifest.get("project_id") != project["id"] or manifest.get("run_id") != admission.get("job_id") or manifest.get("baseline_sha") != admission.get("checkpoint_sha"):
            raise PermissionError("current job or checkpoint does not match admission")
        expected_capabilities = {"codex": ["engineering"], "local-ci": ["local_ci"]}.get(manifest.get("executor"))
        if expected_capabilities is None or manifest.get("required_capabilities") != expected_capabilities:
            raise PermissionError("job capability requirements do not match the authorized executor")
    elif admission.get("job_id") != request.get("idempotency_key"):
        raise PermissionError("current job does not match admission")
    if registered.get("workspace") != str(workspace) or registered.get("worker_id") != admission.get("worker_id"):
        raise PermissionError("workspace registry mismatch")
    run_git = lambda *args: subprocess.run(["git", "-C", str(workspace), *args], check=True, capture_output=True, text=True, timeout=5, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1"}).stdout.strip()
    branch = run_git("branch", "--show-current")
    remote = run_git("config", "--get", "remote.origin.url").removesuffix(".git")
    expected = {f"https://github.com/{project['repository']}", f"git@github.com:{project['repository']}"}
    current_sha = run_git("rev-parse", "HEAD")
    dirty = run_git("status", "--porcelain", "--untracked-files=all")
    if branch != project.get("branch") or remote not in expected or current_sha != admission.get("checkpoint_sha") or dirty:
        raise PermissionError("repository, branch, checkpoint or clean-worktree admission failed")
    if pilot_qa and current_sha!=SANRO_QA_PILOT["source_sha"]:
        raise PermissionError("SANRO QA pilot source SHA differs from the approved pin")
    return admission


def main():
    request = json.load(sys.stdin)
    state_root = os.environ["WORKFORCE_WORKER_STATE"]
    projects = request["projects"]
    profiles = request["profiles"]
    allowed = [entry["command"] for entry in profiles.values()]
    adapter = HermesAdapter(state_root, {k: v["workspace"] for k, v in projects.items()}, allowed)
    try:
        action = request["action"]
        p = request["project"]
        principal = request["principal"]
        mandate = request.get("mandate")
        grants = principal["projects"][p["id"]]
        auth = Authorization(
            subject=principal["subject"],
            scopes=frozenset(grants["scopes"]),
            project_ids=frozenset([p["id"]]),
            workspaces=frozenset([p["workspace"]]),
            approval_refs=frozenset(grants.get("approval_refs", [])),
        )
        if action == "submit":
            profile = profiles.get(request["profile"])
            if not profile:
                raise PermissionError("unknown command profile")
            if profile.get("runtime_operation") is not None:
                raise PermissionError("runtime profiles must use the dedicated runtime-acceptance boundary")
            if profile.get("approval_required", True) and not request.get("approval_ref"):
                raise PermissionError("an explicit authorized approval reference is required")
            if p["id"] not in profile.get("projects", []):
                raise PermissionError("profile project mismatch")
            request["profile_config"] = profile
            admission = verify_bridge_admission(request)
            command = list(profile["command"])
            if profile.get("executor") == "codex":
                if not isinstance(request.get("instruction"), str):
                    raise PermissionError("Codex executor requires a checkpoint-bound instruction")
                codex_command = profile.get("command")
                codex_executable = codex_command[0] if isinstance(codex_command, list) and len(codex_command) == 1 else None
                preflight = collect_runtime_preflight(p, mandate, admission.get("checkpoint_sha"), codex_executable=codex_executable)
                requirements = profile.get("runtime_requirements", ["project_identity", "canonical_workspace", "authorized_branch", "source_repository", "workspace_write", "git_metadata", "mandate", "checkpoint", "codex_cli"])
                require_capabilities(preflight, requirements)
                command = build_codex_argv(profile, admission, json.loads(request["instruction"]), preflight)
                adapter.allowed_commands = [tuple(command)]
            if "{workforce_instruction}" in command:
                instruction = request.get("instruction")
                if not isinstance(instruction, str) or len(instruction) > 20000:
                    raise PermissionError("bounded Director instruction required")
                manifest = json.loads(instruction)
                if manifest.get("project_id") != p["id"] or manifest.get("executor") != profile.get("executor"):
                    raise PermissionError("instruction scope mismatch")
                command = [instruction if arg == "{workforce_instruction}" else arg for arg in command]
                adapter.allowed_commands = [tuple(command)]
            timeout = float(request.get("timeout", 300))
            if not math.isfinite(timeout):
                raise ValueError("invalid timeout")
            result = adapter.submit(auth, project_id=p["id"], workspace=p["workspace"],
                approval_ref=request.get("approval_ref"), command=command,
                timeout=min(max(timeout, 1), 3600),
                idempotency_key=request["idempotency_key"])
        elif action == "runtime":
            native_approval = request.get("native_approval")
            if not isinstance(native_approval, dict) or native_approval.get("approved") is not True:
                raise PermissionError("native runtime approval is required")
            profile = profiles.get(request.get("profile"))
            if not isinstance(profile, dict) or profile.get("executor") != "local-ci" or profile.get("role") != "qa" or profile.get("command") != ["/usr/bin/true"] or profile.get("runtime_operation") not in {"browser_smoke", "private_browser_acceptance", "mariadb_synthetic"}:
                raise PermissionError("fixed Local CI runtime profile required")
            if not isinstance(request.get("idempotency_key"), str) or not request["idempotency_key"].isascii() or len(request["idempotency_key"]) < 8 or len(request["idempotency_key"]) > 64:
                raise ValueError("bounded runtime job id required")
            request["profile_config"] = profile
            admission = verify_bridge_admission(request)
            result = execute_runtime_profile(request, admission, state_root, native_approval=native_approval)
        elif action == "status":
            result = adapter.status(auth, project_id=p["id"], workspace=p["workspace"], job_id=request["job_id"])
        elif action == "logs":
            result = {"logs": adapter.logs(auth, project_id=p["id"], workspace=p["workspace"], job_id=request["job_id"])}
        elif action == "result":
            result = adapter.result(auth, project_id=p["id"], workspace=p["workspace"], job_id=request["job_id"])
        elif action == "cancel":
            result = adapter.cancel(auth, project_id=p["id"], workspace=p["workspace"], job_id=request["job_id"])
        else:
            raise ValueError("unsupported worker action")
        print(json.dumps(result))
        return 0
    finally:
        adapter.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Return a generic error: do not copy command arguments or private paths into API output.
        response = {"error": type(exc).__name__, "message": "worker operation rejected" if isinstance(exc, (PermissionError, ValueError, KeyError)) else "worker operation failed"}
        if isinstance(exc, CapabilityPreflightError):
            response["preflight"] = exc.preflight
        if isinstance(exc, NameError) and isinstance(exc.name, str) and exc.name.isidentifier():
            response["diagnostic_code"] = "UNDEFINED_SYMBOL:" + exc.name
        print(json.dumps(response))
        raise SystemExit(1)
