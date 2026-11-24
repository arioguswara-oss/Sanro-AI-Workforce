"""Free-only routing policy candidate for Hermes custom OpenAI-compatible endpoints.

This module makes routing decisions and writes a small checkpoint. It deliberately does
not make network calls or resolve credentials. Hermes remains responsible for API calls,
provider retries, fallback switching, and its normal approval/tool controls.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class RouteRejected(ValueError):
    pass


@dataclass(frozen=True)
class FreeRoute:
    provider_id: str
    model: str
    base_url: str
    key_env: str
    cost_usd_per_million: float
    reliability: str = "unverified"
    engineering_tools: bool = False
    quota_cooldown_seconds: int = 60

    def validate(self) -> None:
        if not self.provider_id or not self.model or not self.key_env:
            raise RouteRejected("route identity and key_env are required")
        if self.cost_usd_per_million != 0:
            raise RouteRejected("free-only policy rejects paid or unknown-cost routes")
        if not self.base_url.startswith(("https://", "http://127.0.0.1:", "http://localhost:")):
            raise RouteRejected("route endpoint must use HTTPS or loopback")
        if self.quota_cooldown_seconds < 1:
            raise RouteRejected("quota cooldown must be positive")
        if self.engineering_tools and self.reliability != "verified":
            raise RouteRejected("engineering tools require an explicitly verified route")


class FreeOnlyRouter:
    """Ordered route selection with persisted cooldowns and conservative failback."""

    VERSION = 1

    def __init__(self, routes: list[FreeRoute], checkpoint: str | Path):
        if not routes:
            raise RouteRejected("at least one route is required")
        for route in routes:
            route.validate()
        identities = [(r.provider_id, r.model, r.base_url) for r in routes]
        if len(set(identities)) != len(identities):
            raise RouteRejected("duplicate route")
        self.routes = tuple(routes)
        self.checkpoint = Path(checkpoint)
        self._state: dict[str, Any] = {"version": self.VERSION, "cooldowns": {}, "last_success": None}
        self._load()

    @staticmethod
    def _key(route: FreeRoute) -> str:
        return f"{route.provider_id}/{route.model}@{route.base_url}"

    def _load(self) -> None:
        try:
            data = json.loads(self.checkpoint.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            if data.get("version") == self.VERSION and isinstance(data.get("cooldowns"), dict):
                known = {self._key(r) for r in self.routes}
                self._state = {
                    "version": self.VERSION,
                    "cooldowns": {k: float(v) for k, v in data["cooldowns"].items() if k in known},
                    "last_success": data.get("last_success") if data.get("last_success") in known else None,
                }
        except (OSError, ValueError, TypeError):
            pass

    def _save(self) -> None:
        self.checkpoint.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".route-state-", dir=self.checkpoint.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self._state, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, self.checkpoint)
            os.chmod(self.checkpoint, 0o600)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def choose(self, *, engineering_tools: bool = False, now: float | None = None) -> FreeRoute:
        now = time.time() if now is None else now
        cooldowns = self._state["cooldowns"]
        candidates = [r for r in self.routes if not engineering_tools or r.engineering_tools]
        for route in candidates:
            if float(cooldowns.get(self._key(route), 0)) <= now:
                return route
        raise RouteRejected("no eligible route; all routes are cooling down or tool-ineligible")

    def record_quota(self, route: FreeRoute, *, retry_after_seconds: int | None = None, now: float | None = None) -> None:
        if route not in self.routes:
            raise RouteRejected("route is outside this router's allowlist")
        delay = route.quota_cooldown_seconds if retry_after_seconds is None else max(1, int(retry_after_seconds))
        self._state["cooldowns"][self._key(route)] = (time.time() if now is None else now) + delay
        self._save()

    def record_success(self, route: FreeRoute) -> None:
        if route not in self.routes:
            raise RouteRejected("route is outside this router's allowlist")
        self._state["cooldowns"].pop(self._key(route), None)
        self._state["last_success"] = self._key(route)
        self._save()

    def hermes_fallback_entries(self) -> list[dict[str, str]]:
        """Emit Hermes' documented custom endpoint fallback entry shape, in route order."""
        return [{"provider": "custom", "model": r.model, "base_url": r.base_url, "key_env": r.key_env}
                for r in self.routes]
