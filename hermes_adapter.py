"""Isolated, framework-neutral adapter contract for Hermes integration.

No Hermes API is assumed. A host integration must construct Authorization from
its own verified identity, project, workspace, scope, and approval records.
"""
from dataclasses import dataclass
import hashlib
import json
import os
import pathlib
import re
import signal
import subprocess
import sys
import time

from worker import Queue


STATUS = {
    "queued": "QUEUED", "running": "RUNNING", "succeeded": "COMPLETED",
    "failed": "FAILED", "timed_out": "FAILED", "cancelled": "CANCELLED",
    "cancel_requested": "RUNNING", "interrupted": "INTERRUPTED", "paused": "PAUSED",
}
SECRET_PATTERNS = [
    re.compile(r"(?i)(\b(?:api[_-]?key|access[_-]?token|auth(?:orization)?|password|secret)\b\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\b(?:sk|gh[pousr]_[A-Za-z0-9]{8,})[A-Za-z0-9_-]*\b"),
]


def redact(value):
    for pattern in SECRET_PATTERNS:
        if pattern.groups:
            value = pattern.sub(lambda m: m.group(1) + "[REDACTED]", value)
        else:
            value = pattern.sub("[REDACTED]", value)
    return value


@dataclass(frozen=True)
class Authorization:
    subject: str
    scopes: frozenset
    project_ids: frozenset
    workspaces: frozenset
    approval_refs: frozenset


