"""Focused tests for fixed private-browser systemd boundary construction."""
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from private_browser_controller import build_systemd_argv, run_private_browser


class PrivateBrowserControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sanro-browser-controller-")
        self.root = pathlib.Path(self.temp.name)
        self.workspace = self.root / "worktree"
        (self.workspace / "apps/web/scripts").mkdir(parents=True)
        self.runner = self.workspace / "apps/web/scripts/private-browser-mcp-acceptance.mjs"
        self.runner.write_text("// synthetic runner fixture\n")
        self.job = self.root / "state/jobs/job-123"

    def tearDown(self):
        self.temp.cleanup()

    def test_fixed_unit_enforces_namespace_resources_timeout_and_cleanup(self):
        command = build_systemd_argv("/usr/bin/systemd-run", ["/usr/bin/node", str(self.runner)],
                                     self.workspace, self.job, "job-123", 90)
        rendered = "\n".join(command)
        for item in ("--user", "--wait", "--collect", "RuntimeMaxSec=90s", "CPUQuota=100%",
                     "MemoryMax=2G", "TasksMax=128", "PrivateNetwork=yes", "PrivateTmp=yes",
                     "NoNewPrivileges=yes", "ProtectSystem=strict", "KillMode=control-group"):
            self.assertIn(item, rendered)
        self.assertEqual(command[-3:], ["SANRO_REQUIRE_PRIVATE_NETNS=1", "/usr/bin/node", str(self.runner)])
        self.assertIn("/usr/bin/env", command)
        self.assertIn("-i", command)
        self.assertIn("SANRO_CHROMIUM_EXECUTABLE=/usr/local/lib/sanro-playwright/chromium-1255/chrome-linux64/chrome", command)
        self.assertNotIn("--no-sandbox", rendered)
        self.assertFalse(any("ExecStart" in item for item in command))

        class Completed:
            returncode = 0
            stdout = '{"status":"PASS"}\n'
        with patch("private_browser_controller.shutil.which", return_value="/usr/bin/systemd-run"), \
             patch("private_browser_controller.subprocess.run", return_value=Completed()) as run:
            result = run_private_browser(["/usr/bin/node", str(self.runner)], self.workspace,
                                         self.root / "state", "job-123", 90)
        self.assertEqual(result[0], 0)
        self.assertFalse((self.root / "state/jobs/job-123/tmp").exists())
        self.assertTrue((self.root / "state/jobs/job-123/artifacts").is_dir())
        self.assertTrue(run.call_args.kwargs["timeout"] > 90)
        self.assertEqual(run.call_args.kwargs["env"], {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})

    def test_rejects_unsupported_or_unbounded_requests(self):
        for timeout, job_id in ((0, "job-1"), (301, "job-1"), (10, "../job")):
            with self.subTest(timeout=timeout, job_id=job_id), self.assertRaises(ValueError):
                build_systemd_argv("/usr/bin/systemd-run", ["/usr/bin/node"], self.workspace,
                                   self.job, job_id, timeout)
        with self.assertRaises(ValueError):
            build_systemd_argv("/usr/bin/systemd-run", ["/bin/sh", "-c", "id"], self.workspace,
                               self.job, "job-1", 10)

    def test_unit_failure_is_bounded_and_job_tmp_is_removed(self):
        class Completed:
            returncode = 1
            stdout = "Failed to set up private network namespace\n"
        with patch("private_browser_controller.shutil.which", return_value="/usr/bin/systemd-run"), \
             patch("private_browser_controller.subprocess.run", return_value=Completed()):
            code, output, timed_out = run_private_browser(["/usr/bin/node", str(self.runner)], self.workspace,
                                                          self.root / "state", "job-123", 30)
        self.assertEqual(code, 1)
        self.assertFalse(timed_out)
        self.assertFalse((self.root / "state/jobs/job-123/tmp").exists())
        self.assertIn("private network namespace", output)

    def test_controller_rejects_root_before_creating_a_unit(self):
        with patch("private_browser_controller.os.getuid", return_value=0), \
             patch("private_browser_controller.subprocess.run") as run:
            with self.assertRaisesRegex(PermissionError, "refuses root"):
                run_private_browser(["/usr/bin/node", str(self.runner)], self.workspace,
                                    self.root / "state", "job-123", 30)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
