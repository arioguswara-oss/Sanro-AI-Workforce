#!/usr/bin/env python3
"""Fail-closed per-call approval gate for Backup/DR terminal operations.

Only terminal tool calls are matched by config. Routine commands that do not
look data-moving are no-ops; Backup/DR paths, archive/database/encryption/
transfer commands, and ambiguous code-execution wrappers escalate to Hermes'
native human approval. Parse/shape errors block. Never log input (it may carry
sensitive values).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from typing import Any

_BLOCK = "BLOCKED: Backup/DR approval gate could not safely classify this tool call."
_APPROVAL_MESSAGE = (
    "Backup/DR operation requires approval for this exact call. Select Allow Once only; "
    "deny, timeout, or ambiguous approval blocks execution."
)

# Include exact approved source roots/target plus the operations used by the
# minimum viable archive → encrypt → transfer → download → restore workflow.
_RISK = re.compile(
    r"(?:"
    r"\b(?:tar|sqlite3?|mysqldump|mariadb-dump|mariadb|mysql|age|rclone|rsync|scp|sftp|"
    r"gzip|gunzip|zip|unzip|dd)\b|"
    r"\b(?:backup|restore|archive|dump|encrypt|decrypt|upload|download|snapshot)\b|"
    r"\b(?:VPS|HOST)[-_](?:BACKUP|SNAPSHOT)\b|"
    r"/(?:home|root)/[^\s]*/\.hermes(?:/|\b)|"
    r"/(?:home|root)/[^\s]*/\.local/share/[A-Za-z0-9_.-]+(?:/|\b)|"
    r"/opt/[A-Za-z0-9_.-]+/worktrees/[A-Za-z0-9_.-]+(?:/|\b)|"
    r"(?:^|[;&|`]\s*)(?:python3?|node)\s+(?:-[cm]|-e\b)|"
    r"(?:^|[;&|`]\s*)(?:bash|sh)\s+-c\b"
    r")",
    re.IGNORECASE,
)


def _emit(value: dict[str, Any], exit_code: int = 0) -> None:
    sys.stdout.write(json.dumps(value, separators=(",", ":"), ensure_ascii=True))
    sys.stdout.write("\n")
    raise SystemExit(exit_code)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            _emit({"action": "block", "message": _BLOCK})
        if payload.get("hook_event_name") != "pre_tool_call":
            _emit({"action": "block", "message": _BLOCK})
        if payload.get("tool_name") != "terminal":
            _emit({"action": "block", "message": _BLOCK})
        tool_input = payload.get("tool_input")
        if not isinstance(tool_input, dict):
            _emit({"action": "block", "message": _BLOCK})
        command = tool_input.get("command")
        if not isinstance(command, str) or not command.strip():
            _emit({"action": "block", "message": _BLOCK})
        if not _RISK.search(command):
            _emit({})
        tool_call_id = payload.get("tool_call_id")
        if not isinstance(tool_call_id, str) or not tool_call_id.strip():
            extra = payload.get("extra")
            if isinstance(extra, dict):
                tool_call_id = extra.get("tool_call_id")
        session_id = payload.get("session_id")
        if not isinstance(tool_call_id, str) or not tool_call_id.strip() or not isinstance(session_id, str) or not session_id.strip():
            _emit({"action": "block", "message": _BLOCK})
        # A unique rule key prevents an accidental Always choice from granting
        # a reusable rule across distinct tool calls.
        key = hashlib.sha256(f"{session_id}\0{tool_call_id}\0{command}".encode()).hexdigest()[:24]
        _emit({
            "action": "approve",
            "message": _APPROVAL_MESSAGE,
            "rule_key": f"sanro-backup-once-{key}",
        })
    except SystemExit:
        raise
    except Exception:
        # No exception text or input is emitted: fail closed without exposing data.
        _emit({"action": "block", "message": _BLOCK})


if __name__ == "__main__":
    main()
