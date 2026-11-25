# TokenEconomizer v0.1.0 integration audit

**Date:** 2026-11-25  
**Scope:** Installed Codex plugin and its five Codex hook events, for the SANRO AI Workforce repository only. No Gateway, 9Router, FreeLLMAPI, worker, active development session, or production configuration was changed.

## Decision requested from Owner

**Recommendation: Trust All = GO, conditional on reviewing this file and the checked-in conservative `config.json`.** Approve the five hooks together through Codex's native `/hooks` review. Do not use a trust bypass. Codex does not run them in the session that grants trust; restart Codex after approval. If the Owner does not accept local session/tool-event logging described below, the combined recommendation is NO-GO.

This is a recommendation, not evidence that the hooks have been trusted or activated. At audit time the plugin is enabled in the user Codex configuration, but the trust decision is not exposed by the inspected configuration. The Codex UI trust review remains authoritative.

## Conservative repository configuration

The root `config.json` added with this audit sets:

- `microskills=envfacts`, with at most 5 facts / 200 tokens. This profile derives facts locally and does not call an optimizer model.
- `toolprune=off`: no capability/tool is proposed or disabled; testing, collaboration, web, image, and other tools remain available.
- `loopguard=off`: no judge, redirect, or mid-turn intervention.
- `repomap=off`: no repository map generation.

Environment overrides (including `TE_*`) have higher precedence than this file and can change these choices. Review the running environment before activation. No tool-prune application or Codex capability change was made. The environment-facts block may add a small amount of context; no token saving is claimed without measurement.

## Five-hook audit

Codex's `hooks/codex-hooks.json` registers exactly these five events. Every entry invokes the same `scripts/te-hook --host codex` dispatcher with event-specific timeouts. The dispatcher fails open with an empty JSON response on errors and supports `TE_DISABLE=1`.

| Hook | Observed purpose and effects | Assessment under checked-in configuration |
|---|---|---|
| `SessionStart` | Resolves repository/session context, loads cached facts, prepares local state/CLI launcher and announces applicable state. A first hook can create private TokenEconomizer state. | GO. Facts only; no optimizer call. State/launcher writes are local. |
| `UserPromptSubmit` | Starts a prompt-turn record for loop detection and records prompt/session evidence. | GO. Loop guard is off, so no judge or redirect is requested. Local evidence may contain prompt-derived data. |
| `PostToolUse` | Records tool name/input/result and tool outcome for later learning and accounting. The hook itself does not remove tools. | GO with data-handling caveat: tool commands/results can contain sensitive material; derived records remain local and should be protected like session logs. |
| `Stop` | Closes/updates turn state and would evaluate loop-guard behavior. | GO. Guard is off; it does not redirect or stop the Codex turn. |
| `SessionEnd` | Folds completed local session evidence into repository learning/accounting and updates local state. | GO. Envfacts path does not invoke a model. It may retain derived command/tool/session metadata locally. |

The entries have bounded timeouts (15s, 10s, 60s, 10s, 3s respectively). Each event's behavior depends on shared dispatcher, configuration, and local state; approving only selected events is not recommended because it can leave partial session accounting.

## Security, dependencies, filesystem, network and compatibility