class HermesAdapter:
    """Local adapter; policy allowlists are supplied by the integrating host."""
    def __init__(self, root, project_workspaces, allowed_commands):
        self.queue = Queue(root)
        self.db = self.queue.conn
        self.db.execute("""CREATE TABLE IF NOT EXISTS adapter_jobs (
            job_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace TEXT NOT NULL,
            scope TEXT NOT NULL, subject TEXT NOT NULL, approval_ref TEXT NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS job_notifications (
            job_id TEXT NOT NULL, event TEXT NOT NULL, project_id TEXT NOT NULL,
            workspace TEXT NOT NULL, subject TEXT NOT NULL, message TEXT NOT NULL,
            created REAL NOT NULL, delivered REAL, PRIMARY KEY(job_id, event))""")
        self.project_workspaces = {k: str(pathlib.Path(v).resolve()) for k, v in project_workspaces.items()}
        self.allowed_commands = [tuple(x) for x in allowed_commands]

    def close(self):
        self.queue.close()

    def _authorize(self, auth, project_id, workspace, scope, approval_ref=None):
        if not isinstance(auth, Authorization) or not auth.subject:
            raise PermissionError("verified authorization required")
        workspace = str(pathlib.Path(workspace).resolve())
        if scope not in auth.scopes or project_id not in auth.project_ids:
            raise PermissionError("missing scope or project authorization")
        if workspace not in auth.workspaces or self.project_workspaces.get(project_id) != workspace:
            raise PermissionError("workspace is not authorized for this project")
        if approval_ref is not None and approval_ref not in auth.approval_refs:
            raise PermissionError("approval reference is not authorized")
        return workspace

    def _allowed_command(self, command):
        if not isinstance(command, (list, tuple)) or not command or not all(isinstance(x, str) and x for x in command):
            raise ValueError("command must be a non-empty argv array")
        executable = pathlib.Path(command[0]).name
        if executable in {"sh", "bash", "dash", "zsh", "fish", "cmd", "powershell"}:
            raise PermissionError("shell commands are not permitted")
        if not any(tuple(command[:len(prefix)]) == prefix and executable == pathlib.Path(prefix[0]).name for prefix in self.allowed_commands):
            raise PermissionError("command is outside the configured allowlist")

    def submit(self, auth, *, project_id, workspace, scope="engineering:execute", approval_ref, command, timeout=3600, idempotency_key):
        workspace = self._authorize(auth, project_id, workspace, scope, approval_ref)
        self._allowed_command(command)
        if not idempotency_key or len(idempotency_key) > 200:
            raise ValueError("bounded idempotency_key required")
        key = hashlib.sha256("\0".join((project_id, workspace, scope, idempotency_key)).encode()).hexdigest()
        job_id, created = self.queue.submit(list(command), workspace, timeout, key)
        if created:
            self.db.execute("INSERT INTO adapter_jobs VALUES (?,?,?,?,?,?)", (job_id, project_id, workspace, scope, auth.subject, approval_ref))
        return {"job_id": job_id, "created": created, "status": "QUEUED" if created else self.status(auth, project_id=project_id, workspace=workspace, job_id=job_id, scope=scope)["status"]}

    def _owned(self, auth, project_id, workspace, job_id, scope):
        workspace = self._authorize(auth, project_id, workspace, scope)
        row = self.db.execute("SELECT * FROM adapter_jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None or row["project_id"] != project_id or row["workspace"] != workspace:
            raise PermissionError("job is unavailable in this authorization scope")
        if row["subject"] != auth.subject and "engineering:admin" not in auth.scopes:
            raise PermissionError("job belongs to another subject")
        return row

    def status(self, auth, *, project_id, workspace, job_id, scope="engineering:read"):
        self._owned(auth, project_id, workspace, job_id, scope)
        row = self.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return {"job_id": job_id, "status": STATUS.get(row["state"], "INTERRUPTED"), "created": row["created"], "started": row["started"], "finished": row["finished"], "exit_code": row["exit_code"], "error": redact(row["error"] or "") or None, "failure_reason": row["failure_reason"]}

    def logs(self, auth, *, project_id, workspace, job_id, scope="engineering:read"):
        owner = self._owned(auth, project_id, workspace, job_id, scope)
        path = pathlib.Path(self.db.execute("SELECT log_path FROM jobs WHERE id=?", (job_id,)).fetchone()["log_path"])
        try: data = path.read_text(errors="replace")
        except FileNotFoundError: data = ""
        clean = redact(data)
        if clean != data:
            path.write_text(clean)
        return clean

    def result(self, auth, *, project_id, workspace, job_id, scope="engineering:read"):
        status = self.status(auth, project_id=project_id, workspace=workspace, job_id=job_id, scope=scope)
        return {"job_id": job_id, "status": status["status"], "exit_code": status["exit_code"], "error": status["error"], "failure_reason": status["failure_reason"], "output": self.logs(auth, project_id=project_id, workspace=workspace, job_id=job_id, scope=scope)}

    def cancel(self, auth, *, project_id, workspace, job_id, scope="engineering:cancel"):
        self._owned(auth, project_id, workspace, job_id, scope)
        accepted = self.queue.cancel(job_id)
        self.collect_notifications()
        return {"job_id": job_id, "accepted": accepted}

    def collect_notifications(self):
        """Persist one minimal event per terminal job; safe to call repeatedly."""
        rows = self.db.execute("""SELECT j.id, j.state, a.project_id, a.workspace, a.subject
            FROM jobs j JOIN adapter_jobs a ON a.job_id=j.id
            WHERE j.state IN ('succeeded','failed','timed_out','cancelled','interrupted','paused')
            AND NOT EXISTS (SELECT 1 FROM job_notifications n WHERE n.job_id=j.id)""").fetchall()
        now = time.time()
        for row in rows:
            state = STATUS.get(row["state"], "INTERRUPTED")
            message = f"Engineering job {row['id']} {state.lower()}."
            self.db.execute("INSERT OR IGNORE INTO job_notifications VALUES (?,?,?,?,?,?,?,NULL)",
                (row["id"], state, row["project_id"], row["workspace"], row["subject"], message, now))
        return len(rows)

    def drain_notifications(self, auth, *, project_id, workspace, scope="engineering:read"):
        """At-most-once, session-bound pull delivery for hosts without a native push API."""
        workspace = self._authorize(auth, project_id, workspace, scope)
        self.collect_notifications()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            rows = self.db.execute("""SELECT job_id,event,message FROM job_notifications
                WHERE project_id=? AND workspace=? AND subject=? AND delivered IS NULL
                ORDER BY created,job_id""", (project_id, workspace, auth.subject)).fetchall()
            if rows:
                self.db.executemany("UPDATE job_notifications SET delivered=? WHERE job_id=? AND event=? AND delivered IS NULL",
                                    [(time.time(), r["job_id"], r["event"]) for r in rows])
            self.db.commit()
            return [{"job_id": r["job_id"], "event": r["event"], "message": r["message"]} for r in rows]
        except BaseException:
            self.db.rollback()
            raise


class WorkerSupervisor:
    """Explicit local-process supervisor; never registers a system service."""
    def __init__(self, root):
        self.root = pathlib.Path(root).resolve()
        self.process = None

    def start(self):
        if self.process is not None and self.process.poll() is None:
            return False
        worker = pathlib.Path(__file__).with_name("worker.py")
        # The queue supervisor needs no Hermes/provider credentials. Do not inherit
        # the Gateway environment; the worker also constructs a reduced child env.
        worker_env = {
            "PATH": os.defpath,
            "HOME": str(self.root),
            "TMPDIR": str(self.root / "tmp"),
            "LANG": "C.UTF-8",
            "PYTHONNOUSERSITE": "1",
        }
        self.process = subprocess.Popen(
            [sys.executable, str(worker), "--root", str(self.root), "serve"],
            env=worker_env, start_new_session=True, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True

    def shutdown(self, timeout=10):
        if self.process is None or self.process.poll() is not None:
            return True
        os.killpg(self.process.pid, signal.SIGTERM)
        try:
            self.process.wait(timeout=timeout)
            return True
        except subprocess.TimeoutExpired:
            os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait()
            return False

    def recover(self):
        lock_file = open(self.root / "worker.lock", "a+")
        try:
            import fcntl
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (ImportError, BlockingIOError) as exc:
            lock_file.close()
            raise RuntimeError("cannot recover while a worker owns the queue") from exc
        q = Queue(self.root)
        try:
            q.recover()
        finally:
            q.close()
            lock_file.close()
        return "INTERRUPTED jobs require explicit review and resubmission with a new idempotency key"
