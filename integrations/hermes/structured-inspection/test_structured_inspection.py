"""Adversarial acceptance tests; fixture files contain synthetic data only."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hermes_inspection_adapter import TOOL_NAME, make_handler, register
from structured_inspection import StructuredInspection, parse_request


class _InspectionFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "sanro-inspection-metadata"
        self.root.mkdir(mode=0o700)
        self._write("backup-job-status.json", json.dumps({
            "state": "complete", "updated_at": "2026-11-24T10:00:00Z",
        }))
        self._write("restore-job-status.json", '{"state":"idle","updated_at":null}')
        self.service = StructuredInspection(self.root, {"operator-a"})
        self.request = {"version": 1, "operation": "inspect_metadata",
                        "resource": "backup-job-status", "fields": ["state"]}

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, name, data):
        path = self.root / name
        path.write_text(data)
        path.chmod(0o600)


class StructuredInspectionTests(_InspectionFixture):

    def test_authorized_metadata_only(self):
        result = self.service.inspect(self.request, principal="operator-a")
        self.assertEqual(result, {"ok": True, "resource": "backup-job-status",
                                  "fields": {"state": "complete"}})
        self.assertNotIn("updated_at", json.dumps(result))

    def test_unauthorized_principal_denied(self):
        self.assertEqual(self.service.inspect(self.request, principal="intruder"), {"ok": False, "error": "inspection_denied"})

    def test_arbitrary_and_sensitive_paths_are_not_schema_fields(self):
        for key, value in (("path", "/etc/shadow"), ("resource", "/etc/shadow")):
            request = dict(self.request)
            request[key] = value
            self.assertFalse(self.service.inspect(request, principal="operator-a")["ok"])

    def test_symlink_resource_denied(self):
        (self.root / "backup-job-status.json").unlink()
        outside = self.root.parent / "sensitive.json"
        outside.write_text('{"state":"secret-value","updated_at":"secret-time"}')
        os.symlink(outside, self.root / "backup-job-status.json")
        self.assertFalse(self.service.inspect(self.request, principal="operator-a")["ok"])

    def test_malformed_json_and_duplicate_keys_denied(self):
        self.assertFalse(parse_request("{", principal="operator-a", service=self.service)["ok"])
        raw = '{"version":1,"version":1,"operation":"inspect_metadata","resource":"backup-job-status","fields":["state"]}'
        self.assertFalse(parse_request(raw, principal="operator-a", service=self.service)["ok"])

    def test_unknown_keys_invalid_fields_and_wrong_types_denied(self):
        variants = [dict(self.request, command="tar -cf x"),
                    dict(self.request, fields=["state", "secret"]),
                    dict(self.request, fields=["updated_at"]),
                    dict(self.request, fields="state"),
                    dict(self.request, operation="restore"),
                    dict(self.request, version=True)]
        for request in variants:
            self.assertFalse(self.service.inspect(request, principal="operator-a")["ok"])

    def test_compound_operation_and_batch_are_rejected(self):
        self.assertFalse(self.service.inspect([self.request, self.request], principal="operator-a")["ok"])
        self.assertFalse(self.service.inspect(dict(self.request, operations=["inspect_metadata", "restore"]), principal="operator-a")["ok"])

    def test_sensitive_or_oversized_values_never_return(self):
        self._write("backup-job-status.json", json.dumps({"state": "x" * 129, "updated_at": None}))
        result = self.service.inspect(self.request, principal="operator-a")
        self.assertFalse(result["ok"])
        self._write("backup-job-status.json", "x" * 17000)
        self.assertFalse(self.service.inspect(self.request, principal="operator-a")["ok"])

    def test_sensitive_unregistered_file_invalidates_root(self):
        (self.root / "credentials.json").write_text('{"token":"synthetic"}')
        with self.assertRaises(ValueError):
            StructuredInspection(self.root, {"operator-a"})

    def test_sensitive_extra_fields_in_registered_file_are_denied(self):
        self._write("backup-job-status.json", '{"state":"complete","updated_at":null,"secret":"synthetic"}')
        self.assertFalse(self.service.inspect(self.request, principal="operator-a")["ok"])

    def test_sensitive_values_in_approved_fields_denied(self):
        self._write("backup-job-status.json", '{"state":"synthetic-secret","updated_at":"not-a-time"}')
        self.assertFalse(self.service.inspect(self.request, principal="operator-a")["ok"])


class HermesAdapterAcceptanceTests(_InspectionFixture):
    """Exercise supported ``register(ctx)`` contract without loading live Hermes."""

    def test_registered_handler_uses_host_uid_not_model_identity(self):
        uid = os.geteuid()
        service = StructuredInspection(self.root, {str(uid)})
        captured = {}

        class FakeContext:
            def register_tool(self, **kwargs):
                captured.update(kwargs)

        handler = make_handler(service, {uid}, uid_getter=lambda: uid)
        returned = handler(self.request, session_id="attacker-controlled-session",
                           principal="9999", user_id="9999")
        self.assertEqual(json.loads(returned)["ok"], True)
        self.assertEqual(json.loads(returned)["fields"]["state"], "complete")
        forged = handler(dict(self.request, principal="9999", user_id="9999"))
        self.assertFalse(json.loads(forged)["ok"])
        with patch.dict(os.environ, {
            "SANRO_INSPECTION_ROOT": str(self.root),
            "SANRO_INSPECTION_AUTHORIZED_UIDS": str(uid),
        }):
            register(FakeContext())
        self.assertEqual(captured["name"], TOOL_NAME)
        self.assertEqual(captured["toolset"], "sanro_inspection")
        self.assertFalse(captured["schema"]["parameters"]["additionalProperties"])
        registered_result = json.loads(captured["handler"](self.request, session_id="model-controlled"))
        self.assertTrue(registered_result["ok"])

    def test_unapproved_host_uid_and_misconfigured_adapter_deny(self):
        handler = make_handler(self.service, {os.geteuid()}, uid_getter=lambda: os.geteuid() + 1)
        self.assertFalse(json.loads(handler(self.request))["ok"])

        captured = {}

        class FakeContext:
            def register_tool(self, **kwargs):
                captured.update(kwargs)

        with patch.dict(os.environ, {}, clear=True):
            register(FakeContext())
        self.assertFalse(json.loads(captured["handler"](self.request))["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
