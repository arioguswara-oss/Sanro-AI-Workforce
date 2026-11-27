#!/usr/bin/env python3
"""Synthetic black-box regression coverage for approval_gate.py.

The harness records current classifier behavior and proposed safe outcomes.
It does not execute any command contained in a test payload.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

GATE = Path(__file__).with_name("approval_gate.py")


def classify(command=None, **payload_overrides):
    payload = {
        "hook_event_name": "pre_tool_call",
        "tool_name": "terminal",
        "tool_call_id": "synthetic-call-01",
        "session_id": "synthetic-session-01",
        "tool_input": {"command": command},
    }
    payload.update(payload_overrides)
    proc = subprocess.run(
        [sys.executable, str(GATE)], input=json.dumps(payload), text=True,
        capture_output=True, check=False,
    )
    return proc.returncode, json.loads(proc.stdout)


class ApprovalGateRegression(unittest.TestCase):
    def assert_approval(self, command):
        code, result = classify(command)
        self.assertEqual(code, 0)
        self.assertEqual(result.get("action"), "approve")
        self.assertTrue(result.get("rule_key", "").startswith("sanro-backup-once-"))

    def assert_no_approval(self, command):
        code, result = classify(command)
        self.assertEqual(code, 0)
        self.assertNotEqual(result.get("action"), "approve")

    def test_routine_inspection_keyword_false_positive(self):
        # Current behavior is intentionally captured; proposal should classify as no-op.
        self.assert_approval("grep -n 'backup restore transfer' README.md")

    def test_configuration_metadata_false_positive(self):
        self.assert_approval("cat config.json | jq '.backup.enabled'")

    def test_sensitive_data_access_path(self):
        self.assert_approval("cat /home/example/.hermes/config.json")

    def test_backup_operation(self):
        self.assert_approval("tar -czf backup.tar.gz ./data")

    def test_restore_operation(self):
        self.assert_approval("sqlite3 app.db < restore.sql")

    def test_transfer_operation(self):
        self.assert_approval("rsync ./archive host:/srv/archive")

    def test_ambiguous_execution_wrapper(self):
        self.assert_approval("bash -c 'echo inspect'")

    def test_malformed_json_blocks(self):
        proc = subprocess.run([sys.executable, str(GATE)], input="{", text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout).get("action"), "block")

    def test_malformed_payload_shape_blocks(self):
        code, result = classify("ls", tool_input=None)
        self.assertEqual(code, 0)
        self.assertEqual(result.get("action"), "block")

    def test_compound_command_detects_risky_member(self):
        self.assert_approval("echo inspect; tar -cf /tmp/a.tar ./data")

    def test_rule_key_is_per_call(self):
        _, first = classify("tar -cf a.tar data")
        _, second = classify("tar -cf a.tar data", tool_call_id="synthetic-call-02")
        self.assertNotEqual(first["rule_key"], second["rule_key"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
