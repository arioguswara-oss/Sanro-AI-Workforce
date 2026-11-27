"""Synthetic tests for the isolated, host-side status producer and plugin loading."""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from hermes_inspection_adapter import TOOL_NAME
from metadata_producer import MetadataProducer, create_metadata_root

WORKSPACE = Path(__file__).resolve().parent


class MetadataProducerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "sanro-inspection-metadata"
        create_metadata_root(self.root)
        self.clock = lambda: datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
        self.producer = MetadataProducer(self.root, clock=self.clock)

    def tearDown(self):
        self.temp.cleanup()

    def test_writes_only_coarse_allowlisted_status_and_producer_timestamp(self):
        self.producer.update("backup", "complete")
        record = json.loads((self.root / "backup-job-status.json").read_text())
        self.assertEqual(record, {"state": "complete", "updated_at": "2026-11-24T12:00:00Z"})
        self.assertEqual(set(record), {"state", "updated_at"})
        self.assertEqual((self.root / "backup-job-status.json").stat().st_mode & 0o777, 0o600)

    def test_rejects_unknown_job_state_and_caller_supplied_details(self):
        for job, state in (("customer-project", "complete"), ("backup", "secret=synthetic"),
                           ("restore", "complete\nprivate")):
            with self.assertRaises(ValueError):
                self.producer.update(job, state)

    def test_rejects_extra_files_and_symlink_destinations(self):
        (self.root / "private.json").write_text('{"token":"synthetic"}')
        with self.assertRaises(ValueError):
            self.producer.update("backup", "running")
        (self.root / "private.json").unlink()
        target = Path(self.temp.name) / "outside.json"
        target.write_text('{"state":"idle"}')
        os.symlink(target, self.root / "backup-job-status.json")
        with self.assertRaises(ValueError):
            self.producer.update("backup", "running")
        self.assertEqual(json.loads(target.read_text()), {"state": "idle"})

    def test_refuses_symlink_root_and_unsafe_permissions(self):
        link = Path(self.temp.name) / "sanro-inspection-metadata-link"
        os.symlink(self.root, link)
        with self.assertRaises(ValueError):
            create_metadata_root(link)
        self.root.chmod(0o750)
        with self.assertRaises(ValueError):
            MetadataProducer(self.root)


class HermesPluginLoadAcceptanceTests(unittest.TestCase):
    def test_candidate_loads_as_isolated_hermes_directory_plugin(self):
        """Mirror Hermes _load_directory_module; no live registry or Gateway is touched."""
        with tempfile.TemporaryDirectory() as temp:
            plugin_root = Path(temp) / "plugins" / "sanro-structured-inspection"
            plugin_root.mkdir(parents=True)
            (plugin_root / "plugin.yaml").write_bytes((WORKSPACE / "plugin.yaml").read_bytes())
            shutil.copyfile(WORKSPACE / "hermes_inspection_adapter.py", plugin_root / "__init__.py")
            shutil.copyfile(WORKSPACE / "structured_inspection.py", plugin_root / "structured_inspection.py")
            metadata_root = Path(temp) / "sanro-inspection-metadata"
            metadata_root.mkdir(mode=0o700)
            status = metadata_root / "backup-job-status.json"
            status.write_text('{"state":"unknown","updated_at":"2026-11-24T12:00:00Z"}')
            status.chmod(0o600)
            restore = metadata_root / "restore-job-status.json"
            restore.write_text('{"state":"idle","updated_at":null}')
            restore.chmod(0o600)

            module_name = "hermes_plugins.jd03e_synthetic"
            spec = importlib.util.spec_from_file_location(
                module_name, plugin_root / "__init__.py", submodule_search_locations=[str(plugin_root)])
            self.assertIsNotNone(spec)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
                captured = {}

                class FakePluginContext:
                    def register_tool(self, **kwargs):
                        captured.update(kwargs)

                with patch.dict(os.environ, {
                    "SANRO_INSPECTION_ROOT": str(metadata_root),
                    "SANRO_INSPECTION_AUTHORIZED_UIDS": str(os.geteuid()),
                }):
                    module.register(FakePluginContext())
                self.assertEqual(captured["name"], TOOL_NAME)
                result = json.loads(captured["handler"]({
                    "version": 1, "operation": "inspect_metadata", "resource": "backup-job-status",
                    "fields": ["state"],
                }))
                self.assertEqual(result["fields"], {"state": "unknown"})
            finally:
                sys.modules.pop(module_name, None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
