import importlib.util
import json
import pathlib
import sys
import tempfile
import time
import types
import unittest

PLUGIN_PATH = pathlib.Path(__file__).parent / ".hermes/plugins/jd04_engineering_worker/__init__.py"
SPEC = importlib.util.spec_from_file_location("jd04_project_plugin", PLUGIN_PATH)
PLUGIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLUGIN)


class FakePluginContext:
    def __init__(self, config):
        self.config = config
        self.tools = {}
        self.unload = None

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def on_unload(self, callback):
        self.unload = callback


class NativePluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jd04-native-")
        self.root = pathlib.Path(self.temp.name) / "plugin-root"
        self.state_root = pathlib.Path(self.temp.name) / "state"
        self.workspace = pathlib.Path(self.temp.name) / "project"
        self.workspace.mkdir()
        self.old_root = PLUGIN.ROOT
        self.old_state_root = PLUGIN.STATE_ROOT
        PLUGIN.ROOT = self.root
        PLUGIN.STATE_ROOT = self.state_root
        self.fake_modules = {}
        gateway = types.ModuleType("gateway"); gateway.__path__ = []
        session_context = types.ModuleType("gateway.session_context")
        session_values = {"HERMES_SESSION_PLATFORM": "telegram", "HERMES_SESSION_USER_ID": "1007",
                          "HERMES_SESSION_CHAT_ID": "chat-9", "HERMES_SESSION_KEY": "telegram:chat-9"}
        session_context.bound_session_env = lambda name: session_values.get(name, "")
        tools = types.ModuleType("tools"); tools.__path__ = []
        approval = types.ModuleType("tools.approval")
        approval.request_tool_approval = lambda *a, **kw: {"approved": True, "message": None}
        for name, module in (("gateway", gateway), ("gateway.session_context", session_context), ("tools", tools), ("tools.approval", approval)):
            self.fake_modules[name] = sys.modules.get(name)
            sys.modules[name] = module

    def test_plugin_root_resolves_workspace_for_hermes_directory_loader(self):
        self.assertEqual(self.old_root, PLUGIN_PATH.resolve().parents[3])
        self.assertTrue((self.old_root / "hermes_adapter.py").is_file())

    def tearDown(self):
        PLUGIN.ROOT = self.old_root
        PLUGIN.STATE_ROOT = self.old_state_root
        for name, original in self.fake_modules.items():
            if original is None: sys.modules.pop(name, None)
            else: sys.modules[name] = original
        self.temp.cleanup()

    def test_verified_register_tool_contract_and_scoped_job(self):
        ctx = FakePluginContext({"projects": {"proj-native": {
            "workspace": str(self.workspace), "telegram_user_ids": ["1007"],
            "scopes": ["engineering:execute", "engineering:read", "engineering:cancel"],
            "command_profiles": {"python": {"argv": [sys.executable, "-c"],
                "argument_pattern": r"^[A-Za-z0-9 ()'._-]{0,200}$"}},
        }}})
        PLUGIN.register(ctx)
        registered = ctx.tools["jd04_engineering_job"]
        self.assertEqual(registered["toolset"], "jd04_engineering_worker")
        submitted = json.loads(registered["handler"]({"action": "submit", "project_id": "proj-native",
            "profile": "python", "arguments": ["print('native-plugin-ok')"], "idempotency_key": "native-1"}))
        self.assertTrue(submitted["job_id"])
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = json.loads(registered["handler"]({"action": "status", "project_id": "proj-native", "job_id": submitted["job_id"]}))
            if status.get("status") == "COMPLETED": break
            time.sleep(.03)
        self.assertEqual(status["status"], "COMPLETED")
        self.assertEqual(status["notifications"][0]["event"], "COMPLETED")
        again = json.loads(registered["handler"]({"action": "status", "project_id": "proj-native", "job_id": submitted["job_id"]}))
        self.assertNotIn("notifications", again)
        output = json.loads(registered["handler"]({"action": "logs", "project_id": "proj-native", "job_id": submitted["job_id"]}))
        self.assertIn("native-plugin-ok", output["logs"])
        ctx.unload()

    def test_missing_telegram_identity_fails_closed(self):
        ctx = FakePluginContext({"projects": {"proj-native": {
            "workspace": str(self.workspace), "telegram_user_ids": ["1007"],
            "scopes": ["engineering:execute", "engineering:read", "engineering:cancel"],
            "command_profiles": {"python": {"argv": [sys.executable, "-c"]}},
        }}})
        PLUGIN.register(ctx)
        module = sys.modules["gateway.session_context"]
        module.bound_session_env = lambda name: ""
        response = json.loads(ctx.tools["jd04_engineering_job"]["handler"]({"action": "submit", "project_id": "proj-native",
            "profile": "python", "arguments": ["pass"], "idempotency_key": "unauth"}))
        self.assertIn("error", response)
        self.assertIn("identity", response["error"])
        ctx.unload()

    def test_denied_approval_prevents_submission(self):
        ctx = FakePluginContext({"projects": {"proj-native": {
            "workspace": str(self.workspace), "telegram_user_ids": ["1007"],
            "scopes": ["engineering:execute"],
            "command_profiles": {"python": {"argv": [sys.executable, "-c"]}},
        }}})
        PLUGIN.register(ctx)
        sys.modules["tools.approval"].request_tool_approval = lambda *a, **kw: {"approved": False, "message": "denied"}
        response = json.loads(ctx.tools["jd04_engineering_job"]["handler"]({"action": "submit", "project_id": "proj-native",
            "profile": "python", "arguments": ["pass"], "idempotency_key": "denied"}))
        self.assertEqual(response["status"], "approval_denied")
        self.assertFalse((self.root / "jobs.sqlite3").exists())
        ctx.unload()

    def test_profile_traversal_and_missing_scope_are_denied(self):
        ctx = FakePluginContext({"projects": {"proj-native": {
            "workspace": str(self.workspace), "telegram_user_ids": ["1007"],
            "scopes": ["engineering:execute"],
            "command_profiles": {"python": {"argv": [sys.executable, "-c"]}},
        }}})
        PLUGIN.register(ctx)
        handler = ctx.tools["jd04_engineering_job"]["handler"]
        traversal = json.loads(handler({"action": "submit", "project_id": "proj-native", "profile": "python",
            "arguments": ["../escape"], "idempotency_key": "traversal"}))
        self.assertIn("error", traversal)
        denied_read = json.loads(handler({"action": "notifications", "project_id": "proj-native"}))
        self.assertIn("error", denied_read)
        self.assertFalse((self.root / "jobs.sqlite3").exists())
        ctx.unload()


if __name__ == "__main__":
    unittest.main(verbosity=2)
