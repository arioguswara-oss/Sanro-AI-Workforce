#!/usr/bin/env python3
"""Small durable FIFO worker for the JD-04A prototype (stdlib only)."""
import argparse
import base64
import math
import datetime as dt
import fcntl
import hashlib
import json
import os
import pathlib
import re
import signal
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from landlock_sandbox import apply_landlock
from process_sandbox import apply_process_policy


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def apply_job_sandbox(workspace, job_tmp):
    apply_landlock(workspace, job_tmp)
    apply_process_policy()


def canonical_worktree(path):
    candidate = pathlib.Path(path).expanduser()
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("job cwd must be absolute and traversal-free")
    root = pathlib.Path(candidate.anchor)
    cursor = root
    for part in candidate.parts[1:]:
        cursor = cursor / part
        try:
            if cursor.is_symlink():
                raise ValueError("job cwd cannot contain symlinks")
        except OSError as error:
            raise ValueError("job cwd is unavailable") from error
    try:
        canonical = candidate.resolve(strict=True)
    except OSError as error:
        raise ValueError("job cwd is unavailable") from error
    if canonical != candidate or not canonical.is_dir():
        raise ValueError("job cwd must be a canonical directory")
    return str(canonical)


def acquire_worktree_lock(state_root, workspace):
    """Hold a per-workspace lock; Git workspaces share one metadata inode across UIDs."""
    canonical = str(pathlib.Path(workspace).resolve(strict=True))
    git_entry = pathlib.Path(canonical) / ".git"
    if git_entry.is_symlink():
        raise PermissionError("workspace Git metadata cannot be a symlink")
    if git_entry.is_dir():
        metadata_root = git_entry
    elif git_entry.is_file():
        marker = git_entry.read_text(encoding="utf-8").strip()
        if not marker.startswith("gitdir: ") or "\n" in marker:
            raise PermissionError("workspace Git metadata pointer is invalid")
        pointer = pathlib.Path(marker[8:])
        metadata_root = (pointer if pointer.is_absolute() else pathlib.Path(canonical) / pointer).resolve(strict=True)
        if not metadata_root.is_dir():
            raise PermissionError("workspace Git metadata directory is invalid")
    else:
        # Non-Git fixtures are supported for local worker unit tests only.
        metadata_root = pathlib.Path(tempfile.gettempdir()) / f"sanro-workforce-worktree-locks-{os.getuid()}"
        metadata_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_dir = metadata_root / "sanro-workforce-locks"
    lock_dir.mkdir(mode=0o700, exist_ok=True)
    info = lock_dir.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise PermissionError("worktree lock directory must be private and user-owned")
    lock_dir.chmod(0o700)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    path = lock_dir / (digest + ".lock")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        lock_info = os.fstat(fd)
        if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != os.getuid() or lock_info.st_mode & 0o077:
            raise PermissionError("worktree lock file must be private and user-owned")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("worktree is already locked") from error
        return fd
    except Exception:
        os.close(fd)
        raise


def release_worktree_lock(fd):
    if fd is not None:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def herdr_status(state):
    """Opt-in OSC 7501 status for a Herdr-managed supervisor terminal."""
    if os.environ.get("WORKFORCE_HERDR_STATUS") == "1":
        sys.stdout.write(f"\x1b]7501;state={state}:app=jack-worker\x1b\\")
        sys.stdout.flush()


def herdr_job_status(state, job_id):
    """Publish this FIFO job as a separate Herdr status record."""
    if os.environ.get("WORKFORCE_HERDR_STATUS") != "1":
        return
    if state not in {"idle", "working", "done", "error"} or not re.fullmatch(r"[a-f0-9]{32}", str(job_id)):
        return
    project_id = os.environ.get("WORKFORCE_HERDR_PROJECT_ID", "")
    worker_name = os.environ.get("WORKFORCE_HERDR_WORKER_NAME", "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", project_id):
        project_id = "unknown"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", worker_name):
        worker_name = "workforce-worker"
    title = base64.b64encode(f"project={project_id} worker={worker_name} job={job_id}".encode()).decode("ascii")
    sys.stdout.write(f"\x1b]7501;state={state}:id={job_id}:app=sanro-workforce:title={title}\x1b\\")
    sys.stdout.flush()


