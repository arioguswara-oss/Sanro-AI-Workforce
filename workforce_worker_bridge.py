"""Private stdio bridge from the local Workforce API to the JD-04 adapter."""
import json
import os
import math
import sys

from hermes_adapter import Authorization, HermesAdapter


def main():
    request = json.load(sys.stdin)
    state_root = os.environ["WORKFORCE_WORKER_STATE"]
    projects = request["projects"]
    profiles = request["profiles"]
    allowed = [entry["command"] for entry in profiles.values()]
    adapter = HermesAdapter(state_root, {k: v["workspace"] for k, v in projects.items()}, allowed)
    try:
        action = request["action"]
        p = request["project"]
        principal = request["principal"]
        grants = principal["projects"][p["id"]]
        auth = Authorization(
            subject=principal["subject"],
            scopes=frozenset(grants["scopes"]),
            project_ids=frozenset([p["id"]]),
            workspaces=frozenset([p["workspace"]]),
            approval_refs=frozenset(grants.get("approval_refs", [])),
        )
        if action == "submit":
            profile = profiles.get(request["profile"])
            if not profile:
                raise PermissionError("unknown command profile")
            if profile.get("approval_required", True) and not request.get("approval_ref"):
                raise PermissionError("an explicit authorized approval reference is required")
            if p["id"] not in profile.get("projects", []):
                raise PermissionError("profile project mismatch")
            command = list(profile["command"])
            if "{workforce_instruction}" in command:
                instruction = request.get("instruction")
                if not isinstance(instruction, str) or len(instruction) > 20000:
                    raise PermissionError("bounded Director instruction required")
                manifest = json.loads(instruction)
                if manifest.get("project_id") != p["id"] or manifest.get("executor") != profile.get("executor"):
                    raise PermissionError("instruction scope mismatch")
                command = [instruction if arg == "{workforce_instruction}" else arg for arg in command]
                adapter.allowed_commands = [tuple(command)]
            timeout = float(request.get("timeout", 300))
            if not math.isfinite(timeout):
                raise ValueError("invalid timeout")
            result = adapter.submit(auth, project_id=p["id"], workspace=p["workspace"],
                approval_ref=request.get("approval_ref"), command=command,
                timeout=min(max(timeout, 1), 3600),
                idempotency_key=request["idempotency_key"])
        elif action == "status":
            result = adapter.status(auth, project_id=p["id"], workspace=p["workspace"], job_id=request["job_id"])
        elif action == "logs":
            result = {"logs": adapter.logs(auth, project_id=p["id"], workspace=p["workspace"], job_id=request["job_id"])}
        elif action == "result":
            result = adapter.result(auth, project_id=p["id"], workspace=p["workspace"], job_id=request["job_id"])
        elif action == "cancel":
            result = adapter.cancel(auth, project_id=p["id"], workspace=p["workspace"], job_id=request["job_id"])
        else:
            raise ValueError("unsupported worker action")
        print(json.dumps(result))
        return 0
    finally:
        adapter.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Return a generic error: do not copy command arguments or private paths into API output.
        print(json.dumps({"error": type(exc).__name__, "message": "worker operation rejected" if isinstance(exc, (PermissionError, ValueError, KeyError)) else "worker operation failed"}))
        raise SystemExit(1)
