"""Hermes project plugin shim for the isolated JD-04 worker.

Discovery is opt-in in Hermes (HERMES_ENABLE_PROJECT_PLUGINS). Project ACLs and
command allowlists are read from this plugin's settings; missing identity or
settings fail closed. No live runtime is modified by this package's presence.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import tempfile
import re

# Plugin is loaded from <workspace>/.hermes/plugins/<plugin>/; parents[3] is
# the workspace root where the adapter and worker modules live.
ROOT = pathlib.Path(__file__).resolve().parents[3]
STATE_ROOT = pathlib.Path(tempfile.gettempdir()) / f"jd04-worker-state-{os.getuid()}"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hermes_adapter import Authorization, HermesAdapter, WorkerSupervisor, redact

TOOL_SCHEMA = {
    "name": "jd04_engineering_job",
    "description": "Submit and manage isolated serial engineering jobs for an authorized project.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["submit", "status", "logs", "cancel", "result", "notifications"]},
            "project_id": {"type": "string"}, "job_id": {"type": "string"},
            "idempotency_key": {"type": "string"},
            "profile": {"type": "string"},
            "arguments": {"type": "array", "items": {"type": "string"}},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 86400},
        },
        "required": ["action", "project_id"],
    },
}


def register(ctx) -> None:
    """Hermes native plugin entry point (PluginContext.register_tool)."""
    projects = ctx.get_config("projects", {}) or {}
    if not isinstance(projects, dict):
        projects = {}
    profiles = {}
    for item in projects.values():
        if isinstance(item, dict) and isinstance(item.get("command_profiles"), dict):
            profiles.update({key: value for key, value in item["command_profiles"].items()
                             if isinstance(key, str) and isinstance(value, dict)})
    allowed = [entry.get("argv") for entry in profiles.values() if isinstance(entry.get("argv"), list)]
    adapter = None
    supervisor = None

    def services():
        nonlocal adapter, supervisor
        if adapter is None:
            adapter = HermesAdapter(STATE_ROOT,
                                    {pid: item["workspace"] for pid, item in projects.items()
                                     if isinstance(item, dict) and item.get("workspace")}, allowed)
            supervisor = WorkerSupervisor(STATE_ROOT)
        return adapter, supervisor

    def handle(args, **kwargs):
        action, project_id = args.get("action"), args.get("project_id")
        item = projects.get(project_id) if isinstance(project_id, str) else None
        if not isinstance(item, dict):
            return json.dumps({"error": "project is not configured"})
        try:
            from gateway.session_context import bound_session_env
            platform = bound_session_env("HERMES_SESSION_PLATFORM")
            user_id = bound_session_env("HERMES_SESSION_ACTOR_ID")
            chat_id = bound_session_env("HERMES_SESSION_CHAT_ID")
            session_key = bound_session_env("HERMES_SESSION_KEY")
            if platform != "telegram" or not user_id or not session_key:
                raise PermissionError("Telegram user and active session identity are required")
            authorized_users = {str(v) for v in item.get("telegram_user_ids", [])}
            if user_id not in authorized_users:
                raise PermissionError("Telegram user is not authorized for this project")
            workspace_path = pathlib.Path(item.get("workspace", ""))
            if not workspace_path.is_absolute() or not workspace_path.is_dir() or workspace_path.is_symlink():
                raise PermissionError("project workspace must be an existing absolute directory")
            workspace = str(workspace_path.resolve())
            subject = ":".join((platform, user_id, chat_id, session_key))
            configured_scopes = item.get("scopes", [])
            if not isinstance(configured_scopes, list) or not all(s in {"engineering:execute", "engineering:read", "engineering:cancel", "engineering:admin"} for s in configured_scopes):
                raise PermissionError("project scopes are invalid")
            scopes = frozenset(configured_scopes)
            required_scope = {"submit": "engineering:execute", "cancel": "engineering:cancel",
                              "status": "engineering:read", "logs": "engineering:read",
                              "result": "engineering:read", "notifications": "engineering:read"}.get(action)
            if required_scope is None or required_scope not in scopes:
                raise PermissionError("action scope is not authorized")
            approval_refs = frozenset()
            if action == "submit":
                profile_name = args.get("profile")
                profile = item.get("command_profiles", {}).get(profile_name)
                values = args.get("arguments", [])
                if not isinstance(profile_name, str) or not isinstance(profile, dict) or not isinstance(profile.get("argv"), list):
                    raise PermissionError("command profile is not authorized for this project")
                if not isinstance(values, list) or not all(isinstance(v, str) and "\x00" not in v and "\n" not in v and "\r" not in v for v in values):
                    raise ValueError("arguments must be plain single-line strings")
                pattern = profile.get("argument_pattern", r"^[A-Za-z0-9_./:=,+@ -]{0,512}$")
                if any(not re.fullmatch(pattern, v) or pathlib.PurePosixPath(v).is_absolute() or ".." in pathlib.PurePosixPath(v).parts for v in values):
                    raise PermissionError("argument is outside the command profile")
                command = list(profile["argv"]) + values
                if not command or not all(isinstance(v, str) and v and "\x00" not in v for v in command):
                    raise PermissionError("invalid configured command profile")
                digest = hashlib.sha256(json.dumps(command, separators=(",", ":")).encode()).hexdigest()[:16]
                from tools.approval import request_tool_approval
                decision = request_tool_approval(
                    "jd04_engineering_job", f"Submit project {project_id} command hash {digest}",
                    rule_key=f"jd04:{project_id}:{digest}", approval_callback=kwargs.get("callback"))
                if not isinstance(decision, dict) or decision.get("approved") is not True:
                    return json.dumps({"status": "approval_denied", "message": "native approval was not granted"})
                approval_refs = frozenset({hashlib.sha256((subject + digest).encode()).hexdigest()})
            auth = Authorization(subject, scopes, frozenset({project_id}), frozenset({workspace}), approval_refs)
            api, process_supervisor = services()
            if action == "submit":
                response = api.submit(auth, project_id=project_id, workspace=workspace,
                    approval_ref=next(iter(approval_refs)), command=command,
                    timeout=int(args.get("timeout", 3600)), idempotency_key=args.get("idempotency_key", ""))
                process_supervisor.start()
            elif action == "status":
                response = api.status(auth, project_id=project_id, workspace=workspace, job_id=args.get("job_id"))
            elif action == "logs":
                response = {"job_id": args.get("job_id"), "logs": api.logs(auth, project_id=project_id, workspace=workspace, job_id=args.get("job_id"))}
            elif action == "result":
                response = api.result(auth, project_id=project_id, workspace=workspace, job_id=args.get("job_id"))
            elif action == "cancel":
                response = api.cancel(auth, project_id=project_id, workspace=workspace, job_id=args.get("job_id"))
            elif action == "notifications":
                response = {"notifications": api.drain_notifications(auth, project_id=project_id, workspace=workspace)}
            else:
                response = {"error": "unknown action"}
            if action != "notifications" and "engineering:read" in scopes:
                notifications = api.drain_notifications(auth, project_id=project_id, workspace=workspace)
                if notifications:
                    response["notifications"] = notifications
            return json.dumps(response, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": redact(str(exc))[:500]})

    ctx.register_tool(name="jd04_engineering_job", toolset="jd04_engineering_worker",
                      schema=TOOL_SCHEMA, handler=handle,
                      description="Submit/status/log/cancel/result for authorized JD-04 engineering jobs.")
    ctx.on_unload(lambda: supervisor.shutdown() if supervisor else None)
