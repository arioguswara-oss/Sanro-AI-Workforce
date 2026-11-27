"""Isolated, read-only metadata inspection candidate.

This module is not connected to Hermes or exposed as a live tool. The caller
must obtain ``principal`` from trusted authentication middleware. ``root`` and
the authorization list are trusted service configuration, never request data.
"""
from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from typing import Any, Mapping

MAX_FILE_BYTES = 16_384
MAX_RESPONSE_BYTES = 2_048
_GENERIC_DENY = {"ok": False, "error": "inspection_denied"}
_REGISTRY: Mapping[str, tuple[str, frozenset[str]]] = {
    # These fixed logical resources expose only operational status metadata.
    # updated_at is retained locally by the producer but deliberately not caller-visible.
    "backup-job-status": ("backup-job-status.json", frozenset({"state"})),
    "restore-job-status": ("restore-job-status.json", frozenset({"state"})),
}
_REQUEST_KEYS = frozenset({"version", "operation", "resource", "fields"})
_STATE_VALUES = frozenset({"idle", "queued", "running", "complete", "failed", "unknown"})
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_REGISTERED_FILES = frozenset(path for path, _fields in _REGISTRY.values())


class StructuredInspection:
    """Read explicitly allowlisted metadata from fixed files under a trusted root."""

    def __init__(self, root: str | os.PathLike[str], authorized_principals: set[str] | frozenset[str]):
        # Resolve once at trusted construction time. Requests cannot influence this path.
        self._root = Path(root).resolve(strict=True)
        root_stat = self._root.stat()
        if (not stat.S_ISDIR(root_stat.st_mode) or root_stat.st_uid != os.geteuid()
                or root_stat.st_mode & 0o077):
            raise ValueError("inspection root must be a directory")
        if any(entry.name not in _REGISTERED_FILES for entry in self._root.iterdir()):
            raise ValueError("inspection root contains an unregistered file")
        self._authorized = frozenset(p for p in authorized_principals if isinstance(p, str) and p)

    def inspect(self, request: Any, *, principal: str) -> dict[str, Any]:
        """Return bounded metadata or a generic deny; never returns source file contents."""
        try:
            return self._inspect(request, principal)
        except Exception:
            # Keep filesystem details, parse errors, and request values private.
            return dict(_GENERIC_DENY)

    def _inspect(self, request: Any, principal: str) -> dict[str, Any]:
        if not isinstance(principal, str) or principal not in self._authorized:
            return dict(_GENERIC_DENY)
        if not isinstance(request, dict) or set(request) != _REQUEST_KEYS:
            return dict(_GENERIC_DENY)
        if type(request["version"]) is not int or request["version"] != 1 or request["operation"] != "inspect_metadata":
            return dict(_GENERIC_DENY)
        resource = request["resource"]
        fields = request["fields"]
        if not isinstance(resource, str) or resource not in _REGISTRY:
            return dict(_GENERIC_DENY)
        if (not isinstance(fields, list) or not fields or len(fields) > 2
                or any(not isinstance(field, str) for field in fields)
                or len(set(fields)) != len(fields)):
            return dict(_GENERIC_DENY)
        filename, allowed_fields = _REGISTRY[resource]
        if any(field not in allowed_fields for field in fields):
            return dict(_GENERIC_DENY)

        # The registry contains single fixed basenames. O_NOFOLLOW blocks symlink swaps.
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(self._root / filename, flags)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES
                    or info.st_uid != os.geteuid() or info.st_mode & 0o077):
                return dict(_GENERIC_DENY)
            chunks = bytearray()
            while len(chunks) <= MAX_FILE_BYTES:
                block = os.read(fd, min(4096, MAX_FILE_BYTES + 1 - len(chunks)))
                if not block:
                    break
                chunks.extend(block)
            if len(chunks) > MAX_FILE_BYTES:
                return dict(_GENERIC_DENY)
        finally:
            os.close(fd)

        record = json.loads(chunks.decode("utf-8"))
        if not isinstance(record, dict) or set(record) != {"state", "updated_at"}:
            return dict(_GENERIC_DENY)
        stamp = record["updated_at"]
        if stamp is not None and (not isinstance(stamp, str) or not _TIMESTAMP.fullmatch(stamp)):
            return dict(_GENERIC_DENY)
        # Values are restricted to short scalar metadata; no nested records or blobs.
        result_fields: dict[str, str | int | bool | None] = {}
        for field in fields:
            value = record.get(field)
            if field == "state" and value not in _STATE_VALUES:
                return dict(_GENERIC_DENY)
            result_fields[field] = value
        response = {"ok": True, "resource": resource, "fields": result_fields}
        if len(json.dumps(response, separators=(",", ":"), ensure_ascii=True).encode("ascii")) > MAX_RESPONSE_BYTES:
            return dict(_GENERIC_DENY)
        return response


def parse_request(raw: str | bytes, *, principal: str, service: StructuredInspection) -> dict[str, Any]:
    """Strict JSON boundary helper. Duplicate keys and malformed JSON deny generically."""
    try:
        if isinstance(raw, bytes):
            if len(raw) > 4096:
                return dict(_GENERIC_DENY)
            raw = raw.decode("utf-8")
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > 4096:
            return dict(_GENERIC_DENY)

        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate key")
                result[key] = value
            return result

        request = json.loads(raw, object_pairs_hook=unique_object)
        return service.inspect(request, principal=principal)
    except Exception:
        return dict(_GENERIC_DENY)
