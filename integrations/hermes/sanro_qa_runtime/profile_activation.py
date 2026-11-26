"""Stage/enable/disable the reviewed plugin in the existing sanro-qa profile.

This helper is intentionally not run by development tests. Activation changes
only that profile's plugin registry and requires an explicit --activate call.
"""
from __future__ import annotations

import argparse
import filecmp
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


PLUGIN_NAME = "sanro-qa-runtime"
PROFILE_NAME = "sanro-qa"
FILES = ("plugin.yaml", "__init__.py", "client.py")


def profile_home(value: str | None) -> Path:
    expected = Path.home() / ".hermes" / "profiles" / PROFILE_NAME
    requested = Path(value) if value else expected
    if requested.is_symlink() or requested.absolute() != expected.absolute():
        raise ValueError("profile path must be the existing sanro-qa profile")
    actual = requested
    if not actual.is_dir() or actual.is_symlink():
        raise ValueError("existing sanro-qa profile directory is required")
    return actual


def stage(source: Path, home: Path) -> Path:
    plugin_root = home / "plugins"
    if not plugin_root.is_dir() or plugin_root.is_symlink():
        raise ValueError("existing profile plugins directory is required")
    target = plugin_root / PLUGIN_NAME
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise ValueError("plugin target is not a regular directory")
        if all((target / name).is_file() and not (target / name).is_symlink()
               and filecmp.cmp(source / name, target / name, shallow=False) for name in FILES):
            return target
        raise ValueError("plugin target exists with different content; refusing overwrite")
    with tempfile.TemporaryDirectory(prefix=".sanro-qa-stage-", dir=plugin_root) as temp:
        staged = Path(temp) / PLUGIN_NAME
        staged.mkdir(mode=0o700)
        for name in FILES:
            src = source / name
            if not src.is_file() or src.is_symlink():
                raise ValueError("plugin source is incomplete")
            shutil.copyfile(src, staged / name)
            os.chmod(staged / name, 0o600)
        staged.rename(target)
    return target


def hermes(profile: Path, *args: str) -> None:
    executable = shutil.which("hermes")
    if not executable:
        raise RuntimeError("Hermes CLI not found in PATH")
    result = subprocess.run([executable, "-p", PROFILE_NAME, *args],
                            cwd=profile, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            check=False, timeout=60)
    if result.returncode:
        raise RuntimeError("Hermes profile command failed; inspect locally without sharing secrets")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--stage", action="store_true", help="copy reviewed files only")
    action.add_argument("--activate", action="store_true", help="doctor then enable for sanro-qa only")
    action.add_argument("--rollback", action="store_true", help="disable plugin for sanro-qa only")
    parser.add_argument("--profile-home", help="defaults to ~/.hermes/profiles/sanro-qa")
    args = parser.parse_args()
    try:
        home = profile_home(args.profile_home)
        source = Path(__file__).resolve().parent
        target = home / "plugins" / PLUGIN_NAME
        if args.stage:
            stage(source, home)
        elif args.activate:
            target = stage(source, home)
            hermes(home, "plugins", "doctor", str(target), "--ci")
            hermes(home, "plugins", "enable", PLUGIN_NAME)
        else:
            hermes(home, "plugins", "disable", PLUGIN_NAME)
        print("sanro-qa plugin operation completed")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        print("sanro-qa plugin operation blocked; no secret or runtime detail emitted", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