- **Integrity:** source checkout `/home/sanro/TokenEconomizer` has official remote `https://github.com/microsoft/TokenEconomizer.git`; local `HEAD` equals `origin/main` at `46b0a356dc08f01064fa683d9f7d6988dc5deade` (2026-11-24), and the worktree is clean. Installed plugin cache matches the source `plugin/` tree except the source-only `lib/tokeneconomizer` link. This is an expected Codex packaging difference: the installed bootstrap resolves the Python package from the configured local marketplace source. No file-content discrepancy was found in the remaining plugin tree.
- **Hook payloads:** the installed hook manifest's SHA-256 is `f06a40d2017487b3382e4786d19731bfff6fe8b7c3d58de619fd5d9886588fde`. Launcher/bootstrap hashes: `te-hook` `445639b9c2aaeb56b2694e2b6fb850acd0e9326aa863f380f423ec30cf8985a5`; `te_bootstrap.py` `e4fef3422ae5d413efeab71138c501082e432fb7d15dff5537af74ec474925d0`; `te` `d863a58cb7a3c5b0be61bc25e705371f2f52facdcdab8f5de80b6b2e1c76ad0b`.
- **Dependencies:** the runtime package declares Python `>=3.10`, standard-library-only runtime and no install dependencies. Codex hook entrypoints are Python/shell; no npm package is involved in Codex execution. Host Python is 3.14.4, so the declared minimum is met.
- **Filesystem:** expected writes are TokenEconomizer's private state under `~/.tokeneconomizer` (session/ledger/error data and launcher), plus evidence/state read from the current repository. Tool pruning can edit project `.codex/config.toml`, but is disabled here. The hook code reads Codex hook payloads and local session/tool evidence; commands and tool output can themselves include sensitive strings. No secrets were inspected or copied into this report. Keep state private and do not commit it.
- **Credentials/network:** hook code can launch an agent CLI for model-backed side-calls when features requiring a judge/proposer/redirect are enabled; those calls can use that CLI's existing login and incur usage. The checked-in settings disable those features; envfacts needs no credentials or network. No direct network client is used by this configured path. This audit made no model call or external service request beyond read-only GitHub repository/PR inspection.
- **Compatibility:** Codex reports `0.162.1`, matching the stated deployment. The installed manifest uses the five Codex event names above and invokes the bootstrap with `--host codex`. The local `codex --version` command emitted a read-only-PATH-alias warning; it still reported version `0.162.1`. No CLI update was attempted.

## Evidence and status at audit time

- **PASS:** official source ref equality and clean worktree; installed/source plugin file comparison (with expected dropped source link); host Python meets requirement; Codex CLI version matches; conservative config committed to this branch.
- **NOT VERIFIED:** Codex hook trust, runtime activation, hook execution, smoke test, session ledger and savings. The status skill command could not run because `~/.tokeneconomizer/bin/te` does not exist yet. No hooks were invoked or approval prompt bypassed. Token savings are **unmeasured**.
- **No changes:** no CLI update/reinstall, service or cost increase, worker/session disruption, Gateway/9Router/FreeLLMAPI change, merge or deployment.

## Owner approval, smoke test and measurement

1. Review this audit and `config.json`, then in Codex use `/hooks` and approve **Trust all and continue** if accepted. Do not use `--dangerously-bypass-hook-trust`.
2. Exit and start a new Codex session in this repository. Verify the hooks page shows the plugin hooks trusted, and run the TokenEconomizer `status` skill/command. Confirm config reports `microskills=envfacts toolprune=off loopguard=off repomap=off`.
3. Run a harmless coding/documentation prompt and one harmless tool call; confirm normal tools/testing remain available, no loop redirect appears, and the session status records the run without errors. Do not use production or real secrets as smoke-test data.
4. Measure only after a baseline and treated session with comparable task/model/tooling. Compare reported input/output/cache/optimizer tokens and task outcome. Because envfacts adds context, count its injected tokens. Do not describe gross context reduction as net savings without an equivalent-quality comparison.

## Rollback

- Immediate per-session opt-out: set `TE_DISABLE=1` before starting Codex.
- Revoke the hook trust in Codex's native `/hooks` UI; this stops hook execution without uninstalling or changing the CLI.
- To retain trust but turn off all mechanisms, set `microskills=off`, `toolprune=off`, `loopguard=off`, and `repomap=off` in this repository's `config.json` (or equivalent `TE_*` environment values), then restart the session.
- No tool-prune deny list was applied, so no `toolprune restore` is needed. Removing the plugin is unnecessary for rollback and was not done.

**Current integration state:** source verified; conservative repository config prepared; trust pending Owner; runtime smoke test and savings measurement pending.
