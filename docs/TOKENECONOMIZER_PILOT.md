# TokenEconomizer isolated Codex pilot — preparation evidence

**Date:** 2026-11-25  
**Integration:** SANRO AI Workforce Draft PR #2, branch `feature/hermes-workforce-foundation`  
**Pilot root:** `/tmp/sanro-tokeneconomizer-pilot-20261125`

## Scope and current gate

This is an isolated pilot preparation, not activation across workers. The pilot uses a synthetic-only discount calculator fixture and a separate Codex home/state root. The plugin is enabled only in that home. No worker, project repository, Gateway, 9Router, FreeLLMAPI, or global Codex configuration was changed.

**Owner gate: pending.** The five hooks have not been trusted or invoked. To review/approve through Codex's native mechanism, launch the isolated pilot from a terminal:

```sh
/tmp/sanro-tokeneconomizer-pilot-20261125/start-pilot-codex.sh
```

In that Codex UI, use `/hooks` and choose **Trust all and continue** only if the hook list and this evidence are acceptable. The isolated `CODEX_HOME` means that approval is scoped to this pilot and does not approve hooks in the normal/global Codex home. Restart using the same script after approval. Do not use a trust bypass. Send confirmation after approval so the smoke phase can continue.

## Runtime configuration — verified in pilot

The previous integration report and root `config.json` implied that a repository-root file controls plugin configuration. That was wrong: TokenEconomizer loads per-repository config from `$TOKENECONOMIZER_HOME/repos/<repo-key>/config.json`. The root file was removed from the Draft PR.

For this pilot, the already-installed v0.1.0 plugin CLI was run with a clean environment and pilot-only paths:

- `TOKENECONOMIZER_HOME=/tmp/sanro-tokeneconomizer-pilot-20261125/state`
- synthetic repo: `/tmp/sanro-tokeneconomizer-pilot-20261125/repo`
- Codex host: `codex`

The CLI `config set` wrote to `state/repos/repo-a00c0b0da2/config.json`, mode `0600`; state root mode is `0700`. A subsequent `te --host codex --cwd <synthetic repo> config show`, run again under the pilot filesystem/network confinement, returned without warnings:

- microskills: `envfacts`, maximum 5 facts / 200 tokens
- toolprune: `off`
- loopguard: `off`
- repomap: `off`

This verifies the plugin's config loader resolves the actual host/repository state for this pilot. Hook-time loading remains to be confirmed after native hook approval.

## Pilot setup and isolation evidence

- Pilot Codex reports `tokeneconomizer@tokeneconomizer installed, enabled 0.1.0` in the isolated home. The existing Codex CLI binary/version is used; no CLI update was run. The pilot cache was materialized from the configured local Microsoft source at the same v0.1.0; the global install/config/cache were not changed.
- The pilot uses a clean environment whitelist. Its `HOME`, `CODEX_HOME`, `TOKENECONOMIZER_HOME`, temporary directory, and XDG cache/config paths all point inside the pilot root. No auth or credentials files exist in the pilot homes; no credential values were read.
- Landlock reports ABI 8. The pilot launcher applies a restrictive filesystem ruleset before starting Codex: standard runtime paths and the official source/Codex package are read-only; writable paths are limited to the pilot root. It allows only the current process's procfs view, not a general view of other user processes.
- Confinement preflight passed: attempts to open the existing global Codex auth/credentials files, open another project tree, and write the read-only official source were denied. These checks opened no secret contents. A TCP socket creation probe failed with `EPERM` under the host policy; the Landlock ruleset also denies TCP bind/connect. No external network request was made by the pilot.
- `bwrap` user namespaces were unavailable and the Docker socket was not accessible; the pilot uses Landlock instead. This has not been used to run hooks yet.

Synthetic task fixture: `repo/PILOT_TASK.md`, `repo/discount.py`, and `repo/tests/test_discount.py`. The starter implementation is intentionally incorrect; no tests were run before trust approval.

## Test and measurement status

| Measure | Status | Evidence |
|---|---|---|
| Effective conservative config | **PASS** | Pilot plugin CLI `config show` under confinement; exact settings above |
| Plugin in isolated Codex home | **PASS** | `codex plugin list` reports installed/enabled v0.1.0 |
| Pilot state permissions | **PASS** | state root `0700`, config `0600` |
| Exclusion of global credential/project paths | **PASS** | confined open attempts denied; no contents read |
| Network isolation | **PASS** | TCP socket creation denied; Landlock bind/connect denied |
| Five-hook trust and activation | **PENDING OWNER** | not approved, no hook executed |
| Hook smoke test and latency | **PENDING** | run after Owner trust |
| Coding-quality comparison | **PENDING / constrained** | requires equivalent model execution; pilot has no credentials/network |
| Token savings | **NOT MEASURED** | no baseline/treated model sessions; no savings claim |

The no-credential/no-network boundary prevents a Codex model call from this pilot. After trust, hook event smoke and latency can be measured without credentials. A comparable model-quality or token comparison cannot be claimed unless a credentialless, no-additional-cost model path is made available; do not inject another project's auth into the pilot.

## Rollback

1. Stop the pilot Codex process with `/exit` or Ctrl+C.
2. Revoke only the pilot hook trust in its `/hooks` UI. Global Codex trust/config is separate and was not changed.
3. The entire pilot state and fixture are under `/tmp/sanro-tokeneconomizer-pilot-20261125`; no cleanup is necessary for safety. If later cleaning it, preserve the evidence first and remove only that exact pilot directory.

## Next action

Owner approval in the isolated Codex UI is the only gate before invoking hook runtime. Global activation remains unrequested and requires a separate Owner approval. Draft PR #2 remains unmerged and undeployed.
