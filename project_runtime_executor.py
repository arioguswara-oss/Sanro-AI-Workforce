"""Project-scoped, fixed-operation runtime wrapper for reviewed Hermes/Local CI profiles.

The host supplies a private policy file built from its verified registry, mandate,
and native approval state. This module accepts no shell command or arbitrary argv.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone


OPERATIONS = {
    "browser_smoke": ("browser_runtime", "runtime:browser", "apps/web/scripts/gdi02r-browser-acceptance.mjs"),
    "private_browser_acceptance": ("private_browser_runtime", "runtime:browser", "apps/web/scripts/private-browser-mcp-acceptance.mjs"),
    "mariadb_synthetic": ("mariadb_runtime", "runtime:mariadb", "isolated_mariadb_executor.py"),
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
MAX_TIMEOUT_SECONDS = 300


class RuntimeAdmissionError(PermissionError):
    pass


def _git(workspace: pathlib.Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(workspace), *args], check=True, capture_output=True,
        text=True, timeout=5,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1"},
    )
    return result.stdout.strip()


def _safe_private_file(value: str) -> pathlib.Path:
    path = pathlib.Path(value)
    if not path.is_absolute() or path.is_symlink():
        raise RuntimeAdmissionError("private policy file must be a canonical absolute file")
    resolved = path.resolve(strict=True)
    info = resolved.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeAdmissionError("private policy file ownership or mode is unsafe")
    return resolved


def _validate_policy(policy: dict, request: dict, now: datetime | None = None) -> tuple[dict, dict, pathlib.Path, str]:
    required = {"version", "project_id", "job_id", "worker_id", "workspace", "repository", "branch", "source_sha", "checkpoint_sha", "operation", "required_capabilities", "mandate_id", "subject", "approval_ref", "native_approval_sha256", "timeout_seconds", "arguments"}
    if not isinstance(request, dict) or set(request) != required or request.get("version") != 1:
        raise RuntimeAdmissionError("runtime request schema is invalid")
    for key in ("project_id", "job_id", "worker_id", "mandate_id", "subject", "approval_ref"):
        if not isinstance(request[key], str) or not ID_RE.fullmatch(request[key]):
            raise RuntimeAdmissionError(f"invalid {key}")
    if request["operation"] not in OPERATIONS or request["arguments"] != {}:
        raise RuntimeAdmissionError("runtime operation or arguments are not allowlisted")
    if request["operation"] == "private_browser_acceptance" and request["project_id"] != "sanro-ai-workforce":
        raise RuntimeAdmissionError("private browser controller is restricted to the authorized Workforce project")
    capability, action, _ = OPERATIONS[request["operation"]]
    if request["required_capabilities"] != [capability]:
        raise RuntimeAdmissionError("runtime capability requirement mismatch")
    timeout = request["timeout_seconds"]
    if type(timeout) is not int or not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise RuntimeAdmissionError("timeout must be an integer within the runtime bound")
    if not SHA_RE.fullmatch(request["source_sha"]) or request["checkpoint_sha"] != request["source_sha"]:
        raise RuntimeAdmissionError("source checkpoint mismatch")
    if not SHA256_RE.fullmatch(request["native_approval_sha256"]):
        raise RuntimeAdmissionError("verified native approval evidence is required")

    workspace_text = request["workspace"]
    workspace = pathlib.Path(workspace_text)
    if not workspace.is_absolute() or ".." in workspace.parts or workspace.is_symlink():
        raise RuntimeAdmissionError("canonical workspace is required")
    workspace = workspace.resolve(strict=True)
    if str(workspace) != workspace_text or not workspace.is_dir():
        raise RuntimeAdmissionError("workspace path is not canonical")
    for parent in (workspace, *workspace.parents):
        if parent.is_symlink():
            raise RuntimeAdmissionError("workspace path contains a symlink")

    projects = policy.get("projects") if isinstance(policy, dict) else None
    project = projects.get(request["project_id"]) if isinstance(projects, dict) else None
    if not isinstance(project, dict) or any(project.get(key) != request.get(key) for key in ("workspace", "repository", "branch", "worker_id")):
        raise RuntimeAdmissionError("project registry identity does not match")
    if policy.get("version") != 1 or project.get("status") != "AUTHORIZED":
        raise RuntimeAdmissionError("project policy is not authorized")

    mandates = policy.get("mandates")
    mandate = mandates.get(request["mandate_id"]) if isinstance(mandates, dict) else None
    current = now or datetime.now(timezone.utc)
    if not isinstance(mandate, dict):
        raise RuntimeAdmissionError("authorized mandate is unavailable")
    try:
        expires = datetime.fromisoformat(mandate["expires_at"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        raise RuntimeAdmissionError("mandate expiration is invalid") from exc
    if expires.tzinfo is None or expires <= current:
        raise RuntimeAdmissionError("mandate is expired")
    mandate_fields = {
        "status": "APPROVED", "project_id": request["project_id"],
        "repository": request["repository"], "branch": request["branch"],
        "workspace": str(workspace), "subject": request["subject"],
    }
    if any(mandate.get(key) != value for key, value in mandate_fields.items()):
        raise RuntimeAdmissionError("mandate identity does not match")
    if request["approval_ref"] not in mandate.get("approval_refs", []):
        raise RuntimeAdmissionError("native approval reference is not bound to the mandate")
    if action not in mandate.get("allowed_actions", []) or action in mandate.get("forbidden_actions", []):
        raise RuntimeAdmissionError("runtime operation is not authorized by the mandate")
    if mandate.get("max_cost_usd") != 0 or mandate.get("environment") != "isolated-development":
        raise RuntimeAdmissionError("runtime mandate exceeds the development-only boundary")

    if _git(workspace, "branch", "--show-current") != request["branch"]:
        raise RuntimeAdmissionError("authorized branch mismatch")
    remote = _git(workspace, "config", "--get", "remote.origin.url").removesuffix(".git")
    allowed_remote = {f"https://github.com/{request['repository']}", f"git@github.com:{request['repository']}"}
    if remote not in allowed_remote or _git(workspace, "rev-parse", "HEAD") != request["source_sha"]:
        raise RuntimeAdmissionError("repository identity or source SHA mismatch")
    if _git(workspace, "status", "--porcelain", "--untracked-files=all"):
        raise RuntimeAdmissionError("workspace must be clean before runtime acceptance")

    state_root_value = project.get("state_root")
    if not isinstance(state_root_value, str) or not os.path.isabs(state_root_value):
        raise RuntimeAdmissionError("project runtime state root is not configured")
    state_root = pathlib.Path(state_root_value)
    state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    resolved_state = state_root.resolve(strict=True)
    if state_root.is_symlink() or str(resolved_state) != state_root_value or resolved_state == workspace or workspace in resolved_state.parents:
        raise RuntimeAdmissionError("runtime state must be outside the workspace")
    if any(parent.is_symlink() for parent in (resolved_state, *resolved_state.parents)):
        raise RuntimeAdmissionError("runtime state path cannot contain a symlink")
    state_root = resolved_state
    info = state_root.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeAdmissionError("runtime state root ownership or mode is unsafe")
    return project, mandate, state_root, action


def _atomic_json(path: pathlib.Path, value: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".checkpoint-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _argv(workspace: pathlib.Path, operation: str) -> list[str]:
    if operation not in OPERATIONS:
        raise RuntimeAdmissionError("runtime operation is not allowlisted")
    _, _, relative = OPERATIONS[operation]
    target = workspace / relative
    if not target.is_file() or target.is_symlink() or workspace not in target.resolve().parents:
        raise RuntimeAdmissionError("allowlisted runtime entrypoint is unavailable")
    if operation in {"browser_smoke", "private_browser_acceptance"}:
        executable = shutil.which("node", path="/usr/bin:/bin")
        if not executable:
            raise RuntimeAdmissionError("Node.js runtime is unavailable")
        return [executable, str(target)]
    return [sys.executable, str(target)]


def _run_bounded(argv: list[str], workspace: pathlib.Path, timeout: int, operation: str,
                 state_root: pathlib.Path | None = None, job_id: str | None = None) -> tuple[int, str, bool]:
    if operation == "private_browser_acceptance":
        from private_browser_controller import run_private_browser
        if state_root is None or job_id is None:
            raise RuntimeAdmissionError("private browser state and admitted job identity are required")
        return run_private_browser(argv, workspace, state_root, job_id, timeout)
    job_tmp = pathlib.Path(tempfile.mkdtemp(prefix=".workforce-runtime-job-", dir=workspace))
    env = {"PATH": "/usr/bin:/bin:/usr/sbin", "LANG": "C.UTF-8", "HOME": str(job_tmp), "TMPDIR": str(job_tmp), "PYTHONNOUSERSITE": "1"}
    if operation == "browser_smoke":
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(workspace / "apps/web/.cache/playwright")
    try:
        from worker import apply_job_sandbox
        process = subprocess.Popen(argv, cwd=workspace, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   close_fds=True, start_new_session=True, text=True,
                                   preexec_fn=lambda: apply_job_sandbox(str(workspace), str(job_tmp)))
        try:
            output, _ = process.communicate(timeout=timeout)
            return process.returncode, output[-12000:], False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                output, _ = process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                output, _ = process.communicate(timeout=2)
            return process.returncode, output[-12000:], True
    finally:
        shutil.rmtree(job_tmp, ignore_errors=True)


def _parse_runtime_evidence(operation: str, output: str, workspace: pathlib.Path,
                            artifact_root: pathlib.Path | None = None) -> dict | None:
    event = None
    for line in output.splitlines()[-20:]:
        try:
            candidate = json.loads(line)
            if isinstance(candidate, dict) and candidate.get("status") in {"PASS", "BLOCKED"}:
                event = candidate
        except (json.JSONDecodeError, TypeError):
            continue
    if not isinstance(event, dict) or event.get("status") != "PASS":
        return None
    if operation == "browser_smoke":
        screenshot = event.get("screenshot")
        expected = "apps/web/.cache/playwright/GDI02R_CHROMIUM_SMOKE.png"
        path = workspace / expected
        if event.get("result") != "DOM_OK:42" or not isinstance(event.get("browserVersion"), str) or screenshot != expected or not path.is_file():
            return None
        try:
            canonical = path.resolve(strict=True)
            if canonical != path or workspace not in canonical.parents or any(parent.is_symlink() for parent in (path, *path.parents) if parent != workspace):
                return None
        except OSError:
            return None
        return {"browser_version": event["browserVersion"], "dom_result": event["result"], "screenshot": expected}
    if operation == "private_browser_acceptance":
        required_steps = {"initialize", "tools/list", "navigate", "snapshot", "fill", "click", "evaluate", "screenshot", "close"}
        limits = event.get("enforcedLimits")
        measured = event.get("measured")
        if (event.get("javascriptState") != "DOM_OK:MCP_OK:42"
                or not isinstance(event.get("browserVersion"), str)
                or not isinstance(event.get("mcpVersion"), str)
                or event.get("mcpVersion") != "0.0.86"
                or type(event.get("uid")) is not int or event["uid"] == 0
                or event.get("chromiumSandboxConfigured") is not True
                or event.get("chromiumNoSandboxArgumentObserved") is not False
                or not required_steps.issubset(set(event.get("steps", [])))
                or event.get("networkIsolation") != "private-network-namespace"
                or event.get("unauthorizedEgressBlocked") is not True
                or not isinstance(limits, dict)
                or type(limits.get("memoryMaxBytes")) is not int
                or type(limits.get("cpuQuotaCores")) not in {int, float}
                or type(limits.get("pidsMax")) is not int
                or not 0 < limits.get("memoryMaxBytes", 0) <= 2 * 1024 ** 3
                or not 0 < limits.get("cpuQuotaCores", 0) <= 1
                or not 0 < limits.get("pidsMax", 0) <= 128
                or not isinstance(measured, dict)
                or type(measured.get("peakProcessTreeRssBytes")) is not int
                or type(measured.get("peakProcessCount")) is not int
                or type(measured.get("processTreeCpuTicks")) is not int
                or not 0 < measured.get("peakProcessTreeRssBytes", 0)
                or not 0 < measured.get("peakProcessCount", 0)
                or measured.get("processTreeCpuTicks", -1) < 0
                or event.get("cleanup") != "PASS"
                or not isinstance(event.get("screenshotSha256"), str)
                or not SHA256_RE.fullmatch(event["screenshotSha256"])):
            return None
        screenshot = event.get("screenshot")
        if artifact_root is None or not isinstance(screenshot, str):
            return None
        try:
            candidate = pathlib.Path(screenshot)
            canonical = candidate.resolve(strict=True)
            root = artifact_root.resolve(strict=True)
            if not candidate.is_absolute() or canonical != candidate or root not in canonical.parents or not canonical.is_file():
                return None
            digest = hashlib.sha256(canonical.read_bytes()).hexdigest()
            if digest != event["screenshotSha256"]:
                return None
        except OSError:
            return None
        return {"browser_version": event["browserVersion"], "mcp_version": event["mcpVersion"],
                "javascript_state": event["javascriptState"], "screenshot_sha256": event["screenshotSha256"],
                "network_isolation": event["networkIsolation"], "unauthorized_egress_blocked": True,
                "enforced_limits": limits, "measured": measured}
    if operation == "mariadb_synthetic":
        if event.get("network_disabled") is not True or event.get("synthetic_rows_verified") != 2 or not isinstance(event.get("server_version"), str):
            return None
        return {"server_version": event["server_version"], "network_disabled": True, "synthetic_rows_verified": 2}
    return None


def _reported_blocked(output: str) -> bool:
    for line in output.splitlines()[-20:]:
        try:
            event = json.loads(line)
            if isinstance(event, dict) and event.get("status") == "BLOCKED":
                return True
        except (json.JSONDecodeError, TypeError):
            continue
    return False


def execute(request: dict, policy: dict) -> dict:
    project, mandate, state_root, action = _validate_policy(policy, request)
    workspace = pathlib.Path(request["workspace"])
    jobs_dir, audit_dir = state_root / "jobs", state_root / "audit"
    jobs_dir.mkdir(mode=0o700, exist_ok=True)
    audit_dir.mkdir(mode=0o700, exist_ok=True)
    for private_dir in (jobs_dir, audit_dir):
        info = private_dir.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise RuntimeAdmissionError("runtime checkpoint or audit directory is unsafe")
    job_path = jobs_dir / f"{request['job_id']}.json"
    lock_path = jobs_dir / f"{request['job_id']}.lock"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    except FileExistsError as exc:
        raise RuntimeAdmissionError("duplicate or concurrent runtime job rejected") from exc
    worktree_lock_fd = None
    try:
        if job_path.exists():
            raise RuntimeAdmissionError("job already has a checkpoint; silent replay rejected")
        now = datetime.now(timezone.utc).isoformat()
        checkpoint = {
            "version": 1, "project_id": request["project_id"], "job_id": request["job_id"],
            "worker_id": request["worker_id"], "mandate_id": request["mandate_id"],
            "branch": request["branch"], "source_sha": request["source_sha"],
            "checkpoint_sha": request["checkpoint_sha"], "operation": request["operation"],
            "required_capabilities": request["required_capabilities"], "stage": "ADMITTED",
            "started_at": now, "mandate_expires_at": mandate["expires_at"],
            "approval_ref_sha256": hashlib.sha256(request["approval_ref"].encode()).hexdigest(),
            "native_approval_sha256": request["native_approval_sha256"],
            "evidence": [], "resume_eligible": False,
        }
        _atomic_json(job_path, checkpoint)
        _audit(audit_dir, {"event": "admitted", "project_id": request["project_id"], "worker_id": request["worker_id"], "job_id": request["job_id"], "mandate_id": request["mandate_id"], "native_approval_sha256": request["native_approval_sha256"], "operation": request["operation"], "source_sha": request["source_sha"], "timestamp": now})
        try:
            from worker import acquire_worktree_lock
            worktree_lock_fd = acquire_worktree_lock(state_root, workspace)
        except Exception as error:
            if request["operation"] == "private_browser_acceptance":
                shutil.rmtree(state_root / "jobs" / request["job_id"], ignore_errors=True)
            finished = datetime.now(timezone.utc).isoformat()
            checkpoint.update({"stage": "BLOCKED", "finished_at": finished, "result": "BLOCKED",
                               "error_type": type(error).__name__, "resume_eligible": False})
            _atomic_json(job_path, checkpoint)
            _audit(audit_dir, {"event": "blocked", "project_id": request["project_id"], "worker_id": request["worker_id"], "job_id": request["job_id"], "error_type": type(error).__name__, "timestamp": finished})
            return {"status": "BLOCKED", "project_id": request["project_id"], "job_id": request["job_id"], "checkpoint_sha256": hashlib.sha256(job_path.read_bytes()).hexdigest()}
        checkpoint["stage"] = "RUNNING"
        _atomic_json(job_path, checkpoint)
        try:
            code, output, timed_out = _run_bounded(_argv(workspace, request["operation"]), workspace,
                request["timeout_seconds"], request["operation"], state_root, request["job_id"])
        except Exception as error:
            if request["operation"] == "private_browser_acceptance":
                shutil.rmtree(state_root / "jobs" / request["job_id"], ignore_errors=True)
            finished = datetime.now(timezone.utc).isoformat()
            checkpoint.update({"stage": "BLOCKED", "finished_at": finished, "result": "BLOCKED",
                               "error_type": type(error).__name__, "resume_eligible": False})
            _atomic_json(job_path, checkpoint)
            _audit(audit_dir, {"event": "blocked", "project_id": request["project_id"], "job_id": request["job_id"], "error_type": type(error).__name__, "timestamp": finished})
            checkpoint_sha256 = hashlib.sha256(job_path.read_bytes()).hexdigest()
            return {"status": "BLOCKED", "project_id": request["project_id"], "job_id": request["job_id"], "checkpoint_sha256": checkpoint_sha256}
        artifact_root = state_root / "jobs" / request["job_id"] / "artifacts"
        if code == 0 and not timed_out:
            runtime_evidence = _parse_runtime_evidence(request["operation"], output, workspace,
                artifact_root if request["operation"] == "private_browser_acceptance" else None)
        else:
            runtime_evidence = None
        status = "BLOCKED" if timed_out or _reported_blocked(output) else "PASS" if code == 0 and runtime_evidence else "FAIL"
        if request["operation"] == "private_browser_acceptance" and status != "PASS":
            shutil.rmtree(artifact_root, ignore_errors=True)
        checkpoint.update({"stage": "COMPLETED" if code == 0 and not timed_out else "BLOCKED" if timed_out else "FAILED",
                           "finished_at": datetime.now(timezone.utc).isoformat(), "exit_code": code,
                           "result": status, "output": _redact_output(output),
                           "evidence": [{"kind": request["operation"], "verified": bool(runtime_evidence), **(runtime_evidence or {}), "exit_code": code, "timed_out": timed_out}],
                           "resume_eligible": False})
        _atomic_json(job_path, checkpoint)
        _audit(audit_dir, {"event": "finished", "project_id": request["project_id"], "worker_id": request["worker_id"], "job_id": request["job_id"], "mandate_id": request["mandate_id"], "result": status, "exit_code": code, "timestamp": checkpoint["finished_at"]})
        checkpoint_sha256 = hashlib.sha256(job_path.read_bytes()).hexdigest()
        return {"status": status, "project_id": request["project_id"], "job_id": request["job_id"], "checkpoint_sha256": checkpoint_sha256, "exit_code": code}
    finally:
        if worktree_lock_fd is not None:
            import fcntl
            fcntl.flock(worktree_lock_fd, fcntl.LOCK_UN)
            os.close(worktree_lock_fd)
        os.close(lock_fd)
        os.unlink(lock_path)


def _redact_output(value: str) -> str:
    import re
    value = re.sub(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", value)
    value = re.sub(r"\b(?:sk|gh[pousr]_[A-Za-z0-9]{8,})[A-Za-z0-9_-]*\b", "[REDACTED]", value)
    return value[-12000:]


def _audit(path: pathlib.Path, event: dict) -> None:
    target = path / f"{event['project_id']}.jsonl"
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(target, flags, 0o600)
    try:
        os.write(fd, (json.dumps(event, sort_keys=True) + "\n").encode())
        os.fsync(fd)
    finally:
        os.close(fd)


def main() -> int:
    try:
        policy_path = _safe_private_file(os.environ["WORKFORCE_RUNTIME_POLICY"])
        if len(sys.argv) != 4 or sys.argv[1] != "--operation" or sys.argv[2] not in OPERATIONS:
            raise RuntimeAdmissionError("fixed runtime operation arguments required")
        if len(sys.argv[3]) > 20000:
            raise RuntimeAdmissionError("bounded runtime request required")
        request = json.loads(sys.argv[3])
        if request.get("operation") != sys.argv[2]:
            raise RuntimeAdmissionError("runtime operation does not match its fixed profile")
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        result = execute(request, policy)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "PASS" else 1
    except Exception as error:
        # Never emit request data, paths, command arguments, or exception strings.
        print(json.dumps({"status": "BLOCKED", "error": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