def herdr_console_event(state, job_id):
    """Write safe lifecycle text to Spaces alongside machine-readable OSC."""
    if os.environ.get("WORKFORCE_HERDR_STATUS") != "1":
        return
    project_id = os.environ.get("WORKFORCE_HERDR_PROJECT_ID", "unknown")
    worker_name = os.environ.get("WORKFORCE_HERDR_WORKER_NAME", "workforce-worker")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", project_id):
        project_id = "unknown"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", worker_name):
        worker_name = "workforce-worker"
    if re.fullmatch(r"[a-f0-9]{32}", str(job_id)):
        print(f"[SANRO] project={project_id} worker={worker_name} job={job_id} state={state}", flush=True)


def redact_text(value):
    value = re.sub(r"(?i)(\b(?:api[_-]?key|access[_-]?token|auth(?:orization)?|password|secret)\b\s*[:=]\s*)([^\s,;]+)", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "[REDACTED]", value)
    return re.sub(r"\b(?:sk|gh[pousr]_[A-Za-z0-9]{8,})[A-Za-z0-9_-]*\b", "[REDACTED]", value)


def codex_pause_reason(line):
    """Accept only structured, allowlisted Codex failure codes; never parse free text."""
    try:
        event = json.loads(line)
        if not isinstance(event, dict) or event.get("type") not in {"turn.failed", "error"}:
            return None
        error = event.get("error")
        if not isinstance(error, dict):
            return None
        code = error.get("code") or error.get("codexErrorInfo")
        return {
            "usage_limit_exceeded": "CODEX_QUOTA_EXHAUSTED",
            "quota_exhausted": "CODEX_QUOTA_EXHAUSTED",
            "temporary_network_failure": "TEMPORARY_NETWORK_FAILURE",
            "network_error": "TEMPORARY_NETWORK_FAILURE",
            "runtime_approval_pending": "RUNTIME_APPROVAL_PENDING",
            "approval_required": "RUNTIME_APPROVAL_PENDING",
        }.get(code)
    except (ValueError, TypeError):
        return None


