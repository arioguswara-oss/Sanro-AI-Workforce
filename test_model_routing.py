import tempfile
import unittest
from pathlib import Path

from model_routing import FreeOnlyRouter, FreeRoute, RouteRejected


class FreeOnlyRouterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.checkpoint = Path(self.temp.name) / "route-state.json"
        self.primary = FreeRoute("local-gateway", "free-a", "http://127.0.0.1:8080/v1", "LOCAL_KEY", 0,
                                 reliability="verified", engineering_tools=True, quota_cooldown_seconds=45)
        self.secondary = FreeRoute("local-gateway", "free-b", "http://127.0.0.1:8080/v1", "LOCAL_KEY", 0, reliability="verified")

    def tearDown(self):
        self.temp.cleanup()

    def test_free_route_selection_and_hermes_shape(self):
        router = FreeOnlyRouter([self.primary, self.secondary], self.checkpoint)
        self.assertEqual(router.choose(), self.primary)
        self.assertEqual(router.hermes_fallback_entries(), [
            {"provider": "custom", "model": "free-a", "base_url": "http://127.0.0.1:8080/v1", "key_env": "LOCAL_KEY"},
            {"provider": "custom", "model": "free-b", "base_url": "http://127.0.0.1:8080/v1", "key_env": "LOCAL_KEY"},
        ])

    def test_quota_cooldown_checkpoint_recovery_and_failback(self):
        router = FreeOnlyRouter([self.primary, self.secondary], self.checkpoint)
        router.record_quota(self.primary, retry_after_seconds=12, now=100)
        self.assertEqual(router.choose(now=101), self.secondary)
        resumed = FreeOnlyRouter([self.primary, self.secondary], self.checkpoint)
        self.assertEqual(resumed.choose(now=111), self.secondary)
        self.assertEqual(resumed.choose(now=112), self.primary)

    def test_engineering_tools_only_on_explicitly_verified_route(self):
        router = FreeOnlyRouter([self.primary, self.secondary], self.checkpoint)
        self.assertEqual(router.choose(engineering_tools=True), self.primary)
        router.record_quota(self.primary, now=100)
        with self.assertRaises(RouteRejected):
            router.choose(engineering_tools=True, now=101)

    def test_paid_unknown_cost_and_non_tls_remote_routes_rejected(self):
        for cost, endpoint in [(0.01, "https://router.example/v1"), (0, "http://router.example/v1")]:
            with self.subTest(cost=cost, endpoint=endpoint), self.assertRaises(RouteRejected):
                FreeOnlyRouter([FreeRoute("x", "m", endpoint, "KEY", cost)], self.checkpoint)

    def test_duplicate_routes_rejected(self):
        with self.assertRaises(RouteRejected):
            FreeOnlyRouter([self.primary, self.primary], self.checkpoint)

    def test_workload_capabilities_filter_routes_and_keep_engineering_on_codex(self):
        router = FreeOnlyRouter([self.primary, self.secondary], self.checkpoint)
        self.assertEqual(router.choose(capabilities={"summarization"}), self.primary)
        self.assertEqual(router.choose(capabilities={"monitoring"}), self.primary)
        self.assertEqual(router.choose(capabilities={"simple_text_processing"}), self.primary)
        with self.assertRaises(RouteRejected):
            router.choose(capabilities={"runtime_orchestration"})
        with self.assertRaises(RouteRejected):
            router.choose(capabilities={"engineering"})
        qualified = FreeRoute("qualified", "tools", "https://tools.example/v1", "TOOLS_KEY", 0,
                              "verified", True, 60, frozenset({"structured_tool_calling", "summarization"}))
        self.assertEqual(FreeOnlyRouter([qualified], self.checkpoint).choose(capabilities={"structured_tool_calling"}), qualified)
        orchestrator = FreeRoute("orchestrator", "plan", "https://orchestrator.example/v1", "PLAN_KEY", 0,
                                 "verified", False, 60, frozenset({"runtime_orchestration", "monitoring", "summarization", "simple_text_processing"}))
        routed = FreeOnlyRouter([orchestrator], self.checkpoint)
        for capability in orchestrator.capabilities:
            self.assertEqual(routed.choose(capabilities={capability}), orchestrator)


if __name__ == "__main__":
    unittest.main()
