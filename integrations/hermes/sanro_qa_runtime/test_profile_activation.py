from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from integrations.hermes.sanro_qa_runtime import profile_activation as activation


class ProfileActivationTests(unittest.TestCase):
    def test_stage_is_idempotent_and_copies_only_plugin_runtime_files(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / ".hermes" / "profiles" / "sanro-qa"
            (home / "plugins").mkdir(parents=True)
            src = Path(activation.__file__).parent
            target = activation.stage(src, home)
            self.assertEqual(set(p.name for p in target.iterdir()), set(activation.FILES))
            self.assertEqual(activation.stage(src, home), target)
            self.assertEqual((target / "client.py").stat().st_mode & 0o777, 0o600)

    def test_stage_refuses_conflicting_content_and_symlink_target(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "sanro-qa"
            plugin_root = home / "plugins"
            plugin_root.mkdir(parents=True)
            target = plugin_root / activation.PLUGIN_NAME
            target.mkdir()
            (target / "plugin.yaml").write_text("unreviewed")
            with self.assertRaisesRegex(ValueError, "different content"):
                activation.stage(Path(activation.__file__).parent, home)

    def test_profile_path_is_exact_existing_named_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            fake_home = Path(temp)
            expected = fake_home / ".hermes" / "profiles" / "sanro-qa"
            expected.mkdir(parents=True)
            with patch.object(activation.Path, "home", return_value=fake_home):
                self.assertEqual(activation.profile_home(None), expected)
                with self.assertRaisesRegex(ValueError, "existing sanro-qa"):
                    activation.profile_home(str(fake_home / "other-profile"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
