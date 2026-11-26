"""Build a native, project-scoped Codex CLI command for a validated Workforce job."""
import json
import os
import pathlib
import stat


def build_codex_argv(profile, admission, instruction):
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
    prompt = "SANRO authorized engineering job. Respect this JSON mandate and checkpoint; do not access other projects, merge, deploy, or use paid APIs.\n" + json.dumps({"admission": admission, "instruction": instruction}, ensure_ascii=False, separators=(",", ":"))
    return [str(executable), "exec", "--cd", admission["workspace"], "--sandbox", "workspace-write", "--approve-for-me", "--json", "--ephemeral", prompt]
