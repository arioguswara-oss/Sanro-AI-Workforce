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

from model_routing import FreeOnlyRouter, FreeRoute, RouteRejected


class ProviderFailure(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, retry_after: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status, self.retry_after, self.retryable = status, retry_after, retryable


@dataclass(frozen=True)
class ProviderResponse:
    status: int
    body: bytes
    headers: dict[str, str]


def _http_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> ProviderResponse:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return ProviderResponse(response.status, response.read(2_000_000), dict(response.headers.items()))
    except urllib.error.HTTPError as error:
        return ProviderResponse(error.code, error.read(16_384), dict(error.headers.items()))
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ProviderFailure("provider transport unavailable", retryable=True) from error


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

    def complete(self, messages: list[dict], *, tools: list[dict] | None = None) -> dict:
        if tools and (not self.route.engineering_tools or self.route.reliability != "verified"):
            raise RouteRejected("route is not qualified for tool-calling engineering work")
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
            raise ProviderFailure("provider quota exhausted", status=429, retry_after=_retry_after(response.headers), retryable=True)
        if response.status in (408, 425) or response.status >= 500:
            raise ProviderFailure("provider temporarily unavailable", status=response.status, retry_after=_retry_after(response.headers), retryable=True)
        if response.status in (401, 403):
            raise ProviderFailure("provider authorization rejected", status=response.status)
        if response.status < 200 or response.status >= 300:
            raise ProviderFailure("provider rejected request", status=response.status)
        try:
            result = json.loads(response.body)
            if not isinstance(result, dict) or not isinstance(result.get("choices"), list) or not result["choices"]:
                raise ValueError
            return result
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as error:
            raise ProviderFailure("provider response did not match the OpenAI chat-completions shape") from error


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

    def complete(self, messages: list[dict], *, request_id: str, engineering: bool = False, tools: list[dict] | None = None) -> dict:
        if engineering:
            raise RouteRejected("engineering execution remains assigned to Codex; provider models cannot run tools")
        if not request_id or len(request_id) > 200:
            raise RouteRejected("bounded request_id required")
        fingerprint_input = {"messages": messages, "tools": tools}
        state = self.checkpoint.begin(request_id, fingerprint_input)
        attempted = set(state["attempted_routes"])
        eligible = [r for r in self.router.routes if r.reliability == "verified" and not tools]
        if not eligible:
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
            try:
                result = provider.complete(messages, tools=tools)
            except ProviderFailure as error:
                if not error.retryable:
                    self.checkpoint.update(request_id, status="BLOCKED", attempted_routes=sorted(attempted), last_error=error.status)
                    raise
                cooldown = error.retry_after if error.status == 429 else None
                self.router.record_unavailable(route, retry_after_seconds=cooldown)
                attempted.add(key)
                self.checkpoint.update(request_id, status="FALLING_BACK", attempted_routes=sorted(attempted), last_error=error.status)
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

    def resume(self, messages: list[dict], *, request_id: str) -> dict:
        """Retry an explicitly resubmitted inference request after cooldown; no tool is replayed."""
        row = self.checkpoint.state["requests"].get(request_id)
        if not row or row.get("status") != "PAUSED":
            raise RouteRejected("only a paused inference checkpoint can be resumed")
        if not self.resume_eligible(request_id):
            raise RouteRejected("no eligible provider has recovered; checkpoint remains PAUSED")
        # Keep attempts as evidence, but permit a fresh model attempt after quota reset.
        row["attempted_routes"] = []
        return self.complete(messages, request_id=request_id, engineering=False)
