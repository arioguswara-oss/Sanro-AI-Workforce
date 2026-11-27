import unittest

from workforce_worker_bridge import verify_bridge_admission
from project_runtime_executor import SANRO_QA_PILOT


class BridgeAdmissionTests(unittest.TestCase):
    def test_bridge_fails_closed_before_executor_without_registered_admission(self):
        request = {"project": {"id": "pilot"}, "projects": {}}
        with self.assertRaisesRegex(PermissionError, "validated project admission"):
            verify_bridge_admission(request)

    def test_pilot_bridge_accepts_only_the_approved_read_only_runtime_binding(self):
        profile={"executor":"local-ci","role":"qa","command":["/usr/bin/true"],
                 "runtime_operation":SANRO_QA_PILOT["operation"]}
        permission={"version":1,"read_only":True,"write_scope":"none","allow_network":False,"allow_process_creation":True}
        project={"id":SANRO_QA_PILOT["project_id"],"workspace":SANRO_QA_PILOT["workspace"],
                 "repository":SANRO_QA_PILOT["repository"],"branch":SANRO_QA_PILOT["branch"],
                 "source_sha":SANRO_QA_PILOT["source_sha"],"worker_id":SANRO_QA_PILOT["worker_id"],
                 "mainline_qa_only":True,"environment":"isolated-development","permission_profile":permission}
        principal={"subject":"owner:synthetic","projects":{project["id"]:{"scopes":["read","runtime:browser"],
                   "approval_refs":[SANRO_QA_PILOT["approval_id"]]}}}
        mandate={"id":SANRO_QA_PILOT["approval_id"],"status":"APPROVED","project_id":project["id"],
                 "repository":project["repository"],"branch":"main","environment":"isolated-development",
                 "owner_actor":principal["subject"],"max_cost_usd":0,"allowed_actions":["qa:execute","runtime:browser"],
                 "forbidden_actions":["engineering:execute","git:write","worker:manage","ssh:staging","merge","production:deploy","paid-api","other-repository:write"],
                 "scopes":["runtime:browser"],"expires_at":SANRO_QA_PILOT["expires_at"]}
        request={"action":"runtime","project":project,"projects":{project["id"]:project},"admission":{
                 "project_id":project["id"],"repository":project["repository"],"branch":"main",
                 "environment":"isolated-development","workspace":project["workspace"],"worker_id":"sanro-qa",
                 "permission_profile":permission,"command_profile":"local-ci","job_id":"sanroqa-pilot-job-001",
                 "checkpoint_sha":SANRO_QA_PILOT["source_sha"],"mandate_expires_at":SANRO_QA_PILOT["expires_at"]},
                 "mandate":mandate,"principal":principal,"profile_config":profile,
                 "approval_ref":SANRO_QA_PILOT["approval_id"],"idempotency_key":"sanroqa-pilot-job-001"}
        self.assertEqual(verify_bridge_admission(request)["worker_id"],"sanro-qa")
        request["mandate"]={**mandate,"allowed_actions":[*mandate["allowed_actions"],"engineering:execute"]}
        with self.assertRaisesRegex(PermissionError,"action scope"):
            verify_bridge_admission(request)


if __name__ == "__main__":
    unittest.main(verbosity=2)
