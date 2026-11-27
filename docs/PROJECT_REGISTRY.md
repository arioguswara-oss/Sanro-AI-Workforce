# Project Registry

| Project ID | Project | Repository | Branch | Runtime worker | Status |
|---|---|---|---|---|---|
| `sanro-ai-workforce` | SANRO AI Workforce Herdr pilot | `arioguswara-oss/Sanro-AI-Workforce` | `feature/hermes-workforce-foundation` | `sanro-workforce-pilot` (`t4`, PID 3018876, serial FIFO) | Runtime synthetic PASS; terminal output and Core lifecycle record verified; Owner final Spaces/Inbox visual check pending |

`sanro-browser-qa` is the fixed project ID in the isolated QA plugin candidate. It is **not registered as an authorized executor project in this checkout**: the pilot workspace path, branch, worker identity, repository transport identity, principal scopes and current mandate must be entered and validated in the private Workforce authorization file on the host. Do not infer these values from the project name or the previously reported Gitea main SHA. Until that private binding and a native per-job approval provider exist, the API must reject/leave the pilot runtime inactive.

Private Cloud Browser V1 is tracked under the same project/repository/branch. A project-authorized runtime operation now routes through the existing Workforce approval/native callback and wrapper, then a bounded transient systemd user unit with private network namespace and per-job artifacts. The source path and API admission are tested; no native callback/profile is registered on the VPS, and systemd/AppArmor/cgroup activation has not been verified. No Codex/Hermes service registration is active. See [Private Cloud Browser V1 operating package](integrations/PRIVATE_CLOUD_BROWSER_V1.md).

Pilot workspace is isolated at `/home/sanro/.local/state/sanro-ai-workforce-herdr-pilot/workspace`; durable queue and API status state are under the adjacent `state` directory. The Herdr supervisor remains live and idle after the synthetic job. No existing Codex or Hermes process was adopted.
