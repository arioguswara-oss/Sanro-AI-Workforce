"""Build a native, project-scoped Codex CLI command for a validated Workforce job."""
import json
import os
import pathlib
import stat
from runtime_preflight import require_capabilities


def build_codex_argv(profile, admission, instruction, preflight=None):
    command = profile.get("command")
    if not isinstance(command, list) or len(command) != 1 or not isinstance(command[0], str):
        raise PermissionError("Codex profile must contain only the explicit Codex executable")
    executable = pathlib.Path(command[0])
    if not executable.is_absolute() or executable.name != "codex":
        raise PermissionError("Codex profile must use an absolute Codex executable path")
    try:
        info = executable.lstat()
    except OSError as error:
        raise PermissionError("Codex executable is unavailable") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or not os.access(executable, os.X_OK):
        raise PermissionError("Codex executable must be a regular executable file")
    required = ("project_id", "worker_id", "job_id", "workspace", "checkpoint_sha")
    if not isinstance(admission, dict) or any(not isinstance(admission.get(key), str) or not admission[key] for key in required):
        raise PermissionError("validated project, worker, job, workspace and checkpoint are required")
    if admission.get("permission_profile", {}).get("write_scope") != "project-worktree":
        raise PermissionError("unsupported project permission profile")
    if admission.get("permission_profile", {}).get("allow_network") is not False:
        raise PermissionError("Codex network access must remain disabled")
    if admission.get("required_capabilities") != ["engineering"]:
        raise PermissionError("Codex CLI may only receive explicitly admitted engineering jobs")
    if admission.get("required_capabilities") != ["engineering"]:
        raise PermissionError("Codex CLI may only receive explicitly admitted engineering jobs")
    required_capabilities = profile.get("runtime_requirements", ["project_identity", "canonical_workspace", "authorized_branch", "source_repository", "workspace_write", "git_metadata", "mandate", "checkpoint", "codex_cli"])
    allowed_capabilities = {"project_identity", "canonical_workspace", "authorized_branch", "source_repository", "workspace_write", "git_metadata", "mandate", "checkpoint", "codex_cli", "ssh_agent", "network", "unix_socket", "mariadb", "mariadb_isolated", "playwright_chromium", "browser_smoke", "local_ci", "git_delivery", "ssh_staging", "staging_target", "checkpoint_evidence"}
    if not isinstance(required_capabilities, list) or not all(name in allowed_capabilities for name in required_capabilities):
        raise PermissionError("unsupported runtime capability requirement")
    require_capabilities(preflight, required_capabilities)
    prompt = "SANRO authorized engineering job. Respect this JSON mandate and checkpoint; do not access other projects, merge, deploy, or use paid APIs.\n" + json.dumps({"admission": admission, "instruction": instruction}, ensure_ascii=False, separators=(",", ":"))
    return [str(executable), "exec", "--cd", admission["workspace"], "--sandbox", "workspace-write", "--approve-for-me", "--json", "--ephemeral", prompt]
