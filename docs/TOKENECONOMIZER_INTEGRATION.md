# TokenEconomizer v0.1.0 integration audit

**Date:** 2026-11-25  
**Scope:** Installed Codex plugin and its five Codex hook events, for the SANRO AI Workforce repository only. No Gateway, 9Router, FreeLLMAPI, worker, active development session, or production configuration was changed.

## Decision requested from Owner

**Recommendation: Trust All = GO, conditional on reviewing this file and the checked-in conservative `config.json`.** Approve the five hooks together through Codex's native `/hooks` review. Do not use a trust bypass. Codex does not run them in the session that grants trust; restart Codex after approval. If the Owner does not accept local session/tool-event logging described below, the combined recommendation is NO-GO.

This is a recommendation, not evidence that the hooks have been trusted or activated. At audit time the plugin is enabled in the user Codex configuration, but the trust decision is not exposed by the inspected configuration. The Codex UI trust review remains authoritative.

## Configuration correction and pilot follow-up

Correction to the initial report: a repository-root `config.json` is **not** read by this plugin. TokenEconomizer loads repository settings from `$TOKENECONOMIZER_HOME/repos/<repo-key>/config.json`. The ineffective root config file was removed from the Draft PR.

An isolated Codex pilot now has an effective per-repository configuration written with the installed v0.1.0 plugin CLI and verified using `te --host codex --cwd <pilot-repo> config show` under confinement:

- `microskills=envfacts`, maximum 5 facts / 200 tokens; no proposer model call.
- `toolprune=off`; no tools are removed.
- `loopguard=off`; no judge or turn redirect.
- `repomap=off`.

The pilot state lives only under `/tmp/sanro-tokeneconomizer-pilot-20261125/state` with private permissions. See [isolated pilot evidence](TOKENECONOMIZER_PILOT.md). Environment overrides (`TE_*`) have higher precedence and were absent in the pilot's clean environment.

No tool-prune application or Codex capability change was made. Envfacts may add context; savings remain unmeasured.

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

## Evidence and status

- **PASS:** official source ref equality and clean worktree; installed/source plugin file comparison (with expected dropped source link); host Python meets requirement; Codex CLI version matches.
- **PASS — isolated pilot preparation:** separate Codex home and state; synthetic-only fixture; plugin CLI reports installed/enabled v0.1.0; effective config loader output matches the conservative values; state permissions and Landlock filesystem/network preflight pass. Details and hashes are recorded in [pilot evidence](TOKENECONOMIZER_PILOT.md).
- **BLOCKED:** trust and hook activation. Isolated Codex v0.162.1 requires sign-in before `/hooks` is available; no credentials were accessed and no hook was invoked. Global Codex approval would exceed pilot scope, so was not used.
- **NOT MEASURED:** hook runtime smoke/latency, coding quality, baseline-vs-treated tokens and savings. Pilot has no credentials and network access is denied; no model run was made.
- **No changes:** no CLI update, worker/session disruption, Gateway/9Router/FreeLLMAPI change, merge or deployment.

## Owner approval, smoke test and measurement

The isolated UI was prepared, but it stops at sign-in before `/hooks`. Under the no-credential constraint, the Trust All review cannot be reached. Do not approve from the normal/global Codex UI because its trust scope would extend beyond this pilot. Do not use `--dangerously-bypass-hook-trust`. The pilot remains blocked before hook execution; no smoke test or latency measurement has been run. Coding quality and token comparisons also require a no-cost, credentialless model path, which is not available in this pilot.

## Rollback

- Stop the isolated pilot with `/exit` or Ctrl+C.
- Revoke pilot hook trust in that pilot's native `/hooks` UI. Global Codex trust/config is separate and was not changed.
- `TE_DISABLE=1` disables hooks for a process. To turn mechanisms off while retaining pilot trust, use `te --host codex --cwd <pilot-repo> config set microskills=off toolprune=off loopguard=off repomap=off`.
- No tool-prune deny list was applied, so `toolprune restore` is not needed.

**Current integration state:** source verified; effective conservative runtime config verified in isolated pilot; pilot trust blocked by required sign-in; no smoke or latency run; coding quality and token savings unmeasured; global activation not authorized.
