"""Synthetic contract tests for Hermes v0.22 directory-plugin integration."""
from __future__ import annotations

import importlib
import json
import unittest
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

from integrations.hermes.sanro_qa_runtime import client


class Response:
    def __init__(self, body, status=200):
        self.status = status
        self.body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit):
        return self.body[:limit]


class Context:
    def __init__(self):
        self.tools = []
        self.hooks = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)

    def register_hook(self, *args, **kwargs):
        self.hooks.append((args, kwargs))


class HermesQAPluginTests(unittest.TestCase):
    def test_manifest_declares_profile_local_secret_prompting(self):
        manifest = Path(__file__).with_name("plugin.yaml").read_text()
        self.assertIn('requires_hermes: ">=0.22.0"', manifest)
        self.assertIn("name: SANRO_QA_WORKFORCE_BEARER_TOKEN\n    secret: true", manifest)
        self.assertIn("name: SANRO_QA_APPROVAL_REF\n    secret: true", manifest)

    def test_register_uses_v022_directory_plugin_tool_contract_without_hooks(self):
        plugin = importlib.import_module("integrations.hermes.sanro_qa_runtime")
        ctx = Context()
        plugin.register(ctx)
        self.assertEqual([tool["name"] for tool in ctx.tools], [
            "sanro_qa_browser_smoke", "sanro_qa_private_browser_acceptance",
        ])
        self.assertEqual(ctx.hooks, [])
        for tool in ctx.tools:
            schema = tool["schema"]["parameters"]
            self.assertTrue(schema["additionalProperties"] is False)
            self.assertEqual(set(schema["properties"]), {"version", "job_id"})
            self.assertEqual(tool["toolset"], "sanro_qa_runtime")

    def test_missing_profile_token_or_approval_fails_closed_without_request(self):
        calls = []
        handler = client.make_handler("sanro-qa-browser-smoke", environ={}, opener=lambda *a, **k: calls.append(a))
        self.assertEqual(json.loads(handler({"version": 1, "job_id": "job-qa-0001"}))["code"], "runtime_not_configured")
        self.assertEqual(calls, [])
        handler = client.make_handler("sanro-qa-browser-smoke", environ={
            "SANRO_QA_WORKFORCE_BEARER_TOKEN": "synthetic-token-123456",
        }, opener=lambda *a, **k: calls.append(a))
        self.assertEqual(json.loads(handler({"version": 1, "job_id": "job-qa-0001"}))["code"], "approval_not_configured")
        self.assertEqual(calls, [])

    def test_rejects_extra_fields_invalid_job_and_bool_version(self):
        handler = client.make_handler("sanro-qa-browser-smoke", environ={})
        for args in (
            {"version": 1, "job_id": "job-qa-0001", "command": "id"},
            {"version": True, "job_id": "job-qa-0001"},
            {"version": 1, "job_id": "short"},
        ):
            with self.subTest(args=args):
                self.assertEqual(json.loads(handler(args))["code"], "invalid_request")

    def test_posts_fixed_project_profile_and_returns_only_sanitized_result(self):
        env = {"SANRO_QA_WORKFORCE_BEARER_TOKEN": "synthetic-token-not-real",
               "SANRO_QA_APPROVAL_REF": "approval-qa-synthetic"}
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["auth"] = request.get_header("Authorization")
            captured["timeout"] = timeout
            captured["payload"] = json.loads(request.data)
            return Response({"status": "PASS", "job_id": "job-qa-0001",
                             "project_id": client.PROJECT_ID, "operation": "browser_smoke",
                             "secret": "should-not-escape"})

        result = client.make_handler("sanro-qa-browser-smoke", environ=env, opener=opener)(
            {"version": 1, "job_id": "job-qa-0001"})
        self.assertEqual(captured["url"], client.API_URL + client.API_PATH)
        self.assertEqual(captured["auth"], "Bearer synthetic-token-not-real")
        self.assertEqual(captured["payload"], {"profile": "sanro-browser-qa-browser-smoke",
                                               "approval_ref": "approval-qa-synthetic",
                                               "idempotency_key": "job-qa-0001"})
        self.assertEqual(captured["timeout"], 150)
        self.assertEqual(json.loads(result), {"status": "PASS", "job_id": "job-qa-0001",
                                              "project_id": client.PROJECT_ID, "operation": "browser_smoke"})
        self.assertNotIn("synthetic-token", result)
        self.assertNotIn("should-not-escape", result)

    def test_private_browser_tool_selects_only_fixed_private_operation(self):
        env = {"SANRO_QA_WORKFORCE_BEARER_TOKEN": "synthetic-token-not-real",
               "SANRO_QA_APPROVAL_REF": "approval-qa-synthetic"}
        captured = {}

        def opener(request, timeout):
            captured["payload"] = json.loads(request.data)
            captured["timeout"] = timeout
            return Response({"status": "BLOCKED", "job_id": "job-qa-0002",
                             "project_id": client.PROJECT_ID,
                             "operation": "private_browser_acceptance"}, status=503)

        result = client.make_handler("sanro-qa-private-browser-acceptance", environ=env, opener=opener)(
            {"version": 1, "job_id": "job-qa-0002"})
        self.assertEqual(captured["payload"]["profile"], "sanro-browser-qa-private-browser-acceptance")
        self.assertEqual(captured["timeout"], 300)
        self.assertEqual(json.loads(result)["operation"], "private_browser_acceptance")

    def test_runtime_fail_and_blocked_statuses_are_preserved_sanitized(self):
        env = {"SANRO_QA_WORKFORCE_BEARER_TOKEN": "synthetic-token-not-real",
               "SANRO_QA_APPROVAL_REF": "approval-qa-synthetic"}
        for status, http_code in (("FAIL", 422), ("BLOCKED", 503)):
            body = json.dumps({"status": status, "job_id": "job-qa-result-1",
                               "project_id": client.PROJECT_ID, "operation": "browser_smoke",
                               "diagnostic": "private host detail"}).encode()
            def rejected(request, timeout, body=body, http_code=http_code):
                raise HTTPError(request.full_url, http_code, "runtime result", {}, BytesIO(body))
            result = client.make_handler("sanro-qa-browser-smoke", environ=env, opener=rejected)(
                {"version": 1, "job_id": "job-qa-result-1"})
            self.assertEqual(json.loads(result)["status"], status)
            self.assertNotIn("private host detail", result)

    def test_profile_operation_mismatch_redirect_and_unavailable_api_fail_closed(self):
        env = {"SANRO_QA_WORKFORCE_BEARER_TOKEN": "synthetic-token-not-real",
               "SANRO_QA_APPROVAL_REF": "approval-qa-synthetic"}
        mismatch = client.make_handler("sanro-qa-browser-smoke", environ=env,
            opener=lambda *_a, **_k: Response({"status": "PASS", "job_id": "job-qa-0003",
                "project_id": client.PROJECT_ID, "operation": "private_browser_acceptance"}))
        self.assertEqual(json.loads(mismatch({"version": 1, "job_id": "job-qa-0003"}))["code"], "profile_operation_mismatch")

        def redirect(*_args, **_kwargs):
            error = HTTPError(client.API_URL + client.API_PATH, 302, "redirect", {}, BytesIO())
            error.close()
            raise error
        redirected = client.make_handler("sanro-qa-browser-smoke", environ=env, opener=redirect)
        self.assertEqual(json.loads(redirected({"version": 1, "job_id": "job-qa-0004"}))["code"], "runtime_unavailable")
        unavailable = client.make_handler("sanro-qa-browser-smoke", environ=env,
                                          opener=lambda *_a, **_k: (_ for _ in ()).throw(OSError("synthetic")))
        result = unavailable({"version": 1, "job_id": "job-qa-0005"})
        self.assertEqual(json.loads(result)["code"], "runtime_unavailable")
        self.assertNotIn("synthetic", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
