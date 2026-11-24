"""Service-side producer for the inspection candidate's non-sensitive metadata.

This module is not registered as a tool. Callers can submit only a fixed job
class and coarse status enum; paths, timestamps, names, messages, and payloads
cannot be supplied by callers.
"""
from __future__ import annotations

import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

_FILES = {
    "backup": "backup-job-status.json",
    "restore": "restore-job-status.json",
}
_STATES = frozenset({"idle", "queued", "running", "complete", "failed", "unknown"})
_ROOT_NAME = "sanro-inspection-metadata"


def _check_directory(root: Path, uid: int) -> None:
    if root.is_symlink() or root.name != _ROOT_NAME:
        raise ValueError("invalid metadata root")
    info = root.stat(follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or info.st_mode & 0o077:
        raise ValueError("unsafe metadata root")
    if any(entry.name not in _FILES.values() for entry in root.iterdir()):
        raise ValueError("unexpected metadata file")


def create_metadata_root(root: str | os.PathLike[str], *, uid_getter: Callable[[], int] = os.geteuid) -> Path:
    """Create the dedicated directory if absent; never repair or follow an unsafe path."""
    path = Path(root)
    if not path.is_absolute() or path.name != _ROOT_NAME or path.is_symlink():
        raise ValueError("invalid metadata root")
    created = False
    try:
        path.mkdir(mode=0o700)
        created = True
    except FileExistsError:
        pass
    if created:
        path.chmod(0o700, follow_symlinks=False)
    _check_directory(path, uid_getter())
    return path


class MetadataProducer:
    """Write only a fixed resource, coarse state enum, and producer clock timestamp."""

    def __init__(self, root: str | os.PathLike[str], *, uid_getter: Callable[[], int] = os.geteuid,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self._root = Path(root)
        self._uid_getter = uid_getter
        self._clock = clock
        _check_directory(self._root, self._uid_getter())

    def update(self, job: str, state: str) -> None:
        if not isinstance(job, str) or job not in _FILES or not isinstance(state, str) or state not in _STATES:
            raise ValueError("invalid metadata update")
        _check_directory(self._root, self._uid_getter())
        timestamp = self._clock()
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
            raise ValueError("producer clock must return an aware datetime")
        record = {"state": state, "updated_at": timestamp.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
        encoded = json.dumps(record, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        target = self._root / _FILES[job]
        if target.exists() or target.is_symlink():
            info = target.stat(follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != self._uid_getter() or info.st_mode & 0o077:
                raise ValueError("unsafe metadata file")

        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=self._root)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                fd = -1
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            if self._uid_getter() != os.geteuid():
                raise ValueError("host identity changed")
            os.replace(temporary, target)
            directory_fd = os.open(self._root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if fd >= 0:
                os.close(fd)
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


__all__ = ["MetadataProducer", "create_metadata_root"]
