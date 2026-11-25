# Hermes integration compatibility
Inspected upstream source: NousResearch/hermes-agent commit `2506f5b0a4d310b96ec2eb6f2de4ea7349ba4d15` on 25 November 2026 Jakarta. This is a reference checkout, not the installed VPS runtime.

| Interface | Candidate usage | Boundary |
|---|---|---|
| `gateway.session_context.bound_session_env(name)` | Read turn-bound platform, actor, chat, session key | No process environment fallback; missing API/identity denies action |
| `tools.approval.request_tool_approval(tool_name, reason, rule_key=..., approval_callback=...)` | Native request before submission | Only literal `approved is True`; pending/denied/missing never queues work |
| `PluginContext.register_tool`, `on_unload` | Existing JD-04 shim | Actual installed version registration still needs host test |
| JD-03 `sanro_inspect_metadata` | Strict Backup/DR state projection and host UID allowlist | No arbitrary path/tool/command input; not a user-session authority |

Scope is checked before requesting native approval. Subjects bind platform/actor/chat/session. `HERMES_SESSION_ACTOR_ID` identifies the current sender; `HERMES_SESSION_USER_ID` is a routing identity and is not accepted as actor proof. Execute-only subjects no longer encounter a read-notification failure after successful submission. No change to native approval policy.

Worker uses a reduced environment, Landlock filesystem policy and seccomp. The source-bound `f909923` acceptance run reported Landlock ABI 0 and correctly failed closed; the current development host reports ABI 8 and focused synthetic worker tests pass. Do not disable the boundary to make tests pass. Acceptance still must run on the authorized target host after SSH/runtime identity is verified. Same-UID/kernel and broad system library reads do not constitute full credential isolation. Workspaces must exclude credentials; live activation remains blocked pending host review.

Native source references:
- https://github.com/NousResearch/hermes-agent/blob/2506f5b0a4d310b96ec2eb6f2de4ea7349ba4d15/gateway/session_context.py
- https://github.com/NousResearch/hermes-agent/blob/2506f5b0a4d310b96ec2eb6f2de4ea7349ba4d15/tools/approval.py
