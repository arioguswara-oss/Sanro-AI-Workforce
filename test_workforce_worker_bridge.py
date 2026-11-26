import unittest

from workforce_worker_bridge import verify_bridge_admission


class BridgeAdmissionTests(unittest.TestCase):
    def test_bridge_fails_closed_before_executor_without_registered_admission(self):
        request = {"project": {"id": "pilot"}, "projects": {}}
        with self.assertRaisesRegex(PermissionError, "validated project admission"):
            verify_bridge_admission(request)


if __name__ == "__main__":
    unittest.main(verbosity=2)
