import json
import os
import tempfile
import unittest
from pathlib import Path

from model_routing import FreeOnlyRouter, FreeRoute, RouteRejected
from provider_adapters import FreeModelEngine, OpenAICompatibleProvider, ProviderFailure, ProviderResponse


class ProviderAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.routes = [
            FreeRoute("9router", "free-chat-a", "http://127.0.0.1:20128/v1", "TEST_9ROUTER_KEY", 0, "verified", False, 60),
            FreeRoute("freellmapi", "free-chat-b", "http://localhost:3001/v1", "TEST_FREELLMAPI_KEY", 0, "verified", False, 60),
        ]
        os.environ["TEST_9ROUTER_KEY"] = "synthetic-token-a"
        os.environ["TEST_FREELLMAPI_KEY"] = "synthetic-token-b"
        self.addCleanup(lambda: os.environ.pop("TEST_9ROUTER_KEY", None))
        self.addCleanup(lambda: os.environ.pop("TEST_FREELLMAPI_KEY", None))
        self.router = FreeOnlyRouter(self.routes, Path(self.temp.name) / "routing.json")
        self.checkpoint = Path(self.temp.name) / "request-checkpoint.json"

    def test_openai_compat_fallback_and_fair_failback(self):
        calls = []
        def transport(url, headers, body, timeout):
            calls.append((url, headers, json.loads(body)))
            if "20128" in url:
                return ProviderResponse(429, b'{"error":"quota"}', {"Retry-After": "120"})
            return ProviderResponse(200, json.dumps({"choices":[{"message":{"role":"assistant","content":"mocked answer"}}]}).encode(), {})
        providers = {route.provider_id: OpenAICompatibleProvider(route, transport=transport) for route in self.routes}
        engine = FreeModelEngine(self.router, providers, self.checkpoint)
        messages = [{"role":"user","content":"synthetic request with private-looking token sk-fake-token"}]
        result = engine.complete(messages, request_id="conversation-1")
        self.assertEqual(result["choices"][0]["message"]["content"], "mocked answer")
        self.assertEqual([call[0] for call in calls], ["http://127.0.0.1:20128/v1/chat/completions", "http://localhost:3001/v1/chat/completions"])
        self.assertEqual(calls[0][1]["authorization"], "Bearer synthetic-token-a")
        self.assertGreater(self.router._state["cooldowns"][self.router._key(self.routes[0])], 0)
        checkpoint = self.checkpoint.read_text()
        self.assertNotIn("private-looking", checkpoint)
        self.assertEqual((self.checkpoint.stat().st_mode & 0o777), 0o600)
        # A recovered route is preferred again at the next safe request boundary.
        self.router._state["cooldowns"][self.router._key(self.routes[0])] = 0
        self.router._save()
        engine.complete(messages, request_id="conversation-2")
        self.assertEqual(calls[-2][0], "http://127.0.0.1:20128/v1/chat/completions")

    def test_checkpoint_pause_resume_and_engineering_executor_separation(self):
        self.router.record_quota(self.routes[0], retry_after_seconds=300)
        self.router.record_quota(self.routes[1], retry_after_seconds=300)
        provider = OpenAICompatibleProvider(self.routes[0], transport=lambda *_: ProviderResponse(200,b'{"choices":[{"message":{"content":"ok"}}]}',{}))
        engine = FreeModelEngine(self.router, {"9router":provider,"freellmapi":provider}, self.checkpoint)
        with self.assertRaises(RouteRejected):
            engine.complete([{"role":"user","content":"x"}], request_id="paused-1")
        self.assertEqual(json.loads(self.checkpoint.read_text())["requests"]["paused-1"]["status"], "PAUSED")
        self.assertFalse(engine.resume_eligible("paused-1"))
        with self.assertRaises(RouteRejected):
            engine.complete([{"role":"user","content":"x"}], request_id="engineering-1", engineering=True)
        for route in self.routes:
            self.router._state["cooldowns"][self.router._key(route)] = 0
        self.router._save()
        self.assertTrue(engine.resume_eligible("paused-1"))
        self.assertEqual(engine.resume([{"role":"user","content":"x"}], request_id="paused-1")["choices"][0]["message"]["content"], "ok")

    def test_tool_calls_require_reliable_engineering_route_and_api_errors_are_bounded(self):
        untrusted = FreeRoute("unverified", "weak", "https://router.invalid/v1", "MISSING_KEY", 0, "unverified", True)
        self.assertRaises(RouteRejected, untrusted.validate)
        calls = []
        provider = OpenAICompatibleProvider(self.routes[0], transport=lambda *args: calls.append(args))
        self.assertRaises(RouteRejected, provider.complete, [{"role":"user","content":"run"}], tools=[{"type":"function"}])
        self.assertEqual(calls, [])
        no_key = FreeRoute("no-key", "model", "https://router.invalid/v1", "MISSING_KEY", 0, "verified", False)
        with self.assertRaises(ProviderFailure) as caught:
            OpenAICompatibleProvider(no_key).complete([{"role":"user","content":"x"}])
        self.assertEqual(caught.exception.status, 401)


if __name__ == "__main__":
    unittest.main()
