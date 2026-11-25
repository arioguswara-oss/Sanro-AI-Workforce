import unittest

from workforce_worker_bridge import require_codex_no_daemon


class CodexForegroundModeTests(unittest.TestCase):
    def test_codex_profile_adds_no_daemon_immediately_after_executable(self):
        profile = {"executor": "codex", "command": ["/home/sanro/.local/bin/codex", "exec", "{workforce_instruction}"]}
        require_codex_no_daemon(profile)
        self.assertEqual(profile["command"], ["/home/sanro/.local/bin/codex", "--no-daemon", "exec", "{workforce_instruction}"])

    def test_codex_flag_is_not_duplicated(self):
        profile = {"executor": "codex", "command": ["codex", "--no-daemon", "exec", "task"]}
        require_codex_no_daemon(profile)
        self.assertEqual(profile["command"].count("--no-daemon"), 1)

    def test_non_codex_profiles_are_unchanged(self):
        profile = {"executor": "local-ci", "command": ["pytest", "-q"]}
        require_codex_no_daemon(profile)
        self.assertEqual(profile["command"], ["pytest", "-q"])

    def test_codex_executor_cannot_hide_a_wrapper_as_the_cli(self):
        profile = {"executor": "codex", "command": ["python3", "codex-wrapper.py"]}
        with self.assertRaisesRegex(PermissionError, "invoke the Codex CLI directly"):
            require_codex_no_daemon(profile)


if __name__ == "__main__":
    unittest.main()
