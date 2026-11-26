"""Fixed systemd user-unit boundary for private synthetic Playwright MCP acceptance.

Authorization is completed by project_runtime_executor before this module is called.
The transient unit is the only supported launch path for this operation; no shell is used.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import time
import json


CPU_QUOTA = "100%"
MEMORY_MAX = "2G"
TASKS_MAX = "128"


def build_systemd_argv(systemd_run: str, argv: list[str], workspace: pathlib.Path,
                       job_root: pathlib.Path, job_id: str, timeout: int) -> list[str]:
    if not os.path.isabs(systemd_run) or not pathlib.Path(systemd_run).name == "systemd-run":
        raise ValueError("systemd-run executable must be absolute and fixed")
    expected_script = workspace / "apps/web/scripts/private-browser-mcp-acceptance.mjs"
    node_path = pathlib.Path(argv[0]) if argv else pathlib.Path("/")
    try:
        resolved_node = node_path.resolve(strict=True)
    except OSError:
        resolved_node = pathlib.Path("/")
    if (len(argv) != 2 or not node_path.is_absolute() or node_path.name != "node"
            or not resolved_node.is_file() or resolved_node.name not in {"node", "nodejs"}
            or pathlib.Path(argv[1]) != expected_script or not expected_script.is_file()
            or expected_script.is_symlink() or expected_script.resolve(strict=True) != expected_script):
        raise ValueError("only the fixed project Playwright acceptance entrypoint may run")
    if not (1 <= timeout <= 300) or not job_id.replace("-", "").replace("_", "").isalnum():
        raise ValueError("job timeout or identifier is invalid")
    unit_suffix = __import__("hashlib").sha256(job_id.encode()).hexdigest()[:16]
    properties = [
        "Type=exec", f"RuntimeMaxSec={timeout}s", "TimeoutStopSec=3s", "KillMode=control-group",
        f"CPUQuota={CPU_QUOTA}", f"MemoryMax={MEMORY_MAX}", f"TasksMax={TASKS_MAX}",
        "PrivateNetwork=yes", "PrivateTmp=yes", "NoNewPrivileges=yes", "ProtectSystem=strict",
        f"ReadWritePaths={job_root}",
    ]
    environment = {
        "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONNOUSERSITE": "1",
        "HOME": str(job_root), "TMPDIR": str(job_root / "tmp"),
        "PLAYWRIGHT_BROWSERS_PATH": str(workspace / "apps/web/.cache/playwright"),
        "SANRO_PROJECT_ID": "sanro-ai-workforce", "SANRO_JOB_ID": job_id,
        "SANRO_BROWSER_STATE_ROOT": str(job_root / "artifacts"),
        "SANRO_REQUIRE_PRIVATE_NETNS": "1",
    }
    result = [systemd_run, "--user", "--quiet", "--wait", "--pipe", "--collect",
              f"--unit=sanro-private-browser-{unit_suffix}"]
    for prop in properties:
        result.append(f"--property={prop}")
    # systemd user managers may hold unrelated environment values. `env -i`
    # creates a clean browser process environment; no shell or arbitrary command.
    result.extend(["--", "/usr/bin/env", "-i"])
    result.extend(f"{key}={value}" for key, value in environment.items())
    result.extend(argv)
    return result


def run_private_browser(argv: list[str], workspace: pathlib.Path, state_root: pathlib.Path,
                        job_id: str, timeout: int) -> tuple[int, str, bool]:
    """Execute through user systemd cgroups/network namespace and fail closed."""
    if os.getuid() == 0:
        raise PermissionError("private browser controller refuses root execution")
    systemd_run = shutil.which("systemd-run", path="/usr/bin:/bin")
    if not systemd_run:
        raise RuntimeError("systemd-run unavailable; private browser execution is blocked")
    job_root = state_root / "jobs" / job_id
    job_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    (job_root / "tmp").mkdir(mode=0o700)
    (job_root / "artifacts").mkdir(mode=0o700)
    command = build_systemd_argv(systemd_run, argv, workspace, job_root, job_id, timeout)
    started = time.monotonic()
    try:
        completed = subprocess.run(command, cwd=workspace, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, timeout=timeout + 12,
                                   check=False, close_fds=True)
        elapsed = time.monotonic() - started
        timed_out = completed.returncode == 124 or elapsed >= timeout
        output = completed.stdout[-12000:]
        has_status = False
        for line in output.splitlines()[-20:]:
            try:
                if json.loads(line).get("status") in {"PASS", "BLOCKED"}:
                    has_status = True
                    break
            except (json.JSONDecodeError, AttributeError):
                continue
        if completed.returncode != 0 and not has_status:
            output += '\n{"status":"BLOCKED","error":"systemd_private_unit_failed"}\n'
        return completed.returncode, output, timed_out
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "")
        if isinstance(output, bytes):
            output = output.decode("utf-8", "replace")
        output += '\n{"status":"BLOCKED","error":"hard_runtime_timeout"}\n'
        return 124, output[-12000:], True
    finally:
        shutil.rmtree(job_root / "tmp", ignore_errors=True)
