import os
import pathlib
import tempfile
import unittest

from codex_job_launcher import build_codex_argv


class CodexLauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="workforce-codex-launcher-")
        self.binary = pathlib.Path(self.tmp.name) / "codex"
        self.binary.write_text("#!/bin/sh\nexit 0\n")
        self.binary.chmod(0o700)
        self.admission = {"project_id": "project-a", "worker_id": "worker-project-a", "job_id": "run-12345678", "workspace": "/tmp/project-a", "checkpoint_sha": "a" * 40, "permission_profile": {"write_scope": "project-worktree", "allow_network": False}}
        self.preflight = {"capabilities": {name: {"status": "PASS"} for name in ("project_identity", "canonical_workspace", "authorized_branch", "source_repository", "workspace_write", "git_metadata", "mandate", "checkpoint", "codex_cli")}}

    def tearDown(self):
        self.tmp.cleanup()

    def test_uses_native_workspace_write_and_approval_with_explicit_scope(self):
        instruction = {"project_id": "project-a", "run_id": "run-12345678", "baseline_sha": "a" * 40, "instruction": "safe task"}
        argv = build_codex_argv({"command": [str(self.binary)]}, self.admission, instruction, self.preflight)
        self.assertEqual(argv[:2], [str(self.binary), "exec"])
        self.assertEqual(argv[argv.index("--cd") + 1], self.admission["workspace"])
        self.assertEqual(argv[argv.index("--sandbox") + 1], "workspace-write")
        self.assertIn("--approve-for-me", argv)
        self.assertIn("--ephemeral", argv)
        self.assertIn(self.admission["job_id"], argv[-1])
        self.assertIn(self.admission["checkpoint_sha"], argv[-1])
        self.assertNotIn("danger-full-access", argv)

    def test_argv_never_interprets_instruction_as_shell(self):
        payload = "$(touch /tmp/should-not-exist); safe text"
        argv = build_codex_argv({"command": [str(self.binary)]}, self.admission, {"instruction": payload}, self.preflight)
        self.assertEqual(argv[-1].count(payload), 1)
        self.assertEqual(len(argv), 10)

    def test_rejects_wrapper_arguments_and_network_permission(self):
        with self.assertRaises(PermissionError):
            build_codex_argv({"command": [str(self.binary), "--dangerously-bypass-approvals-and-sandbox"]}, self.admission, {}, self.preflight)
        admission = {**self.admission, "permission_profile": {"write_scope": "project-worktree", "allow_network": True}}
        with self.assertRaises(PermissionError):
            build_codex_argv({"command": [str(self.binary)]}, admission, {}, self.preflight)

    def test_rejects_missing_preflight_and_unlisted_runtime_gate(self):
        with self.assertRaises(PermissionError):
            build_codex_argv({"command": [str(self.binary)]}, self.admission, {})
        with self.assertRaises(PermissionError):
            build_codex_argv({"command": [str(self.binary)], "runtime_requirements": ["arbitrary_shell"]}, self.admission, {}, self.preflight)


if __name__ == "__main__":
    unittest.main(verbosity=2)
