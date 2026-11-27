"""Free-only OpenAI-compatible provider adapter with bounded fallback policy.

No provider is contacted until a caller explicitly invokes ``complete``. Tests
inject an in-memory transport. Tool output is returned as data and never executed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from model_routing import FreeOnlyRouter, FreeRoute, RouteRejected, WORKLOAD_CAPABILITIES


class ProviderFailure(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, retry_after: int | None = None, retryable: bool = False, kind: str = "provider_failure"):
        super().__init__(message)
        self.status, self.retry_after, self.retryable, self.kind = status, retry_after, retryable, kind


@dataclass(frozen=True)
class ProviderResponse:
    status: int
    body: bytes
    headers: dict[str, str]


def _http_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> ProviderResponse:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        # Never follow redirects with a provider credential or prompt.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            return ProviderResponse(response.status, response.read(2_000_000), dict(response.headers.items()))
    except urllib.error.HTTPError as error:
        return ProviderResponse(error.code, error.read(16_384), dict(error.headers.items()))
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ProviderFailure("provider transport unavailable", retryable=True, kind="network_failure") from error


def _retry_after(headers: dict[str, str]) -> int | None:
    value = next((v for k, v in headers.items() if k.lower() == "retry-after"), None)
    if not value:
        return None
    try:
        return max(1, min(86_400, int(float(value))))
    except ValueError:
        try:
            retry_at = dt.datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=dt.timezone.utc).timestamp()
            return max(1, min(86_400, int(retry_at - time.time())))
        except ValueError:
            return None


class OpenAICompatibleProvider:
    """Adapter shape shared by 9Router and FreeLLMAPI `/v1/chat/completions`."""
    def __init__(self, route: FreeRoute, *, transport: Callable = _http_transport, timeout: float = 45):
        route.validate()
        self.route, self.transport, self.timeout = route, transport, timeout

    def complete(self, messages: list[dict], *, tools: list[dict] | None = None, capabilities: set[str] | frozenset[str] | None = None) -> dict:
        if self.route.reliability != "verified":
            raise RouteRejected("unverified provider is disabled")
        required = set(capabilities or ({"structured_tool_calling"} if tools else {"simple_text_processing"}))
        if not required <= WORKLOAD_CAPABILITIES or "engineering" in required:
            raise RouteRejected("unknown capability or engineering job cannot use a model fallback")
        if not required <= set(self.route.capabilities):
            raise RouteRejected("route does not meet the requested workload capabilities")
        if tools and (not self.route.engineering_tools or "structured_tool_calling" not in required):
            raise RouteRejected("route is not qualified for structured tool calling")
        if "structured_tool_calling" in required and not tools:
            raise RouteRejected("structured tool calling requires bounded tool definitions")
        key = os.environ.get(self.route.key_env)
        if not key:
            raise ProviderFailure("provider credential is unavailable", status=401)
        payload = {"model": self.route.model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools
        body = json.dumps(payload, separators=(",", ":")).encode()
        url = self.route.base_url.rstrip("/") + "/chat/completions"
        response = self.transport(url, {"authorization": f"Bearer {key}", "content-type": "application/json"}, body, self.timeout)
        if response.status == 429:
            raise ProviderFailure("provider quota exhausted", status=429, retry_after=_retry_after(response.headers), retryable=True, kind="rate_limit")
        if response.status in (408, 425) or response.status >= 500:
            raise ProviderFailure("provider temporarily unavailable", status=response.status, retry_after=_retry_after(response.headers), retryable=True, kind="provider_unavailable")
        if response.status in (401, 403):
            raise ProviderFailure("provider authorization rejected", status=response.status)
        if response.status < 200 or response.status >= 300:
            raise ProviderFailure("provider rejected request", status=response.status)
        try:
            result = json.loads(response.body)
            if not isinstance(result, dict) or not isinstance(result.get("choices"), list) or not result["choices"]:
                raise ValueError
            if tools:
                _validate_tool_calls(result, tools)
            return result
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as error:
            raise ProviderFailure("provider response did not match the OpenAI chat-completions shape") from error


def _validate_tool_calls(response: dict, tools: list[dict]) -> None:
    definitions = {}
    for tool in tools:
        if not isinstance(tool, dict) or tool.get("type") != "function" or not isinstance(tool.get("function"), dict):
            raise RouteRejected("tool definition must use the OpenAI function schema")
        function = tool["function"]
        if not isinstance(function.get("name"), str) or not function["name"]:
            raise RouteRejected("tool function name is required")
        definitions[function["name"]] = function.get("parameters", {})
    message = response["choices"][0].get("message")
    calls = message.get("tool_calls") if isinstance(message, dict) else None
    if calls is None:
        return
    if not isinstance(calls, list) or len(calls) > 16:
        raise ProviderFailure("provider tool call schema invalid", retryable=True, kind="invalid_tool_schema")
    try:
        for call in calls:
            if not isinstance(call, dict) or call.get("type") != "function" or not isinstance(call.get("id"), str):
                raise ValueError
            function = call.get("function")
            if not isinstance(function, dict) or function.get("name") not in definitions or not isinstance(function.get("arguments"), str):
                raise ValueError
            arguments = json.loads(function["arguments"])
            schema = definitions[function["name"]]
            if not isinstance(arguments, dict) or not isinstance(schema, dict):
                raise ValueError
            required = schema.get("required", [])
            properties = schema.get("properties", {})
            if schema.get("type", "object") != "object" or not isinstance(required, list) or not isinstance(properties, dict) or any(name not in arguments for name in required):
                raise ValueError
            if schema.get("additionalProperties") is False and any(name not in properties for name in arguments):
                raise ValueError
            for name, value in arguments.items():
                prop = properties.get(name)
                if prop is None:
                    continue
                expected = prop.get("type") if isinstance(prop, dict) else None
                valid_type = {"string": lambda x: isinstance(x, str), "integer": lambda x: type(x) is int,
                              "number": lambda x: type(x) in (int, float), "boolean": lambda x: type(x) is bool,
                              "object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
                              "null": lambda x: x is None}
                if expected in valid_type and not valid_type[expected](value):
                    raise ValueError
                if isinstance(prop, dict) and "enum" in prop and value not in prop["enum"]:
                    raise ValueError
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise ProviderFailure("provider tool call schema invalid", retryable=True, kind="invalid_tool_schema") from error


class RoutingCheckpoint:
    """Atomic checkpoint metadata without prompt, response, or credential contents."""
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.state = self._load()

    def _load(self) -> dict:
        try:
            value = json.loads(self.path.read_text())
            return value if isinstance(value, dict) and value.get("version") == 1 and isinstance(value.get("requests"), dict) else {"version": 1, "requests": {}}
        except (OSError, ValueError, TypeError):
            return {"version": 1, "requests": {}}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".route-checkpoint-", dir=self.path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w") as stream:
                json.dump(self.state, stream, sort_keys=True)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(name, self.path); os.chmod(self.path, 0o600)
        finally:
            try: os.unlink(name)
            except FileNotFoundError: pass

    def begin(self, request_id: str, payload: dict) -> dict:
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        prior = self.state["requests"].get(request_id)
        if prior and prior["fingerprint"] != fingerprint:
            raise RouteRejected("request_id was reused with different request content")
        if prior and prior.get("status") in {"COMPLETED", "RUNNING", "BLOCKED", "INTERRUPTED"}:
            raise RouteRejected("request already completed or has uncertain side effects; automatic replay denied")
        row = prior or {"fingerprint": fingerprint, "status": "RUNNING", "attempted_routes": [], "last_success": None}
        row["status"] = "RUNNING"; self.state["requests"][request_id] = row; self.save()
        return row

    def update(self, request_id: str, **changes) -> None:
        self.state["requests"][request_id].update(changes); self.save()


class FreeModelEngine:
    """Bounded conversation fallback. Codex remains the engineering executor."""
    ENGINEERING_EXECUTOR = "codex"

    def __init__(self, router: FreeOnlyRouter, providers: dict[str, OpenAICompatibleProvider], checkpoint: str | Path):
        self.router, self.providers, self.checkpoint = router, providers, RoutingCheckpoint(checkpoint)

    def complete(self, messages: list[dict], *, request_id: str, engineering: bool = False, tools: list[dict] | None = None, capabilities: set[str] | frozenset[str] | None = None) -> dict:
        if engineering or "engineering" in set(capabilities or ()):
            raise RouteRejected("engineering execution remains assigned to Codex; provider models cannot run tools")
        if not request_id or len(request_id) > 200:
            raise RouteRejected("bounded request_id required")
        required = set(capabilities or ({"structured_tool_calling"} if tools else {"simple_text_processing"}))
        if not required <= WORKLOAD_CAPABILITIES or "engineering" in required:
            raise RouteRejected("unknown workload capability")
        if tools and "structured_tool_calling" not in required:
            raise RouteRejected("tool definitions require structured_tool_calling capability")
        fingerprint_input = {"messages": messages, "tools": tools, "capabilities": sorted(required)}
        state = self.checkpoint.begin(request_id, fingerprint_input)
        attempted = set(state["attempted_routes"])
        eligible = [r for r in self.router.routes if r.reliability == "verified" and required <= set(r.capabilities) and (not tools or r.engineering_tools)]
        if not eligible:
            self.checkpoint.update(request_id, status="PAUSED")
            raise RouteRejected("no verified conversation route available")
        candidates = [r for r in eligible if self.router._state["cooldowns"].get(self.router._key(r), 0) <= time.time()]
        for route in candidates:
            key = self.router._key(route)
            if key in attempted:
                continue
            provider = self.providers.get(route.provider_id)
            if provider is None:
                self.router.record_unavailable(route)
                attempted.add(key)
                self.checkpoint.update(request_id, attempted_routes=sorted(attempted))
                continue
            if provider.route != route:
                self.checkpoint.update(request_id, status="BLOCKED")
                raise RouteRejected("provider route does not match configured capability and cost policy")
            attempted.add(key)
            self.checkpoint.update(request_id, status="RUNNING", attempted_routes=sorted(attempted))
            try:
                result = provider.complete(messages, tools=tools, capabilities=required)
            except ProviderFailure as error:
                if not error.retryable:
                    self.checkpoint.update(request_id, status="BLOCKED", attempted_routes=sorted(attempted), last_error=error.status)
                    raise
                cooldown = error.retry_after if error.status == 429 else None
                self.router.record_unavailable(route, retry_after_seconds=cooldown)
                attempted.add(key)
                self.checkpoint.update(request_id, status="FALLING_BACK", attempted_routes=sorted(attempted), last_error=error.kind)
                continue
            self.router.record_success(route)
            self.checkpoint.update(request_id, status="COMPLETED", attempted_routes=sorted(attempted | {key}), last_success=key, last_error=None)
            return result
        self.checkpoint.update(request_id, status="PAUSED", attempted_routes=sorted(attempted))
        raise RouteRejected("all verified free conversation routes are cooling down or unavailable; checkpoint is PAUSED")

    def resume_eligible(self, request_id: str, *, now: float | None = None) -> bool:
        """Report whether a paused request has a recovered route; does not send it."""
        row = self.checkpoint.state["requests"].get(request_id)
        if not row or row.get("status") != "PAUSED":
            return False
        now = time.time() if now is None else now
        return any(route.reliability == "verified" and self.router._state["cooldowns"].get(self.router._key(route), 0) <= now for route in self.router.routes)

    def resume(self, messages: list[dict], *, request_id: str, capabilities: set[str] | frozenset[str] | None = None) -> dict:
        """Retry an explicitly resubmitted inference request after cooldown; no tool is replayed."""
        row = self.checkpoint.state["requests"].get(request_id)
        if not row or row.get("status") != "PAUSED":
            raise RouteRejected("only a paused inference checkpoint can be resumed")
        if not self.resume_eligible(request_id):
            raise RouteRejected("no eligible provider has recovered; checkpoint remains PAUSED")
        # Keep attempts as evidence, but permit a fresh model attempt after quota reset.
        required = set(capabilities or {"simple_text_processing"})
        fingerprint = hashlib.sha256(json.dumps({"messages": messages, "tools": None, "capabilities": sorted(required)}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if row["fingerprint"] != fingerprint:
            raise RouteRejected("resume content differs from paused request")
        row["attempted_routes"] = []
        self.checkpoint.save()
        return self.complete(messages, request_id=request_id, engineering=False, capabilities=required)
