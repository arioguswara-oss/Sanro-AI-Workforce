import os
import pathlib
import subprocess
import tempfile
import unittest
import zipfile

from runtime_preflight import collect_runtime_preflight, require_capabilities


class RuntimePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="workforce-runtime-preflight-")
        self.workspace = pathlib.Path(self.tmp.name) / "project"
        self.workspace.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "feature/test"], cwd=self.workspace, check=True)
        subprocess.run(["git", "-c", "user.name=synthetic", "-c", "user.email=synthetic@example.invalid", "commit", "--allow-empty", "-qm", "fixture"], cwd=self.workspace, check=True)
        subprocess.run(["git", "remote", "add", "origin", "https://github.com/sanro/synthetic-a.git"], cwd=self.workspace, check=True)
        self.project = {"id": "synthetic-a", "repository": "sanro/synthetic-a", "branch": "feature/test", "worker_id": "worker-a", "workspace": str(self.workspace)}
        self.mandate = {"status": "APPROVED", "project_id": "synthetic-a", "branch": "feature/test", "expires_at": "2099-01-01T00:00:00Z"}
        self.sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.workspace, check=True, capture_output=True, text=True).stdout.strip()

    def tearDown(self):
        self.tmp.cleanup()

    def test_collects_structured_local_capabilities_without_network(self):
        report = collect_runtime_preflight(self.project, self.mandate, self.sha, {"PATH": "/usr/bin:/bin"})
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["capabilities"]["authorized_branch"]["status"], "PASS")
        self.assertEqual(report["capabilities"]["source_repository"]["status"], "PASS")
        self.assertEqual(report["capabilities"]["network"]["status"], "UNVERIFIED")
        self.assertNotIn("ssh_agent", report["capabilities"]["network"]["detail"])

    def test_rejects_branch_mismatch_and_aggregates_required_capability_failures(self):
        self.project["branch"] = "feature/unauthorized"
        report = collect_runtime_preflight(self.project, self.mandate, self.sha, {"PATH": "/usr/bin:/bin", "SSH_AUTH_SOCK": "/missing/agent.sock"})
        self.assertEqual(report["capabilities"]["authorized_branch"]["status"], "BLOCKED")
        self.assertIn("ssh_agent", report["blockers"])
        with self.assertRaisesRegex(PermissionError, "authorized_branch"):
            require_capabilities(report, ["authorized_branch", "ssh_agent"])

    def test_rejects_path_traversal_and_checkpoint_mismatch(self):
        project = {**self.project, "workspace": str(self.workspace / ".." / "project")}
        report = collect_runtime_preflight(project, self.mandate, "not-a-sha", {"PATH": ""})
        self.assertEqual(report["capabilities"]["canonical_workspace"]["status"], "BLOCKED")
        self.assertEqual(report["capabilities"]["checkpoint"]["status"], "BLOCKED")
        self.assertFalse(os.path.islink(self.workspace))

    def test_isolated_synthetic_edit_lint_build_and_git_acceptance(self):
        source = self.workspace / "worker_fixture.py"
        source.write_text("VALUE = 'checkpointed'\n", encoding="utf-8")
        compile(source.read_text(encoding="utf-8"), str(source), "exec")
        artifact = pathlib.Path(self.tmp.name) / "synthetic.zip"
        with zipfile.ZipFile(artifact, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(source, "worker_fixture.py")
        with zipfile.ZipFile(artifact) as archive:
            self.assertEqual(archive.read("worker_fixture.py"), source.read_bytes())
        subprocess.run(["git", "add", "worker_fixture.py"], cwd=self.workspace, check=True)
        subprocess.run(["git", "-c", "user.name=synthetic", "-c", "user.email=synthetic@example.invalid", "commit", "-qm", "synthetic isolated acceptance"], cwd=self.workspace, check=True)
        self.assertEqual(subprocess.run(["git", "status", "--porcelain"], cwd=self.workspace, check=True, capture_output=True, text=True).stdout, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
