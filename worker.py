#!/usr/bin/env python3
"""Small durable FIFO worker for the JD-04A prototype (stdlib only)."""
import argparse
import math
import datetime as dt
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


def herdr_status(state):
    """Opt-in OSC 7501 status for a Herdr-managed supervisor terminal."""
    if os.environ.get("WORKFORCE_HERDR_STATUS") == "1":
        sys.stdout.write(f"\x1b]7501;state={state}:app=jack-worker\x1b\\")
        sys.stdout.flush()


def redact_text(value):
    value = re.sub(r"(?i)(\b(?:api[_-]?key|access[_-]?token|auth(?:orization)?|password|secret)\b\s*[:=]\s*)([^\s,;]+)", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "[REDACTED]", value)
    return re.sub(r"\b(?:sk|gh[pousr]_[A-Za-z0-9]{8,})[A-Za-z0-9_-]*\b", "[REDACTED]", value)


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
          error TEXT, log_path TEXT NOT NULL)""")
        self.conn.execute("CREATE INDEX IF NOT EXISTS jobs_fifo ON jobs(state, created)")

    def submit(self, command, cwd, timeout, dedupe_key):
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 86400:
            raise ValueError("timeout must be finite and between zero and 86400 seconds")
        cwd = str(pathlib.Path(cwd).resolve())
        if not pathlib.Path(cwd).is_dir():
            raise ValueError("job cwd must be an existing directory")
        job_id = uuid.uuid4().hex
        log = str((self.root / "logs" / (job_id + ".log")).resolve())
        try:
            self.conn.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
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
    q.recover()
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
        command = json.loads(row["command"])
        started = time.monotonic()
        code, state, error = None, "succeeded", None
        with open(row["log_path"], "ab", buffering=0) as log:
            log.write((f"[{now()}] start {redact_text(json.dumps(command))}\n").encode())
            proc, output_thread = None, None
            job_tmp = tempfile.mkdtemp(prefix=".jd04-job-", dir=row["cwd"])
            try:
                env = {"PATH": os.defpath, "HOME": row["cwd"], "TMPDIR": job_tmp, "LANG": "C.UTF-8", "PYTHONNOUSERSITE": "1"}
                proc = subprocess.Popen(command, cwd=row["cwd"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True,
                    preexec_fn=lambda: apply_job_sandbox(row["cwd"], job_tmp))
                def copy_output():
                    for line in iter(proc.stdout.readline, b""):
                        log.write(redact_text(line.decode("utf-8", errors="replace")).encode())
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
                    state, error = "failed", f"exit code {code}"
            except Exception as e:
                state, error = "failed", redact_text(str(e))
                if proc is not None and proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL); proc.wait()
            if output_thread is not None:
                output_thread.join(timeout=2)
            shutil.rmtree(job_tmp, ignore_errors=True)
            log.write((f"\n[{now()}] finish state={state} exit={code} elapsed={time.monotonic()-started:.3f}s\n").encode())
        q.conn.execute("UPDATE jobs SET state=?,finished=?,exit_code=?,error=? WHERE id=?", (state, now(), code, error, row["id"]))
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
