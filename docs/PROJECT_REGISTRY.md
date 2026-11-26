# Project Registry

| Project ID | Project | Repository | Branch | Runtime worker | Status |
|---|---|---|---|---|---|
| `sanro-ai-workforce` | SANRO AI Workforce Herdr pilot | `arioguswara-oss/Sanro-AI-Workforce` | `feature/hermes-workforce-foundation` | `sanro-workforce-pilot` (`t4`, PID 3018876, serial FIFO) | Runtime synthetic PASS; terminal output and Core lifecycle record verified; Owner final Spaces/Inbox visual check pending |

Private Cloud Browser V1 is tracked under the same project/repository/branch. Its host MCP acceptance package is prepared, but it is not registered with Codex/Hermes or running on the VPS. Host execution remains unavailable: the SSH agent socket is absent and `hc machine ls` is empty; the live Core status does not provide a shell executor. The existing runtime wrapper's seccomp policy also denies the socket calls required by MCP. See [Private Cloud Browser V1 operating package](integrations/PRIVATE_CLOUD_BROWSER_V1.md).

Pilot workspace is isolated at `/home/sanro/.local/state/sanro-ai-workforce-herdr-pilot/workspace`; durable queue and API status state are under the adjacent `state` directory. The Herdr supervisor remains live and idle after the synthetic job. No existing Codex or Hermes process was adopted.
