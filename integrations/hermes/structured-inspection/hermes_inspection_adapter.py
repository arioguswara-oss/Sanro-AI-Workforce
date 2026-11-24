"""Hermes standalone-plugin adapter for the isolated metadata inspector.

Hermes invokes ``register(ctx)`` and handlers receive model arguments plus
optional task/session kwargs. The installed registry does not supply an
authenticated user identity, so this adapter authorizes the host process's
effective UID, obtained directly from the OS and never from tool arguments.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

if __package__:
    from .structured_inspection import StructuredInspection
else:  # Direct workspace tests; Hermes loads this as a directory plugin package.
    from structured_inspection import StructuredInspection

TOOL_NAME = "sanro_inspect_metadata"
TOOLSET = "sanro_inspection"
DEFAULT_ROOT = ""  # Host must provide an approved isolated root via environment.
SCHEMA = {
    "name": TOOL_NAME,
    "description": "Read allowlisted, non-sensitive Backup/DR job status metadata.",
    "parameters": {
        "type": "object",
        "properties": {
            "version": {"type": "integer", "enum": [1]},
            "operation": {"type": "string", "enum": ["inspect_metadata"]},
            "resource": {"type": "string", "enum": ["backup-job-status", "restore-job-status"]},
            "fields": {"type": "array", "items": {"type": "string", "enum": ["state"]}, "minItems": 1, "maxItems": 1},
        },
        "required": ["version", "operation", "resource", "fields"],
        "additionalProperties": False,
    },
}


def make_handler(
    service: StructuredInspection,
    authorized_uids: set[int] | frozenset[int],
    *,
    uid_getter: Callable[[], int] = os.geteuid,
):
    """Build a handler whose identity source is the host OS, not model input."""
    allowed = frozenset(uid for uid in authorized_uids if type(uid) is int and uid >= 0)

    def handle(args: Any, **_hermes_context: Any) -> str:
        try:
            uid = uid_getter()
            if type(uid) is not int or uid not in allowed:
                return json.dumps({"ok": False, "error": "inspection_denied"}, separators=(",", ":"))
            result = service.inspect(args, principal=str(uid))
            return json.dumps(result, separators=(",", ":"), ensure_ascii=True)
        except Exception:
            return json.dumps({"ok": False, "error": "inspection_denied"}, separators=(",", ":"))

    return handle


def _trusted_uid_configuration(raw: str | None) -> frozenset[int]:
    """Parse administrator-supplied host config; reject empty, malformed, or duplicate IDs."""
    if not isinstance(raw, str) or not raw:
        return frozenset()
    parts = raw.split(",")
    if any(not part.isascii() or not part.isdecimal() or (len(part) > 1 and part.startswith("0")) for part in parts):
        return frozenset()
    values = [int(part) for part in parts]
    if any(value == 0 for value in values) or len(set(values)) != len(values):
        return frozenset()
    return frozenset(values)


def register(ctx: Any) -> None:
    """Hermes plugin entry point. Missing/unsafe host config registers a deny-only tool."""
    raw_root = os.environ.get("SANRO_INSPECTION_ROOT", DEFAULT_ROOT)
    uids = _trusted_uid_configuration(os.environ.get("SANRO_INSPECTION_AUTHORIZED_UIDS"))
    service = None
    try:
        candidate = Path(raw_root)
        if (not candidate.is_absolute() or candidate.name != "sanro-inspection-metadata"
                or candidate.is_symlink()):
            raise ValueError("invalid metadata root")
        service = StructuredInspection(candidate, {str(uid) for uid in uids})
    except Exception:
        # Keep the tool unavailable in practice until trusted host config is correct.
        pass

    if service is None or not uids:
        def handle_denied(_args: Any, **_kwargs: Any) -> str:
            return json.dumps({"ok": False, "error": "inspection_denied"}, separators=(",", ":"))
        handler = handle_denied
    else:
        handler = make_handler(service, uids)
    ctx.register_tool(name=TOOL_NAME, toolset=TOOLSET, schema=SCHEMA, handler=handler)


__all__ = ["DEFAULT_ROOT", "SCHEMA", "TOOL_NAME", "TOOLSET", "make_handler", "register"]
