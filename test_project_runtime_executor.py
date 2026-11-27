"""Synthetic policy and fail-closed tests for the fixed runtime wrapper."""
import os
import json
import hashlib
import copy
import pathlib
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from project_runtime_executor import OPERATIONS, SANRO_QA_PILOT, WORKFORCE_ROOT, RuntimeAdmissionError, _argv, _parse_runtime_evidence, _reported_blocked, _validate_policy, execute
from workforce_runtime_adapter import prepare_runtime_profile


class ProjectRuntimeExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gdi02r-runtime-wrapper-test-")
        self.root = pathlib.Path(self.temp.name)
        self.workspace = self.root / "repo"
        self.workspace.mkdir()
        def git(*args):
            return subprocess.run(["git", "-C", str(self.workspace), *args], check=True, capture_output=True, text=True).stdout.strip()
        subprocess.run(["git", "init", "-b", "feature/runtime-test", str(self.workspace)], check=True, capture_output=True)
        git("config", "user.email", "test@example.invalid")
        git("config", "user.name", "Synthetic Test")
        (self.workspace / "fixture.txt").write_text("synthetic\n")
        git("add", "fixture.txt")
        git("commit", "-m", "fixture")
        git("remote", "add", "origin", "https://github.com/synthetic/runtime-test.git")
        self.sha = git("rev-parse", "HEAD")
        self.state = self.root / "state"
        self.state.mkdir(mode=0o700)
        self.request = {
            "version": 1, "project_id": "runtime-test", "job_id": "job-001",
            "worker_id": "local-ci", "workspace": str(self.workspace),
            "repository": "synthetic/runtime-test", "branch": "feature/runtime-test",
            "source_sha": self.sha, "checkpoint_sha": self.sha,
            "operation": "browser_smoke", "required_capabilities": ["browser_runtime"],
            "mandate_id": "mandate-001", "subject": "owner:synthetic",
            "approval_ref": "approval-001", "native_approval_sha256": "b" * 64,
            "timeout_seconds": 120, "arguments": {},
        }
        self.policy = {
            "version": 1,
            "projects": {"runtime-test": {"status": "AUTHORIZED", "workspace": str(self.workspace),
                "repository": "synthetic/runtime-test", "branch": "feature/runtime-test",
                "worker_id": "local-ci", "state_root": str(self.state)}},
            "jobs": {"job-001": {"status": "AUTHORIZED", "project_id": "runtime-test",
                "worker_id": "local-ci", "branch": "feature/runtime-test", "source_sha": self.sha,
                "operation": "browser_smoke", "mandate_id": "mandate-001", "subject": "owner:synthetic",
                "approval_ref": "approval-001", "native_approval_sha256": "b" * 64}},
            "mandates": {"mandate-001": {"status": "APPROVED", "project_id": "runtime-test",
                "repository": "synthetic/runtime-test", "branch": "feature/runtime-test",
                "workspace": str(self.workspace), "subject": "owner:synthetic",
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "approval_refs": ["approval-001"], "allowed_actions": ["runtime:browser", "runtime:mariadb"],
                "forbidden_actions": ["ssh:staging", "production:deploy", "merge"],
                "max_cost_usd": 0, "environment": "isolated-development"}},
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_authorized_browser_request_validates(self):
        project, mandate, state, action = _validate_policy(self.policy, self.request)
        self.assertEqual(project["status"], "AUTHORIZED")
        self.assertEqual(mandate["status"], "APPROVED")
        self.assertEqual(state, self.state)
        self.assertEqual(action, "runtime:browser")

    def test_browser_and_database_commands_are_fixed_and_scoped(self):
        for _, _, relative in OPERATIONS.values():
            target = self.workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# synthetic fixture\n")
        self.assertEqual(pathlib.Path(_argv(self.workspace, "browser_smoke")[1]), self.workspace / OPERATIONS["browser_smoke"][2])
        self.assertEqual(pathlib.Path(_argv(self.workspace, "mariadb_synthetic")[1]), self.workspace / "isolated_mariadb_executor.py")
        with self.assertRaises(RuntimeAdmissionError):
            _argv(self.workspace, "arbitrary_shell")

    def test_runtime_pass_requires_operation_specific_evidence_shape(self):
        screenshot = self.workspace / "apps/web/.cache/playwright/GDI02R_CHROMIUM_SMOKE.png"
        screenshot.parent.mkdir(parents=True)
        screenshot.write_bytes(b"synthetic screenshot fixture")
        browser = '{"status":"PASS","browserVersion":"synthetic","result":"DOM_OK:42","screenshot":"apps/web/.cache/playwright/GDI02R_CHROMIUM_SMOKE.png"}'
        self.assertEqual(_parse_runtime_evidence("browser_smoke", browser, self.workspace)["dom_result"], "DOM_OK:42")
        self.assertIsNone(_parse_runtime_evidence("browser_smoke", browser.replace("DOM_OK:42", "wrong"), self.workspace))
        maria = '{"status":"PASS","server_version":"synthetic-mariadb","network_disabled":true,"synthetic_rows_verified":2}'
        self.assertTrue(_parse_runtime_evidence("mariadb_synthetic", maria, self.workspace)["network_disabled"])
        self.assertIsNone(_parse_runtime_evidence("mariadb_synthetic", maria.replace('"network_disabled":true', '"network_disabled":false'), self.workspace))
        self.assertTrue(_reported_blocked('{"status":"BLOCKED","error":"Operation not permitted"}'))

    def test_private_browser_requires_project_scope_and_real_isolation_evidence(self):
        request = dict(self.request, operation="private_browser_acceptance",
                       required_capabilities=["private_browser_runtime"])
        with self.assertRaisesRegex(RuntimeAdmissionError, "explicitly supported project binding"):
            _validate_policy(self.policy, request)
        authorized_request = dict(request, project_id="sanro-ai-workforce")
        authorized_policy = copy.deepcopy(self.policy)
        authorized_policy["projects"]["sanro-ai-workforce"] = authorized_policy["projects"].pop("runtime-test")
        authorized_policy["mandates"]["mandate-001"]["project_id"] = "sanro-ai-workforce"
        authorized_policy["jobs"]["job-001"]["project_id"] = "sanro-ai-workforce"
        authorized_policy["jobs"]["job-001"]["operation"] = "private_browser_acceptance"
        _validate_policy(authorized_policy, authorized_request)

        screenshot_root = self.state / "accepted-job" / "artifacts"
        screenshot_root.mkdir(parents=True)
        screenshot = screenshot_root / "acceptance.png"
        screenshot.write_bytes(b"synthetic png artifact")
        digest = hashlib.sha256(screenshot.read_bytes()).hexdigest()
        event = {"status": "PASS", "browserVersion": "synthetic", "mcpVersion": "0.0.86",
                 "uid": 1001, "chromiumSandboxConfigured": True, "chromiumNoSandboxArgumentObserved": False,
                 "javascriptState": "DOM_OK:MCP_OK:42", "steps": ["initialize", "tools/list", "navigate", "snapshot", "fill", "click", "evaluate", "screenshot", "close"],
                 "networkIsolation": "private-network-namespace", "unauthorizedEgressBlocked": True,
                 "enforcedLimits": {"memoryMaxBytes": 2 * 1024 ** 3, "cpuQuotaCores": 1, "pidsMax": 128},
                 "measured": {"peakProcessTreeRssBytes": 4096, "peakProcessCount": 3, "processTreeCpuTicks": 7},
                 "cleanup": "PASS", "screenshot": str(screenshot), "screenshotSha256": digest}
        output = json.dumps(event)
        evidence = _parse_runtime_evidence("private_browser_acceptance", output, self.workspace, screenshot_root)
        self.assertEqual(evidence["javascript_state"], "DOM_OK:MCP_OK:42")
        self.assertTrue(evidence["unauthorized_egress_blocked"])
        event["networkIsolation"] = "NOT_ENFORCED"
        self.assertIsNone(_parse_runtime_evidence("private_browser_acceptance", json.dumps(event), self.workspace, screenshot_root))
        event["networkIsolation"] = "private-network-namespace"
        screenshot.write_bytes(b"tampered")
        self.assertIsNone(_parse_runtime_evidence("private_browser_acceptance", output, self.workspace, screenshot_root))

    def test_sanro_qa_pilot_runtime_is_pinned_read_only_and_uses_workforce_entrypoint(self):
        request = dict(self.request, project_id=SANRO_QA_PILOT["project_id"], job_id="sanroqa-pilot-job-001",
                       worker_id=SANRO_QA_PILOT["worker_id"], workspace=SANRO_QA_PILOT["workspace"],
                       repository=SANRO_QA_PILOT["repository"], branch=SANRO_QA_PILOT["branch"],
                       source_sha=SANRO_QA_PILOT["source_sha"], checkpoint_sha=SANRO_QA_PILOT["source_sha"],
                       operation=SANRO_QA_PILOT["operation"], required_capabilities=[SANRO_QA_PILOT["capability"]],
                       mandate_id=SANRO_QA_PILOT["approval_id"], approval_ref="a" * 64)
        request["native_approval_sha256"] = "c" * 64
        permission = {"version": 1, "read_only": True, "write_scope": "none", "allow_network": False, "allow_process_creation": True}
        policy = {"version": 1,
            "projects": {SANRO_QA_PILOT["project_id"]: {"status": "AUTHORIZED", "workspace": SANRO_QA_PILOT["workspace"],
                "repository": SANRO_QA_PILOT["repository"], "branch": SANRO_QA_PILOT["branch"],
                "worker_id": SANRO_QA_PILOT["worker_id"], "source_sha": SANRO_QA_PILOT["source_sha"],
                "permission_profile": permission, "state_root": str(self.state)}},
            "jobs": {request["job_id"]: {"status": "AUTHORIZED", "project_id": request["project_id"],
                "worker_id": request["worker_id"], "branch": request["branch"], "source_sha": request["source_sha"],
                "operation": request["operation"], "mandate_id": request["mandate_id"], "subject": request["subject"],
                "approval_ref": request["approval_ref"], "native_approval_sha256": request["native_approval_sha256"]}},
            "mandates": {request["mandate_id"]: {"status": "APPROVED", "project_id": request["project_id"],
                "repository": request["repository"], "branch": request["branch"], "workspace": request["workspace"],
                "subject": request["subject"], "expires_at": SANRO_QA_PILOT["expires_at"],
                "approval_refs": [request["approval_ref"]], "allowed_actions": ["qa:execute", "runtime:browser"],
                "forbidden_actions": ["engineering:execute", "git:write", "worker:manage", "ssh:staging", "merge", "production:deploy", "paid-api", "other-repository:write"],
                "max_cost_usd": 0, "environment": "isolated-development"}}}
        project, mandate, state, action = _validate_policy(policy, request)
        self.assertEqual(project["worker_id"], "sanro-qa")
        self.assertTrue(project["permission_profile"]["read_only"])
        self.assertEqual(mandate["expires_at"], SANRO_QA_PILOT["expires_at"])
        self.assertEqual(action, "runtime:browser")
        runner = pathlib.Path(_argv(pathlib.Path(SANRO_QA_PILOT["workspace"]), SANRO_QA_PILOT["operation"], SANRO_QA_PILOT["project_id"])[1])
        self.assertEqual(runner, WORKFORCE_ROOT / "apps/web/scripts/sanro-qa-pilot-local-ci.mjs")
        bad = copy.deepcopy(policy)
        bad["mandates"][SANRO_QA_PILOT["approval_id"]]["allowed_actions"].append("engineering:execute")
        with self.assertRaisesRegex(RuntimeAdmissionError, "mandate is broader"):
            _validate_policy(bad, request)

    def test_workforce_adapter_preserves_owner_approval_id_for_pilot_policy(self):
        project={"id":SANRO_QA_PILOT["project_id"],"workspace":SANRO_QA_PILOT["workspace"],
                 "repository":SANRO_QA_PILOT["repository"],"branch":SANRO_QA_PILOT["branch"],
                 "worker_id":SANRO_QA_PILOT["worker_id"],"permission_profile":
                 {"version":1,"read_only":True,"write_scope":"none","allow_network":False,"allow_process_creation":True}}
        subject="owner:synthetic"
        mandate={"id":SANRO_QA_PILOT["approval_id"],"status":"APPROVED","project_id":project["id"],
                 "repository":project["repository"],"branch":project["branch"],"environment":"isolated-development",
                 "owner_actor":subject,"max_cost_usd":0,"expires_at":SANRO_QA_PILOT["expires_at"],
                 "allowed_actions":["qa:execute","runtime:browser"],"forbidden_actions":["engineering:execute","git:write","worker:manage","ssh:staging","merge","production:deploy","paid-api","other-repository:write"],
                 "scopes":["runtime:browser"]}
        request={"project":project,"mandate":mandate,"principal":{"subject":subject,"projects":
                 {project["id"]:{"approval_refs":[SANRO_QA_PILOT["approval_id"]]}}},
                 "approval_ref":SANRO_QA_PILOT["approval_id"],"native_approval":{"approved":True,"evidence_sha256":"d"*64},
                 "profile_config":{"executor":"local-ci","role":"qa","command":["/usr/bin/true"],
                 "runtime_operation":SANRO_QA_PILOT["operation"],"runtime_timeout_seconds":120,
                 "projects":[SANRO_QA_PILOT["project_id"]]}}
        admission={"project_id":project["id"],"worker_id":project["worker_id"],"job_id":"sanroqa-adapter-job-01",
                   "checkpoint_sha":SANRO_QA_PILOT["source_sha"]}
        runtime_request, runtime_policy=prepare_runtime_profile(request,admission,str(self.state))
        self.assertEqual(runtime_request["mandate_id"],SANRO_QA_PILOT["approval_id"])
        self.assertEqual(runtime_request["operation"],SANRO_QA_PILOT["operation"])
        self.assertEqual(runtime_policy["projects"][project["id"]]["permission_profile"],project["permission_profile"])

    def test_rejects_expired_mandate_and_wrong_project(self):
        self.policy["mandates"]["mandate-001"]["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(RuntimeAdmissionError, "expired"):
            _validate_policy(self.policy, self.request)
        self.policy["mandates"]["mandate-001"]["expires_at"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        wrong = dict(self.request, project_id="other")
        with self.assertRaisesRegex(RuntimeAdmissionError, "project registry"):
            _validate_policy(self.policy, wrong)

    def test_rejects_invalid_operation_arguments_capability_and_timeout(self):
        for update in (
            {"operation": "shell", "required_capabilities": ["browser_runtime"]},
            {"arguments": {"command": "id"}},
            {"required_capabilities": ["local_ci"]},
            {"timeout_seconds": 301},
            {"timeout_seconds": True},
            {"checkpoint_sha": "f" * 40},
        ):
            with self.subTest(update=update), self.assertRaises(RuntimeAdmissionError):
                _validate_policy(self.policy, dict(self.request, **update))

    def test_rejects_missing_approval_or_branch_mismatch(self):
        wrong_approval = dict(self.request, approval_ref="not-authorized")
        policy_with_bound_job = copy.deepcopy(self.policy)
        policy_with_bound_job["jobs"]["job-001"]["approval_ref"] = "not-authorized"
        with self.assertRaisesRegex(RuntimeAdmissionError, "approval reference"):
            _validate_policy(policy_with_bound_job, wrong_approval)
        wrong_branch = dict(self.request, branch="main")
        with self.assertRaisesRegex(RuntimeAdmissionError, "project registry"):
            _validate_policy(self.policy, wrong_branch)

    def test_rejects_job_identity_or_native_approval_rebinding(self):
        wrong_job = dict(self.request, job_id="job-002")
        with self.assertRaisesRegex(RuntimeAdmissionError, "job registry"):
            _validate_policy(self.policy, wrong_job)
        rebound = copy.deepcopy(self.policy)
        rebound["jobs"]["job-001"]["worker_id"] = "other-worker"
        with self.assertRaisesRegex(RuntimeAdmissionError, "job registry"):
            _validate_policy(rebound, self.request)

    def test_rejects_protected_credential_and_runtime_workspaces(self):
        protected_paths = [
            self.root / ".hermes",
            self.root / ".ssh",
            self.root / "secrets",
            self.root / ".local" / "share" / "private-runtime",
        ]
        for protected in protected_paths:
            with self.subTest(path=protected):
                protected.mkdir(parents=True, exist_ok=True)
                request = dict(self.request, workspace=str(protected))
                self.policy["projects"]["runtime-test"]["workspace"] = str(protected)
                self.policy["mandates"]["mandate-001"]["workspace"] = str(protected)
                with self.assertRaisesRegex(RuntimeAdmissionError, "protected host path"):
                    _validate_policy(self.policy, request)

    def test_backup_or_arbitrary_operation_cannot_be_admitted(self):
        for operation in ("backup", "restore", "shell", "terminal"):
            with self.subTest(operation=operation), self.assertRaisesRegex(RuntimeAdmissionError, "not allowlisted"):
                _validate_policy(self.policy, dict(self.request, operation=operation))

    def test_duplicate_checkpoint_is_rejected_without_runtime_launch(self):
        jobs = self.state / "jobs"
        jobs.mkdir(mode=0o700)
        (jobs / "job-001.json").write_text('{"stage":"COMPLETED"}\n')
        with self.assertRaisesRegex(RuntimeAdmissionError, "silent replay"):
            execute(self.request, self.policy)
        self.assertFalse((jobs / "job-001.lock").exists())

    def test_workforce_adapter_binds_profile_mandate_and_checkpoint(self):
        project = {"id": "runtime-test", "workspace": str(self.workspace), "repository": "synthetic/runtime-test",
                   "branch": "feature/runtime-test", "worker_id": "local-ci", "environment": "isolated-development"}
        approval = {"status": "APPROVED", "project_id": "runtime-test", "repository": "synthetic/runtime-test",
                    "branch": "feature/runtime-test", "environment": "isolated-development", "max_cost_usd": 0,
                    "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                    "allowed_actions": ["runtime:browser"], "forbidden_actions": ["production:deploy", "merge"]}
        workforce_request = {"project": project, "principal": {"subject": "owner:synthetic", "projects": {
            "runtime-test": {"approval_refs": ["approval-001"]}}}, "mandate": approval,
            "approval_ref": "approval-001", "native_approval": {"approved": True, "evidence_sha256": "c" * 64},
            "profile_config": {"projects": ["runtime-test"], "role": "qa",
                "executor": "local-ci", "command": ["/usr/bin/true"], "runtime_operation": "browser_smoke", "runtime_timeout_seconds": 100}}
        admission = {"project_id": "runtime-test", "worker_id": "local-ci", "job_id": "job-001", "checkpoint_sha": self.sha}
        workforce_state = self.root / "workforce-state"
        workforce_state.mkdir(mode=0o700)
        wrapped, policy = prepare_runtime_profile(workforce_request, admission, str(workforce_state))
        self.assertEqual(wrapped["operation"], "browser_smoke")
        self.assertEqual(wrapped["required_capabilities"], ["browser_runtime"])
        self.assertEqual(wrapped["source_sha"], self.sha)
        self.assertEqual(wrapped["arguments"], {})
        self.assertEqual(policy["jobs"]["job-001"]["source_sha"], self.sha)
        self.assertEqual(policy["jobs"]["job-001"]["worker_id"], "local-ci")
        self.assertEqual(policy["mandates"][wrapped["mandate_id"]]["allowed_actions"], ["runtime:browser"])

    def test_workforce_adapter_rejects_unapproved_operation(self):
        project = {"id": "runtime-test", "workspace": str(self.workspace), "repository": "synthetic/runtime-test",
                   "branch": "feature/runtime-test", "worker_id": "local-ci"}
        request = {"project": project, "principal": {"subject": "owner:synthetic", "projects": {
            "runtime-test": {"approval_refs": ["approval-001"]}}}, "mandate": {"status": "APPROVED",
            "max_cost_usd": 0, "allowed_actions": [], "forbidden_actions": []}, "approval_ref": "approval-001",
            "native_approval": {"approved": True, "evidence_sha256": "c" * 64},
            "profile_config": {"projects": ["runtime-test"], "role": "qa", "executor": "local-ci", "command": ["/usr/bin/true"],
                "runtime_operation": "browser_smoke"}}
        admission = {"project_id": "runtime-test", "worker_id": "local-ci", "job_id": "job-001", "checkpoint_sha": self.sha}
        workforce_state = self.root / "workforce-state"
        workforce_state.mkdir(mode=0o700)
        with self.assertRaisesRegex(PermissionError, "not explicitly allowed"):
            prepare_runtime_profile(request, admission, str(workforce_state))


if __name__ == "__main__":
    unittest.main()
