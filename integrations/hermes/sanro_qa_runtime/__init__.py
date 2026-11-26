"""Profile-local Hermes tool adapter for fixed Workforce QA operations.

This plugin submits jobs to the loopback Workforce API only. It never executes
commands, selects a workspace, chooses an operation from free text, or handles
Hermes approval decisions. The API/Local CI host remains authoritative.
"""
from __future__ import annotations

from .client import make_handler


def register(ctx) -> None:
    """Register exactly two project-bound Local CI tools; no hooks/capabilities."""
    ctx.register_tool(
        name="sanro_qa_browser_smoke",
        toolset="sanro_qa_runtime",
        schema={
            "name": "sanro_qa_browser_smoke",
            "description": "Submit the fixed synthetic Chromium smoke check for the authorized Workforce project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "version": {"type": "integer", "enum": [1]},
                    "job_id": {"type": "string", "minLength": 8, "maxLength": 128},
                },
                "required": ["version", "job_id"],
                "additionalProperties": False,
            },
        },
        handler=make_handler("sanro-qa-browser-smoke"),
    )
    ctx.register_tool(
        name="sanro_qa_private_browser_acceptance",
        toolset="sanro_qa_runtime",
        schema={
            "name": "sanro_qa_private_browser_acceptance",
            "description": "Submit the fixed private synthetic Playwright MCP acceptance for the authorized Workforce project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "version": {"type": "integer", "enum": [1]},
                    "job_id": {"type": "string", "minLength": 8, "maxLength": 128},
                },
                "required": ["version", "job_id"],
                "additionalProperties": False,
            },
        },
        handler=make_handler("sanro-qa-private-browser-acceptance"),
    )


__all__ = ["register"]
