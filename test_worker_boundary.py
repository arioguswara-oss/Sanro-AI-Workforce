"""Portable boundary test: unavailable Landlock must reject real child execution."""
import pathlib
import tempfile
import unittest
from landlock_sandbox import landlock_abi
from worker import Queue, worker_loop

class BoundaryTests(unittest.TestCase):
    def test_real_execution_remains_fail_closed_without_landlock(self):
        if landlock_abi() > 0:
            self.skipTest('Landlock available: use full worker suite')
        with tempfile.TemporaryDirectory() as directory:
            q = Queue(directory)
            try:
                marker = pathlib.Path(directory) / 'must-not-exist'
                job, _ = q.submit(['/usr/bin/touch', str(marker)], directory, 2, 'boundary-probe')
                self.assertEqual(worker_loop(q, idle_exit=True), 0)
                self.assertEqual(q.status(job)[0]['state'], 'failed')
                self.assertFalse(marker.exists())
            finally:
                q.close()

    def test_unsafe_database_and_nonfinite_timeout_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / 'state'
            root.mkdir(mode=0o700)
            target = pathlib.Path(directory) / 'foreign'
            target.write_text('untouched')
            (root / 'jobs.sqlite3').symlink_to(target)
            self.assertRaises(PermissionError, Queue, root)
            self.assertEqual(target.read_text(), 'untouched')
            (root / 'jobs.sqlite3').unlink()
            q = Queue(root)
            try:
                for timeout in (float('nan'), float('inf'), -1, 86401):
                    self.assertRaises(ValueError, q.submit, ['/usr/bin/true'], directory, timeout, None)
            finally:
                q.close()

    def test_idempotency_conflict_cannot_replace_command(self):
        with tempfile.TemporaryDirectory() as directory:
            q = Queue(directory)
            try:
                first, created = q.submit(['/usr/bin/true'], directory, 2, 'same-key')
                self.assertTrue(created)
                self.assertEqual(q.submit(['/usr/bin/true'], directory, 2, 'same-key'), (first, False))
                self.assertRaises(ValueError, q.submit, ['/usr/bin/false'], directory, 2, 'same-key')
                self.assertRaises(ValueError, q.submit, ['/usr/bin/true'], directory, 3, 'same-key')
            finally:
                q.close()
