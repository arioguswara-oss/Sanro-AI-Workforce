# Provider qualification — 25 November 2026 Jakarta

Canonical repositories from the existing project are `decolua/9router` and `Pendia/FreeLLMAPI`. Similarly named forks are not qualification evidence for these installations.

| Provider | Documented protocol | Price/quota finding | Candidate decision |
|---|---|---|---|
| 9Router | OpenAI-compatible chat completions on local port 20128 | Has subscription, paid and free tiers; quota depends on downstream account/model; no actual account caps observed | Compatible adapter retained, disabled catalog entry; require fixed free-only downstream allowlist and no paid fallback |
| FreeLLMAPI | OpenAI-compatible `/v1/chat/completions`, model IDs/profiles and routing metadata | Advertises free-tier aggregation and optional paid catalog access; upstream caps/terms remain account-specific; states personal experimentation rather than production use | Protocol adapter retained for mocks; no installation/activation; operational benefit unproven and usage scope unresolved |

No pricing advertisement proves this user's route is free. No credentials, provider calls, subscriptions or extra service were used. Unknown quota is `UNAVAILABLE`, never unlimited. Provider capabilities/context/tool quality are documented claims only. All engineering execution stays with Codex, outside conversational fallback.

Sources inspected:
- https://docs.9router.com/ (free/paid/subscription tier description)
- https://github.com/decolua/9router
- https://github.com/Pendia/FreeLLMAPI (API shape, quota handling, premium catalog and experimentation scope)

JD-02 original report and installed model configuration remain unavailable. Historical `fallback.min_switch_reset_seconds` correction is retained as historical evidence, not a claim about current installed runtime. The local candidate applies a bounded per-route circuit, Retry-After cooldown, ordered fallback and failback at request boundaries. It pauses without eligible models. Prompt/response/credentials never enter routing checkpoints; completed/in-flight requests cannot silently replay. HTTP redirects are refused to prevent forwarding credentials to a different endpoint.
