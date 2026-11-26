"""Fail-closed loopback client for the existing Workforce runtime API."""
from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


PROJECT_ID = "sanro-browser-qa"
API_URL = "http://127.0.0.1:8787"
API_PATH = f"/api/projects/{PROJECT_ID}/runtime-acceptance"
PROFILE_BY_TOOL = {
    "sanro-qa-browser-smoke": "sanro-browser-qa-browser-smoke",
    "sanro-qa-private-browser-acceptance": "sanro-browser-qa-private-browser-acceptance",
}
TIMEOUT_BY_TOOL = {
    "sanro-qa-browser-smoke": 150,
    "sanro-qa-private-browser-acceptance": 300,
}
JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$")
APPROVAL_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_RESULT_STATUSES = {"PASS", "FAIL", "BLOCKED"}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _denied(code: str) -> str:
    return json.dumps({"status": "BLOCKED", "code": code}, separators=(",", ":"))


def make_handler(tool_id: str, *, environ=None, opener=None):
    """Create the `register(ctx)` callback handler; tests inject only fake transport/env."""
    if tool_id not in PROFILE_BY_TOOL:
        raise ValueError("tool is not allowlisted")
    env = os.environ if environ is None else environ
    open_request = opener or build_opener(_NoRedirect()).open

    def handle(args, **_hermes_context):
        try:
            if not isinstance(args, dict) or set(args) != {"version", "job_id"}:
                return _denied("invalid_request")
            if type(args["version"]) is not int or args["version"] != 1:
                return _denied("invalid_request")
            job_id = args["job_id"]
            if not isinstance(job_id, str) or not JOB_ID_RE.fullmatch(job_id):
                return _denied("invalid_request")

            token = env.get("SANRO_QA_WORKFORCE_BEARER_TOKEN")
            approval_ref = env.get("SANRO_QA_APPROVAL_REF")
            if not isinstance(token, str) or not token or "\n" in token or "\r" in token:
                return _denied("runtime_not_configured")
            if not isinstance(approval_ref, str) or not APPROVAL_REF_RE.fullmatch(approval_ref):
                return _denied("approval_not_configured")

            body = json.dumps({
                "profile": PROFILE_BY_TOOL[tool_id],
                "approval_ref": approval_ref,
                "idempotency_key": job_id,
            }, separators=(",", ":")).encode("utf-8")
            request = Request(
                API_URL + API_PATH,
                data=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            http_status = 200
            try:
                with open_request(request, timeout=TIMEOUT_BY_TOOL[tool_id]) as response:
                    http_status = response.status
                    result = json.loads(response.read(16385))
            except HTTPError as response:
                http_status = response.code
                try:
                    result = json.loads(response.read(16385))
                finally:
                    response.close()
            if (not isinstance(result, dict) or result.get("status") not in _RESULT_STATUSES
                    or result.get("job_id") != job_id
                    or result.get("project_id") != PROJECT_ID):
                return _denied("invalid_runtime_response")
            operation = result.get("operation")
            allowed_operation = ("browser_smoke" if tool_id == "sanro-qa-browser-smoke"
                                 else "private_browser_acceptance")
            if operation != allowed_operation:
                return _denied("profile_operation_mismatch")
            expected_http_status = {"PASS": 200, "FAIL": 422, "BLOCKED": 503}[result["status"]]
            if http_status != expected_http_status:
                return _denied("runtime_rejected")
            return json.dumps({"status": result["status"], "job_id": job_id,
                               "project_id": PROJECT_ID, "operation": allowed_operation},
                              separators=(",", ":"))
        except (URLError, TimeoutError, OSError, ValueError, TypeError):
            return _denied("runtime_unavailable")
        except Exception:
            # No exception, response body, URL, token, or filesystem detail escapes.
            return _denied("runtime_unavailable")

    return handle


__all__ = ["API_PATH", "API_URL", "PROJECT_ID", "PROFILE_BY_TOOL", "TIMEOUT_BY_TOOL", "make_handler"]
