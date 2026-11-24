import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

from worker import Queue, worker_loop

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

    def test_timeout(self):
        jid = self.submit("import time; print('started', flush=True); time.sleep(4)", timeout=.2)
        p = self.start_worker(); self.assertEqual(p.wait(timeout=5), 0)
        self.assertEqual(self.state(jid), "timed_out")

    def test_fast_process_exit_preserves_return_code(self):
        jid = self.submit("pass")
        p = self.start_worker(); self.assertEqual(p.wait(timeout=5), 0)
        self.assertEqual(self.state(jid), "succeeded", self.q.status(jid))

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