class Queue:
    def __init__(self, root):
        self.root = pathlib.Path(os.path.abspath(pathlib.Path(root).expanduser()))
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root_stat = self.root.lstat()
        if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode) or root_stat.st_uid != os.getuid():
            raise PermissionError("worker state root must be a real directory owned by the current user")
        self.root.chmod(0o700)
        for subdir in (self.root / "logs", self.root / "tmp"):
            subdir.mkdir(exist_ok=True, mode=0o700)
            sub_stat = subdir.lstat()
            if stat.S_ISLNK(sub_stat.st_mode) or not stat.S_ISDIR(sub_stat.st_mode) or sub_stat.st_uid != os.getuid():
                raise PermissionError(f"worker state subdirectory must be private and user-owned: {subdir.name}")
            subdir.chmod(0o700)
        self.db = self.root / "jobs.sqlite3"
        if self.db.exists() or self.db.is_symlink():
            info = self.db.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise PermissionError("worker database must be a private regular file")
        fd = os.open(self.db, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        self.conn = sqlite3.connect(self.db, timeout=30, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY, command TEXT NOT NULL, cwd TEXT NOT NULL,
          timeout REAL NOT NULL, dedupe_key TEXT UNIQUE, state TEXT NOT NULL,
          created TEXT NOT NULL, started TEXT, finished TEXT, exit_code INTEGER,
          error TEXT, log_path TEXT NOT NULL, failure_reason TEXT)""")
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(jobs)")}
        if "failure_reason" not in columns:
            self.conn.execute("ALTER TABLE jobs ADD COLUMN failure_reason TEXT")
        self.conn.execute("CREATE INDEX IF NOT EXISTS jobs_fifo ON jobs(state, created)")

    def submit(self, command, cwd, timeout, dedupe_key):
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 86400:
            raise ValueError("timeout must be finite and between zero and 86400 seconds")
        cwd = canonical_worktree(cwd)
        job_id = uuid.uuid4().hex
        log = str((self.root / "logs" / (job_id + ".log")).resolve())
        try:
            self.conn.execute("INSERT INTO jobs(id,command,cwd,timeout,dedupe_key,state,created,started,finished,exit_code,error,log_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (job_id, json.dumps(command), cwd, timeout, dedupe_key, "queued", now(), None, None, None, None, log))
        except sqlite3.IntegrityError:
            if dedupe_key:
                row = self.conn.execute("SELECT id,command,cwd,timeout FROM jobs WHERE dedupe_key=?", (dedupe_key,)).fetchone()
                if row:
                    if row["command"] != json.dumps(command) or row["cwd"] != cwd or row["timeout"] != timeout:
                        raise ValueError("idempotency key content mismatch")
                    return row["id"], False
            raise
        return job_id, True

    def recover(self):
        # The worker owns the singleton lock, so a remaining running row means its process died.
        rows = self.conn.execute("SELECT id,log_path FROM jobs WHERE state='running'").fetchall()
        for row in rows:
            with open(row["log_path"], "ab") as log:
                log.write((f"[{now()}] checkpoint recovery: marked interrupted; automatic replay disabled\n").encode())
        self.conn.execute("UPDATE jobs SET state='interrupted', finished=?, error='worker stopped before completion; manual review required' WHERE state='running'", (now(),))
        return [row["id"] for row in rows]

    def status(self, job_id=None):
        q = "SELECT * FROM jobs" + (" WHERE id=?" if job_id else "") + " ORDER BY created,id"
        rows = self.conn.execute(q, (job_id,) if job_id else ()).fetchall()
        return [dict(r) | {"command": json.loads(r["command"])} for r in rows]

    def cancel(self, job_id):
        cur = self.conn.execute("UPDATE jobs SET state='cancelled',finished=?,error='cancelled before execution' WHERE id=? AND state='queued'", (now(), job_id))
        if cur.rowcount == 1:
            return True
        cur = self.conn.execute("UPDATE jobs SET state='cancel_requested' WHERE id=? AND state='running'", (job_id,))
        return cur.rowcount == 1

    def close(self):
        self.conn.close()


def worker_loop(q, idle_exit=False):
    lock_path = q.root / "worker.lock"
    lock_file = open(lock_path, "a+")
    try:
        import fcntl
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (ImportError, BlockingIOError):
        print("worker already running", file=sys.stderr)
        return 2
    for recovered_job_id in q.recover():
        herdr_job_status("error", recovered_job_id)
    herdr_status("idle")
    current_status = "idle"
    def set_status(value):
        nonlocal current_status
        if current_status != value:
            current_status = value
            herdr_status(value)
    interrupted = False
    def stop(_sig, _frame):
        nonlocal interrupted
        interrupted = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not interrupted:
        q.conn.execute("BEGIN IMMEDIATE")
        row = q.conn.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY rowid LIMIT 1").fetchone()
        if row:
            q.conn.execute("UPDATE jobs SET state='running',started=?,error=NULL WHERE id=? AND state='queued'", (now(), row["id"]))
        q.conn.execute("COMMIT")
        if not row:
            if idle_exit:
                break
            set_status("idle")
            time.sleep(.1)
            continue
        set_status("working")
        herdr_job_status("working", row["id"])
        herdr_console_event("running", row["id"])
        command = json.loads(row["command"])
        started = time.monotonic()
        code, state, error, failure_reason = None, "succeeded", None, None
        with open(row["log_path"], "ab", buffering=0) as log:
            codex_executor = pathlib.Path(command[0]).name == "codex" and len(command) > 1 and command[1] == "exec"
            log.write((f"[{now()}] start executor=codex output=suppressed\n" if codex_executor else f"[{now()}] start {redact_text(json.dumps(command))}\n").encode())
            proc, output_thread = None, None
            job_tmp = tempfile.mkdtemp(prefix=".jd04-job-", dir=row["cwd"])
            worktree_lock_fd = None
            try:
                worktree_lock_fd = acquire_worktree_lock(q.root, row["cwd"])
                env = {"PATH": os.defpath, "HOME": row["cwd"], "TMPDIR": job_tmp, "LANG": "C.UTF-8", "PYTHONNOUSERSITE": "1"}
                proc = subprocess.Popen(command, cwd=row["cwd"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True,
                    preexec_fn=lambda: apply_job_sandbox(row["cwd"], job_tmp))
                def copy_output():
                    nonlocal failure_reason
                    for line in iter(proc.stdout.readline, b""):
                        decoded = line.decode("utf-8", errors="replace")
                        if codex_executor:
                            failure_reason = codex_pause_reason(decoded) or failure_reason
                        else:
                            log.write(redact_text(decoded).encode())
                    proc.stdout.close()
                output_thread = threading.Thread(target=copy_output, daemon=True)
                output_thread.start()
                while proc.poll() is None:
                    current = q.conn.execute("SELECT state FROM jobs WHERE id=?", (row["id"],)).fetchone()
                    if current["state"] == "cancel_requested" or interrupted:
                        state = "cancelled" if current["state"] == "cancel_requested" else "interrupted"
                        error = "cancelled while running" if state == "cancelled" else "worker shutdown before completion"
                        os.killpg(proc.pid, signal.SIGTERM)
                        try: code = proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            os.killpg(proc.pid, signal.SIGKILL); code = proc.wait()
                        break
                    remaining = row["timeout"] - (time.monotonic() - started)
                    if remaining <= 0:
                        state, error = "timed_out", f"exceeded {row['timeout']} seconds"
                        os.killpg(proc.pid, signal.SIGTERM)
                        try: code = proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            os.killpg(proc.pid, signal.SIGKILL); code = proc.wait()
                        break
                    try: code = proc.wait(timeout=min(.1, remaining))
                    except subprocess.TimeoutExpired: pass
                # A very short child may exit between Popen() and the first loop
                # iteration; capture its return code even when wait() was skipped.
                if code is None and proc is not None and proc.poll() is not None:
                    code = proc.returncode
                if state == "succeeded" and code != 0:
                    if codex_executor and failure_reason:
                        state, error = "paused", "external executor requires authorized recovery"
                    else:
                        state, error = "failed", f"exit code {code}"
            except Exception as e:
                state, error, failure_reason = "failed", redact_text(str(e)), None
                if proc is not None and proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL); proc.wait()
            if output_thread is not None:
                output_thread.join(timeout=2)
            shutil.rmtree(job_tmp, ignore_errors=True)
            release_worktree_lock(worktree_lock_fd)
            log.write((f"\n[{now()}] finish state={state} exit={code} elapsed={time.monotonic()-started:.3f}s\n").encode())
        q.conn.execute("UPDATE jobs SET state=?,finished=?,exit_code=?,error=?,failure_reason=? WHERE id=?", (state, now(), code, error, failure_reason, row["id"]))
        herdr_job_status("done" if state in ("succeeded", "cancelled") else "error", row["id"])
        herdr_console_event("completed" if state == "succeeded" else state, row["id"])
        set_status("done" if state in ("succeeded", "cancelled") else "error")
        # Optional JD-04 Hermes outbox: commit a minimal, deduplicated completion event
        # from the worker process without opening a gateway or platform transport.
        tables = q.conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='job_notifications'").fetchone()
        if tables:
            tables = q.conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='adapter_jobs'").fetchone()
            if tables:
                owner = q.conn.execute("SELECT project_id,workspace,subject FROM adapter_jobs WHERE job_id=?", (row["id"],)).fetchone()
                if owner:
                    event = {"succeeded": "COMPLETED", "failed": "FAILED", "timed_out": "FAILED",
                             "cancelled": "CANCELLED", "interrupted": "INTERRUPTED"}.get(state)
                    if event:
                        q.conn.execute("INSERT OR IGNORE INTO job_notifications VALUES (?,?,?,?,?,?,?,NULL)",
                            (row["id"], event, owner["project_id"], owner["workspace"], owner["subject"],
                             f"Engineering job {row['id']} {event.lower()}.", time.time()))
    lock_file.close()
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=".jd04-worker")
    sub = p.add_subparsers(dest="action", required=True)
    s = sub.add_parser("submit"); s.add_argument("--timeout", type=float, default=300); s.add_argument("--key"); s.add_argument("--cwd", default="."); s.add_argument("command", nargs=argparse.REMAINDER)
    sub.add_parser("run")
    sub.add_parser("status").add_argument("job_id", nargs="?")
    sub.add_parser("cancel").add_argument("job_id")
    sub.add_parser("serve").add_argument("--idle-exit", action="store_true")
    a = p.parse_args(); q = Queue(a.root)
    try:
        if a.action == "submit":
            command = a.command[1:] if a.command and a.command[0] == "--" else a.command
            if not command: p.error("submit requires a command after --")
            jid, created = q.submit(command, a.cwd, a.timeout, a.key)
            print(json.dumps({"job_id": jid, "created": created}))
        elif a.action == "status": print(json.dumps(q.status(a.job_id), indent=2))
        elif a.action == "cancel": print(json.dumps({"cancelled": q.cancel(a.job_id)}))
        else: return worker_loop(q, idle_exit=(a.action == "run" or a.idle_exit))
    finally:
        q.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
