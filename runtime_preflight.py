"""Read-only, fail-closed capability preflight for project-scoped jobs."""
import os
import pathlib
import json
import shutil
import socket
import stat
import subprocess
from datetime import datetime, timezone
import tempfile


def _status(state, detail):
    return {"status": state, "detail": detail}


def _probe_unix_socket_bind():
    root = tempfile.mkdtemp(prefix=f"sanro-workforce-socket-probe-{os.getuid()}-")
    path = os.path.join(root, "probe.sock")
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        probe.bind(path)
        return _status("PASS", "temporary AF_UNIX bind succeeded; probe removed")
    except OSError as error:
        return _status("BLOCKED", "temporary AF_UNIX bind denied: " + error.__class__.__name__)
    finally:
        probe.close()
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        os.rmdir(root)


def collect_runtime_preflight(project, mandate, checkpoint_sha, environ=None, codex_executable=None):
    """Inspect local readiness without opening network sockets or starting services."""
    environ = os.environ if environ is None else environ
    result = {}
    workspace_value = project.get("workspace") if isinstance(project, dict) else None
    if not isinstance(workspace_value, str) or not os.path.isabs(workspace_value) or ".." in pathlib.Path(workspace_value).parts:
        workspace = None
        result["canonical_workspace"] = _status("BLOCKED", "absolute traversal-free workspace required")
    else:
        workspace = pathlib.Path(workspace_value)
        try:
            if any(p.is_symlink() for p in (workspace, *workspace.parents)) or workspace.resolve(strict=True) != workspace:
                raise ValueError
            result["canonical_workspace"] = _status("PASS", "canonical path verified")
        except (OSError, ValueError):
            workspace = None
            result["canonical_workspace"] = _status("BLOCKED", "workspace missing or contains symlink/non-canonical path")

    result["project_identity"] = _status("PASS", "registry project and repository required") if isinstance(project, dict) and all(isinstance(project.get(k), str) and project[k] for k in ("id", "repository", "branch", "worker_id")) else _status("BLOCKED", "project, repository, branch and worker identity required")
    try:
        expires = datetime.fromisoformat(mandate["expires_at"].replace("Z", "+00:00"))
        mandate_ok = (mandate.get("status") == "APPROVED" and mandate.get("project_id") == (project or {}).get("id") and mandate.get("branch") == (project or {}).get("branch") and expires.tzinfo is not None and expires > datetime.now(timezone.utc))
    except (AttributeError, KeyError, TypeError, ValueError):
        mandate_ok = False
    result["mandate"] = _status("PASS", "unexpired project/branch mandate verified") if mandate_ok else _status("BLOCKED", "valid unexpired project/branch mandate required")
    result["checkpoint"] = _status("PASS", "source checkpoint supplied") if isinstance(checkpoint_sha, str) and len(checkpoint_sha) == 40 and all(c in "0123456789abcdef" for c in checkpoint_sha.lower()) else _status("BLOCKED", "full source SHA required")

    if workspace:
        result["workspace_write"] = _status("PASS", "workspace directory is writable by current process") if os.access(workspace, os.W_OK) else _status("BLOCKED", "workspace is not writable by current process")
        try:
            git_dir = subprocess.run(["git", "-C", str(workspace), "rev-parse", "--absolute-git-dir"], check=True, capture_output=True, text=True, timeout=5, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1"}).stdout.strip()
            git_path = pathlib.Path(git_dir).resolve(strict=True)
            result["git_metadata"] = _status("PASS", "resolved Git metadata directory is writable") if os.access(git_path, os.W_OK) else _status("BLOCKED", "resolved Git metadata is not writable; no write probe attempted")
            branch = subprocess.run(["git", "-C", str(workspace), "branch", "--show-current"], check=True, capture_output=True, text=True, timeout=5, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1"}).stdout.strip()
            result["authorized_branch"] = _status("PASS", "current branch matches registry") if branch == project.get("branch") else _status("BLOCKED", "current branch does not match registry")
            head = subprocess.run(["git", "-C", str(workspace), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, timeout=5, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1"}).stdout.strip()
            remote = subprocess.run(["git", "-C", str(workspace), "config", "--get", "remote.origin.url"], check=True, capture_output=True, text=True, timeout=5, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1"}).stdout.strip().removesuffix(".git")
            expected_remotes = {f"https://github.com/{project.get('repository')}", f"git@github.com:{project.get('repository')}"}
            clean = not subprocess.run(["git", "-C", str(workspace), "status", "--porcelain", "--untracked-files=all"], check=True, capture_output=True, text=True, timeout=5, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1"}).stdout.strip()
            result["source_repository"] = _status("PASS", "remote identity, clean worktree and source SHA verified") if remote in expected_remotes and head == checkpoint_sha and clean else _status("BLOCKED", "repository identity, clean state or source SHA mismatch")
        except (OSError, subprocess.SubprocessError):
            result["git_metadata"] = _status("BLOCKED", "Git metadata could not be inspected")
            result["authorized_branch"] = _status("BLOCKED", "Git branch could not be verified")
            result["source_repository"] = _status("BLOCKED", "repository and source SHA could not be verified")
    else:
        result["workspace_write"] = result["git_metadata"] = result["authorized_branch"] = result["source_repository"] = _status("BLOCKED", "workspace validation failed")

    codex = shutil.which("codex", path=environ.get("PATH"))
    if isinstance(codex_executable, str) and os.path.isabs(codex_executable) and pathlib.Path(codex_executable).name == "codex":
        try:
            candidate = pathlib.Path(codex_executable)
            candidate.lstat()
            codex = str(candidate) if candidate.is_file() and not candidate.is_symlink() and os.access(candidate, os.X_OK) else None
        except OSError:
            codex = None
    result["codex_cli"] = _status("PASS", "Codex CLI executable found") if codex else _status("BLOCKED", "Codex CLI executable unavailable")
    agent_socket = environ.get("SSH_AUTH_SOCK")
    try:
        socket_stat = os.stat(agent_socket) if agent_socket else None
        socket_ok = bool(socket_stat and stat.S_ISSOCK(socket_stat.st_mode) and os.access(agent_socket, os.R_OK | os.W_OK))
    except OSError:
        socket_ok = False
    result["ssh_agent"] = _status("PRESENT_UNVERIFIED", "agent socket path exists; no key listing or connection attempted") if socket_ok else _status("BLOCKED", "SSH agent socket unavailable; no connection attempted")
    result["network"] = _status("UNVERIFIED", "configuration does not prove socket/egress capability; no network probe attempted")
    result["unix_socket"] = _probe_unix_socket_bind()
    result["approval_policy"] = _status("UNVERIFIED", "native approval decisions are controlled by runtime; approve-for-me is not approval-never")
    binaries = bool(shutil.which("mariadb", path=environ.get("PATH")) and shutil.which("mariadbd", path=environ.get("PATH")) and shutil.which("mariadb-install-db", path=environ.get("PATH")))
    result["mariadb"] = _status("BINARY_AVAILABLE_UNTESTED", "client/server/installer binaries found; no active database is inspected") if binaries else _status("BLOCKED", "MariaDB client/server/installer binary unavailable")
    result["mariadb_isolated"] = _status("UNVERIFIED", "isolated server acceptance must pass before capability use") if binaries and result["unix_socket"]["status"] == "PASS" else _status("BLOCKED", "isolated MariaDB requires an available AF_UNIX bind and verified server startup")
    browser = next((shutil.which(n, path=environ.get("PATH")) for n in ("chromium", "chromium-browser", "google-chrome") if shutil.which(n, path=environ.get("PATH"))), None)
    playwright_pkg = pathlib.Path(workspace, "apps/web/node_modules/playwright/package.json") if workspace else None
    playwright_version = None
    try:
        playwright_version = json.loads(playwright_pkg.read_text(encoding="utf-8")).get("version") if playwright_pkg and playwright_pkg.is_file() else None
    except (OSError, ValueError):
        pass
    browsers_root = pathlib.Path(environ["PLAYWRIGHT_BROWSERS_PATH"]) if environ.get("PLAYWRIGHT_BROWSERS_PATH") else (pathlib.Path(workspace, "apps/web/.cache/playwright") if workspace else None)
    if browsers_root and browsers_root.is_dir():
        browser = browser or next((str(candidate) for candidate in browsers_root.glob("chromium-*/chrome-linux64/chrome") if candidate.is_file()), None)
    result["playwright_chromium"] = _status("READY_BINARY_ONLY", "Playwright " + str(playwright_version) + " and Chromium binary found; launch is not implied") if playwright_version and browser else _status("BLOCKED", "project Playwright package or Chromium executable unavailable")
    result["browser_smoke"] = _status("UNVERIFIED", "browser must launch in the authorized sandbox and pass DOM/screenshot smoke")
    result["local_ci"] = _status("SCRIPT_AVAILABLE_UNTESTED", "repository scripts are discoverable, but no CI runner was invoked by preflight")
    result["git_delivery"] = _status("APPROVAL_REQUIRED", "Git metadata write and push require native project-scoped runtime approval") if result["git_metadata"]["status"] == "BLOCKED" else _status("UNVERIFIED", "commit/push require a verified job-level Git capability")
    result["ssh_staging"] = _status("BLOCKED", "SSH agent and verified project-specific staging target allowlist are both required")
    result["staging_target"] = _status("BLOCKED", "no project-specific staging target allowlist supplied")
    result["checkpoint_evidence"] = _status("AVAILABLE", "checkpoint SHA supplied") if result["checkpoint"]["status"] == "PASS" else _status("BLOCKED", "checkpoint evidence missing")
    return {"schema_version": 1, "project_id": (project or {}).get("id"), "capabilities": result,
            "blockers": [name for name, value in result.items() if value["status"] == "BLOCKED"]}


class CapabilityPreflightError(PermissionError):
    def __init__(self, preflight, missing):
        super().__init__("mandatory runtime capabilities unavailable: " + ",".join(sorted(missing)))
        self.preflight = preflight


def require_capabilities(preflight, names):
    """Reject a job before executor start when its declared capability gate fails."""
    caps = (preflight or {}).get("capabilities", {})
    missing = [name for name in names if caps.get(name, {}).get("status") not in ("PASS", "AVAILABLE", "READY_BINARY_ONLY", "BINARY_AVAILABLE_UNTESTED")]
    if missing:
        raise CapabilityPreflightError(preflight, missing)
