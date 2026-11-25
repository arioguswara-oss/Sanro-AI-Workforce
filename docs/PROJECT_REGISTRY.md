# Project Registry

| Project ID | Project | Repository | Branch | Runtime worker | Status |
|---|---|---|---|---|---|
| `sanro-ai-workforce` | SANRO AI Workforce Herdr pilot | `arioguswara-oss/Sanro-AI-Workforce` | `feature/hermes-workforce-foundation` | `sanro-workforce-pilot` (`t3`, `serial-workforce-supervisor`) | Synthetic pilot completed; Android visual confirmation pending |

Pilot workspace is isolated at `/home/sanro/.local/state/sanro-ai-workforce-herdr-pilot/workspace`; durable queue and API status state are under the adjacent `state` directory. The Herdr supervisor remains live and idle after the synthetic job. No existing Codex or Hermes process was adopted.
