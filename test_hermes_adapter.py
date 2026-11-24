import pathlib
import fcntl
import os
import sys
import tempfile
import time
import unittest

from hermes_adapter import Authorization, HermesAdapter, WorkerSupervisor


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="jd04-adapter-")
        self.workspace = pathlib.Path(self.tmp.name) / "project"
        self.workspace.mkdir()
        self.workspace_b = pathlib.Path(self.tmp.name) / "project-b"
        self.workspace_b.mkdir()
        (self.workspace_b / "private.txt").write_text("other-project-secret")
        self.root = pathlib.Path(self.tmp.name) / "state"
        self.adapter = HermesAdapter(self.root, {"proj-a": self.workspace}, [[sys.executable, "-c"]])
        self.auth = Authorization("user-a", frozenset({"engineering:execute", "engineering:read", "engineering:cancel"}), frozenset({"proj-a"}), frozenset({str(self.workspace.resolve())}), frozenset({"approval-7"}))
        self.supervisor = WorkerSupervisor(self.root)
        self.supervisor.start()

    def tearDown(self):
        self.supervisor.shutdown()
        self.adapter.close()
        self.tmp.cleanup()

    def submit(self, source, key, timeout=60):
        return self.adapter.submit(self.auth, project_id="proj-a", workspace=self.workspace, approval_ref="approval-7", command=[sys.executable, "-c", source], timeout=timeout, idempotency_key=key)

    def wait_status(self, job_id, expected, timeout=5):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            state = self.adapter.status(self.auth, project_id="proj-a", workspace=self.workspace, job_id=job_id)["status"]
            if state == expected: return state
            time.sleep(.03)
        return state

    def test_45_second_job_nonblocking_and_foreground_response(self):
        started = time.monotonic()
        result = self.submit("import time; print('started', flush=True); time.sleep(45); print('done')", "long-job")
        submit_latency = time.monotonic() - started
        self.assertLess(submit_latency, 2)
        job_id = result["job_id"]
        self.assertEqual(self.wait_status(job_id, "RUNNING"), "RUNNING")
        foreground_start = time.monotonic()
        reply = self.adapter.status(self.auth, project_id="proj-a", workspace=self.workspace, job_id=job_id)
        foreground_latency = time.monotonic() - foreground_start
        self.assertEqual(reply["status"], "RUNNING")
        self.assertLess(foreground_latency, .1)
        print(f"MEASURED submit_latency_seconds={submit_latency:.6f} foreground_response_seconds={foreground_latency:.6f}")
        log_text = ""
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and "\nstarted\n" not in log_text:
            log_text = self.adapter.logs(self.auth, project_id="proj-a", workspace=self.workspace, job_id=job_id)
            time.sleep(.02)
        self.assertIn("\nstarted\n", log_text)
        cancelled = self.adapter.cancel(self.auth, project_id="proj-a", workspace=self.workspace, job_id=job_id)
        self.assertTrue(cancelled["accepted"])
        self.assertEqual(self.wait_status(job_id, "CANCELLED"), "CANCELLED")
        result = self.adapter.result(self.auth, project_id="proj-a", workspace=self.workspace, job_id=job_id)
        self.assertEqual(result["status"], "CANCELLED")
        self.assertIn("started", result["output"])
        events = self.adapter.drain_notifications(self.auth, project_id="proj-a", workspace=self.workspace)
        self.assertEqual([event["event"] for event in events], ["CANCELLED"])
        self.assertEqual(self.adapter.drain_notifications(self.auth, project_id="proj-a", workspace=self.workspace), [])

    def test_duplicate_submission_is_idempotent(self):
        one = self.submit("print('once')", "same-key")
        two = self.submit("print('twice')", "same-key")
        self.assertEqual(one["job_id"], two["job_id"])
        self.assertTrue(one["created"])
        self.assertFalse(two["created"])

    def test_completion_result_and_secret_redaction(self):
        submitted = self.submit("print('password=shh123'); print('finished')", "result")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and self.adapter.status(self.auth, project_id="proj-a", workspace=self.workspace, job_id=submitted["job_id"])["status"] == "QUEUED":
            time.sleep(.02)
        self.assertEqual(self.wait_status(submitted["job_id"], "COMPLETED"), "COMPLETED")
        result = self.adapter.result(self.auth, project_id="proj-a", workspace=self.workspace, job_id=submitted["job_id"])
        self.assertIn("[REDACTED]", result["output"])
        self.assertNotIn("shh123", result["output"])
        self.assertEqual(result["exit_code"], 0)
        events = self.adapter.drain_notifications(self.auth, project_id="proj-a", workspace=self.workspace)
        self.assertEqual([event["event"] for event in events], ["COMPLETED"])

    def test_failure_notification_is_redacted_and_session_bound(self):
        submitted = self.submit("raise SystemExit(9)", "failed-event")
        self.assertEqual(self.wait_status(submitted["job_id"], "FAILED"), "FAILED")
        other_session = Authorization("other-session", self.auth.scopes, self.auth.project_ids,
            self.auth.workspaces, self.auth.approval_refs)
        self.assertEqual(self.adapter.drain_notifications(other_session, project_id="proj-a", workspace=self.workspace), [])
        events = self.adapter.drain_notifications(self.auth, project_id="proj-a", workspace=self.workspace)
        self.assertEqual(events[0]["event"], "FAILED")
        self.assertNotIn("raise SystemExit", events[0]["message"])

    def test_interrupted_job_is_not_replayed(self):
        self.supervisor.shutdown()
        submitted = self.submit("print('should not replay')", "interrupted")
        jid = submitted["job_id"]
        self.adapter.db.execute("UPDATE jobs SET state='running',started='crash' WHERE id=?", (jid,))
        lock = open(self.root / "worker.lock", "a+")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with self.assertRaises(RuntimeError):
                self.supervisor.recover()
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()
        message = self.supervisor.recover()
        self.assertIn("explicit review", message)
        self.assertEqual(self.adapter.status(self.auth, project_id="proj-a", workspace=self.workspace, job_id=jid)["status"], "INTERRUPTED")
        self.assertEqual(self.adapter.db.execute("SELECT count(*) FROM jobs WHERE state='queued'").fetchone()[0], 0)

    def test_supervisor_shutdown_interrupts_active_job(self):
        submitted = self.submit("import time; print('started', flush=True); time.sleep(45)", "shutdown-test")
        self.assertEqual(self.wait_status(submitted["job_id"], "RUNNING"), "RUNNING")
        self.assertTrue(self.supervisor.shutdown(timeout=4))
        self.assertEqual(self.adapter.status(self.auth, project_id="proj-a", workspace=self.workspace, job_id=submitted["job_id"])["status"], "INTERRUPTED")

    def test_supervisor_does_not_inherit_gateway_environment(self):
        self.supervisor.shutdown()
        marker = "JD04_SYNTHETIC_CREDENTIAL_MARKER"
        previous = os.environ.get(marker)
        os.environ[marker] = "synthetic-only"
        try:
            self.supervisor.start()
            child_env = pathlib.Path(f"/proc/{self.supervisor.process.pid}/environ").read_bytes()
            self.assertNotIn(marker.encode(), child_env)
            self.assertNotIn(b"synthetic-only", child_env)
        finally:
            if previous is None:
                os.environ.pop(marker, None)
            else:
                os.environ[marker] = previous

    def test_rejects_unauthorized_project_workspace_and_command(self):
        with self.assertRaises(PermissionError):
            self.adapter.submit(self.auth, project_id="proj-b", workspace=self.workspace, approval_ref="approval-7", command=[sys.executable, "-c", "pass"], idempotency_key="bad")
        with self.assertRaises(PermissionError):
            self.adapter.submit(self.auth, project_id="proj-a", workspace=self.tmp.name, approval_ref="approval-7", command=[sys.executable, "-c", "pass"], idempotency_key="bad2")
        with self.assertRaises(PermissionError):
            self.adapter.submit(self.auth, project_id="proj-a", workspace=self.workspace, approval_ref="approval-7", command=["bash", "-c", "true"], idempotency_key="bad3")
        with self.assertRaises(PermissionError):
            self.adapter.submit(self.auth, project_id="proj-a", workspace=self.workspace, approval_ref="unapproved", command=[sys.executable, "-c", "pass"], idempotency_key="bad4")

    def test_cross_project_job_access_denied(self):
        submitted = self.submit("print('private')", "private")
        other = Authorization("user-a", self.auth.scopes, frozenset({"proj-b"}), self.auth.workspaces, self.auth.approval_refs)
        with self.assertRaises(PermissionError):
            self.adapter.status(other, project_id="proj-b", workspace=self.workspace, job_id=submitted["job_id"])

    def test_landlock_denies_host_and_other_project_paths_but_allows_project_work(self):
        other_path = str(self.workspace_b / "private.txt")
        own_path = str(self.workspace / "created.txt")
        script = (
            "from pathlib import Path; import os; "
            f"[(lambda p: print(p+':BLOCKED'))(p) for p in [{other_path!r}, '/etc/passwd'] "
            "if (lambda: True)() and not _can_read(p)]; "
            f"Path({own_path!r}).write_text('allowed'); print('PROJECT_WRITE_OK')"
        )
        # Keep the child probe self-contained and report denial without exposing host file contents.
        script = "def _can_read(p):\n try: open(p,'rb').read(1); return True\n except OSError: return False\n" + script
        submitted = self.submit(script, "landlock-check")
        self.assertEqual(self.wait_status(submitted["job_id"], "COMPLETED"), "COMPLETED")
        output = self.adapter.logs(self.auth, project_id="proj-a", workspace=self.workspace, job_id=submitted["job_id"])
        self.assertIn("BLOCKED", output)
        self.assertIn("PROJECT_WRITE_OK", output)
        self.assertEqual((self.workspace / "created.txt").read_text(), "allowed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
