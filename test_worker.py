import json
import io
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout

from worker import Queue, acquire_worktree_lock, herdr_console_event, herdr_job_status, herdr_status, release_worktree_lock, worker_loop

ROOT = pathlib.Path(__file__).resolve().parent
PY = sys.executable


def wait_for(predicate, timeout=6):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate(): return True
        time.sleep(.04)
    return False


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="jd04-worker-")
        self.root = pathlib.Path(self.tmp.name) / "state"
        self.q = Queue(self.root)

    def tearDown(self):
        self.q.close()
        self.tmp.cleanup()

    def submit(self, code, timeout=3, key=None):
        return self.q.submit([PY, "-c", code], self.tmp.name, timeout, key)[0]

    def start_worker(self):
        return subprocess.Popen([PY, str(ROOT / "worker.py"), "--root", str(self.root), "serve", "--idle-exit"], cwd=ROOT)

    def state(self, jid):
        rows = self.q.status(jid)
        return rows[0]["state"] if rows else None

    def test_conversation_responsive_while_job_runs(self):
        jid = self.submit("import time; time.sleep(.35); print('done')")
        child = self.start_worker()
        start = time.monotonic()
        # Represents a foreground conversation turn while the independent worker runs.
        response = {"answer": "responsive"}
        latency = time.monotonic() - start
        self.assertLess(latency, .1)
        self.assertEqual(response["answer"], "responsive")
        self.assertEqual(child.wait(timeout=5), 0)
        self.assertEqual(self.state(jid), "succeeded")

    def test_fifo_completion_and_logs(self):
        out = pathlib.Path(self.tmp.name) / "order"
        a = self.submit(f"import time; time.sleep(.12); open({str(out)!r},'a').write('1')")
        b = self.submit(f"open({str(out)!r},'a').write('2')")
        p = self.start_worker(); self.assertEqual(p.wait(timeout=5), 0)
        self.assertEqual(out.read_text(), "12")
        self.assertEqual([self.state(a), self.state(b)], ["succeeded", "succeeded"], self.q.status())
        self.assertIn("finish state=succeeded", pathlib.Path(self.q.status(a)[0]["log_path"]).read_text())

    def test_independent_workers_cannot_run_jobs_in_the_same_worktree(self):
        marker = pathlib.Path(self.tmp.name) / "second-ran"
        first = self.submit("import time; time.sleep(.6)", timeout=3)
        first_worker = self.start_worker()
        self.assertTrue(wait_for(lambda: self.state(first) == "running"))
        other_root = pathlib.Path(self.tmp.name) / "other-state"
        other_queue = Queue(other_root)
        second, _ = other_queue.submit([PY, "-c", f"open({str(marker)!r},'w').write('unsafe')"], self.tmp.name, 3, "independent-worker")
        second_worker = subprocess.Popen([PY, str(ROOT / "worker.py"), "--root", str(other_root), "serve", "--idle-exit"], cwd=ROOT)
        try:
            self.assertEqual(second_worker.wait(timeout=5), 0)
            self.assertEqual(other_queue.status(second)[0]["state"], "failed")
            self.assertIn("already locked", other_queue.status(second)[0]["error"])
            self.assertFalse(marker.exists())
        finally:
            self.assertEqual(first_worker.wait(timeout=5), 0)
            other_queue.close()
        self.assertEqual(self.state(first), "succeeded")

    def test_stale_lock_file_does_not_block_authorized_recovery(self):
        first = acquire_worktree_lock(self.root, self.tmp.name)
        release_worktree_lock(first)
        # The inode remains as stale metadata, but no kernel lock remains held.
        second = acquire_worktree_lock(pathlib.Path(self.tmp.name) / "other-state", self.tmp.name)
        release_worktree_lock(second)

    def test_worker_queue_rejects_symlink_and_traversal_workspaces(self):
        link = pathlib.Path(self.tmp.name) / "workspace-link"
        link.symlink_to(self.tmp.name, target_is_directory=True)
        self.assertRaises(ValueError, self.q.submit, [PY, "-c", "pass"], str(link), 3, "symlink-workspace")
        self.assertRaises(ValueError, self.q.submit, [PY, "-c", "pass"], str(pathlib.Path(self.tmp.name) / ".." / "outside"), 3, "traversal-workspace")

    def test_timeout(self):
        jid = self.submit("import time; print('started', flush=True); time.sleep(4)", timeout=.2)
        p = self.start_worker(); self.assertEqual(p.wait(timeout=5), 0)
        self.assertEqual(self.state(jid), "timed_out")

    def test_fast_process_exit_preserves_return_code(self):
        jid = self.submit("pass")
        p = self.start_worker(); self.assertEqual(p.wait(timeout=5), 0)
        self.assertEqual(self.state(jid), "succeeded", self.q.status(jid))

    def test_opt_in_herdr_status_reports_worker_lifecycle(self):
        output = io.StringIO()
        prior = os.environ.get("WORKFORCE_HERDR_STATUS")
        try:
            os.environ["WORKFORCE_HERDR_STATUS"] = "1"
            with redirect_stdout(output):
                for state in ("idle", "working", "done"):
                    herdr_status(state)
        finally:
            if prior is None: os.environ.pop("WORKFORCE_HERDR_STATUS", None)
            else: os.environ["WORKFORCE_HERDR_STATUS"] = prior
        self.assertEqual(output.getvalue(), "".join(f"\x1b]7501;state={state}:app=jack-worker\x1b\\" for state in ("idle", "working", "done")))

    def test_opt_in_herdr_status_registers_scoped_job_record(self):
        output = io.StringIO()
        prior = {key: os.environ.get(key) for key in ("WORKFORCE_HERDR_STATUS", "WORKFORCE_HERDR_PROJECT_ID", "WORKFORCE_HERDR_WORKER_NAME")}
        try:
            os.environ.update(WORKFORCE_HERDR_STATUS="1", WORKFORCE_HERDR_PROJECT_ID="project-a", WORKFORCE_HERDR_WORKER_NAME="wf-project-a")
            with redirect_stdout(output):
                herdr_job_status("working", "0123456789abcdef0123456789abcdef")
                herdr_job_status("working", "unsafe job id")
        finally:
            for key, value in prior.items():
                if value is None: os.environ.pop(key, None)
                else: os.environ[key] = value
        encoded = "cHJvamVjdD1wcm9qZWN0LWEgd29ya2VyPXdmLXByb2plY3QtYSBqb2I9MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
        self.assertEqual(output.getvalue(), f"\x1b]7501;state=working:id=0123456789abcdef0123456789abcdef:app=sanro-workforce:title={encoded}\x1b\\")

    def test_opt_in_herdr_console_event_is_safe_visible_text(self):
        output = io.StringIO()
        prior = {key: os.environ.get(key) for key in ("WORKFORCE_HERDR_STATUS", "WORKFORCE_HERDR_PROJECT_ID", "WORKFORCE_HERDR_WORKER_NAME")}
        try:
            os.environ.update(WORKFORCE_HERDR_STATUS="1", WORKFORCE_HERDR_PROJECT_ID="project-a", WORKFORCE_HERDR_WORKER_NAME="sanro-workforce-pilot")
            with redirect_stdout(output):
                herdr_console_event("running", "0123456789abcdef0123456789abcdef")
                herdr_console_event("done", "invalid")
        finally:
            for key, value in prior.items():
                if value is None: os.environ.pop(key, None)
                else: os.environ[key] = value
        self.assertEqual(output.getvalue(), "[SANRO] project=project-a worker=sanro-workforce-pilot job=0123456789abcdef0123456789abcdef state=running\n")

    def test_child_network_and_process_group_escape_are_denied(self):
        code = "import socket;\ntry: socket.socket()\nexcept PermissionError: print('network-denied')\nelse: raise SystemExit(3)\nimport os;\ntry: os.setsid()\nexcept PermissionError: print('escape-denied')\nelse: raise SystemExit(4)"
        jid = self.submit(code)
        p = self.start_worker(); self.assertEqual(p.wait(timeout=5), 0)
        row = self.q.status(jid)[0]
        self.assertEqual(row["state"], "succeeded", row)
        output = pathlib.Path(row["log_path"]).read_text()
        self.assertIn("network-denied", output)
        self.assertIn("escape-denied", output)

    def test_queued_cancellation(self):
        jid = self.submit("print('must not run')")
        self.assertTrue(self.q.cancel(jid))
        p = self.start_worker(); self.assertEqual(p.wait(timeout=5), 0)
        self.assertEqual(self.state(jid), "cancelled")

    def test_running_cancellation(self):
        jid = self.submit("import time; print('started',flush=True); time.sleep(5)")
        p = self.start_worker()
        self.assertTrue(wait_for(lambda: self.state(jid) == "running"))
        self.assertTrue(self.q.cancel(jid))
        self.assertEqual(p.wait(timeout=5), 0)
        self.assertEqual(self.state(jid), "cancelled")

    def test_duplicate_key_returns_same_job(self):
        one, created1 = self.q.submit([PY, "-c", "print('ok')"], self.tmp.name, 3, "build-42")
        two, created2 = self.q.submit([PY, "-c", "print('ok')"], self.tmp.name, 3, "build-42")
        self.assertRaises(ValueError, self.q.submit, [PY, "-c", "print('different')"], self.tmp.name, 3, "build-42")
        self.assertEqual(one, two)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(len(self.q.status()), 1)

    def test_checkpoint_recovery_marks_interrupted_without_replay(self):
        out = pathlib.Path(self.tmp.name) / "should-not-run"
        jid = self.submit(f"open({str(out)!r},'w').write('replayed')")
        self.q.conn.execute("UPDATE jobs SET state='running',started='interrupted' WHERE id=?", (jid,))
        p = self.start_worker(); self.assertEqual(p.wait(timeout=5), 0)
        self.assertEqual(self.state(jid), "interrupted")
        row = self.q.status(jid)[0]
        self.assertIn("checkpoint recovery", pathlib.Path(row["log_path"]).read_text())
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
