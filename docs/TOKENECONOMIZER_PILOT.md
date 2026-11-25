# TokenEconomizer isolated Codex pilot — preparation evidence

**Date:** 2026-11-25  
**Integration:** SANRO AI Workforce Draft PR #2, branch `feature/hermes-workforce-foundation`  
**Pilot root:** `/tmp/sanro-tokeneconomizer-pilot-20261125`

## Scope and current gate

This is an isolated pilot preparation, not activation across workers. The pilot uses a synthetic-only discount calculator fixture and a separate Codex home/state root. The plugin is enabled only in that home. No worker, project repository, Gateway, 9Router, FreeLLMAPI, or global Codex configuration was changed.

**Owner gate: pending.** The five hooks have not been trusted or invoked. The pilot launcher permits outbound TCP 443 only for official sign-in; TCP bind and other ports remain denied. Launch `/tmp/sanro-tokeneconomizer-pilot-20261125/start-pilot-codex.sh`; choose **Sign in with ChatGPT** (Device Code suitable, no API key), then `/hooks` → **Trust all and continue** after reviewing the five hooks and this evidence. This bundled Owner approval applies to the isolated pilot home only. Exit/restart the same script and notify us for a short smoke. Never paste credentials/codes into chat or bypass trust.

Global Codex trust remains separate and is NO-GO pending separate Owner approval. 

## Runtime configuration — verified in pilot

The previous integration report and root `config.json` implied that a repository-root file controls plugin configuration. That was wrong: TokenEconomizer loads per-repository config from `$TOKENECONOMIZER_HOME/repos/<repo-key>/config.json`. The root file was removed from the Draft PR.

For this pilot, the already-installed v0.1.0 plugin CLI was run with a clean environment and pilot-only paths:

- `TOKENECONOMIZER_HOME=/tmp/sanro-tokeneconomizer-pilot-20261125/state`
- synthetic repo: `/tmp/sanro-tokeneconomizer-pilot-20261125/repo`
- Codex host: `codex`

The CLI `config set` wrote to `state/repos/repo-a00c0b0da2/config.json`, mode `0600`; state root mode is `0700`. SHA-256: runtime config `ea572716394e05048ebef67de4a6177086b18a5501515f261f863c8aaabf93a2`; current Landlock launcher `f1355160bb0b20e613e86626686d1b47dd870042756deb2cab68eb281855ba15`; pilot start script `45e6cb43eef164d8517a12a243dff2e27b47c1246e104166351cf40c797d69ee`. A subsequent `te --host codex --cwd <synthetic repo> config show`, run again under the pilot filesystem/network confinement, returned without warnings:

- microskills: `envfacts`, maximum 5 facts / 200 tokens
- toolprune: `off`
- loopguard: `off`
- repomap: `off`

This verifies the plugin's config loader resolves the actual host/repository state for this pilot. Hook-time loading remains to be confirmed after native hook approval.

## Pilot setup and isolation evidence

- Pilot Codex reports `tokeneconomizer@tokeneconomizer installed, enabled 0.1.0` in the isolated home. The existing Codex CLI binary/version is used; no CLI update was run. The pilot cache was materialized from the configured local Microsoft source at the same v0.1.0; the global install/config/cache were not changed.
- The pilot uses a clean environment whitelist. Its `HOME`, `CODEX_HOME`, `TOKENECONOMIZER_HOME`, temporary directory, and XDG cache/config paths all point inside the pilot root. No auth or credentials files exist in the pilot homes; no credential values were read.
- Landlock reports ABI 8. The pilot launcher applies a restrictive filesystem ruleset before starting Codex: standard runtime paths and the official source/Codex package are read-only; writable paths are limited to the pilot root. It allows only the current process's procfs view, not a general view of other user processes.
- Confinement preflight passed: attempts to open the existing global Codex auth/credentials files, open another project tree, and write the read-only official source were denied. These checks opened no secret contents. For official sign-in, Landlock permits outbound TCP 443 to any destination; it does not apply a host allowlist. TCP bind and other ports remain denied. Local port 9 denial and launcher preflight passed. No external network request was made by the agent.
- `bwrap` user namespaces were unavailable and the Docker socket was not accessible; the pilot uses Landlock instead. This has not been used to run hooks yet.

Synthetic task fixture: `repo/PILOT_TASK.md`, `repo/discount.py`, and `repo/tests/test_discount.py`. The starter implementation is intentionally incorrect; no tests were run before trust approval.

## Test and measurement status

| Measure | Status | Evidence |
|---|---|---|
| Effective conservative config | **PASS** | Pilot plugin CLI `config show` under confinement; exact settings above |
| Plugin in isolated Codex home | **PASS** | `codex plugin list` reports installed/enabled v0.1.0 |
| Pilot state permissions | **PASS** | state root `0700`, config `0600` |
| Exclusion of global credential/project paths | **PASS** | confined open attempts denied; no contents read |
| Network confinement | **PASS** | TCP 443 egress to any host; other ports/bind denied; local port 9 denied; no request by agent |
| Five-hook trust and activation | **PENDING OWNER** | sign-in and native trust review are pending; no hook executed |
| Hook smoke test and latency | **PENDING** | run one short smoke after Owner trust and restart |
| Coding-quality comparison | **PENDING / scoped** | synthetic task after pilot sign-in; do not claim beyond that task |
| Token savings | **NOT MEASURED** | no baseline/treated model sessions; no savings claim |

Before Owner sign-in no model call is available. Owner may use ChatGPT included-plan sign-in in this isolated pilot; no API key or another project's auth. After trust/restart run one short synthetic fix/test smoke. Token savings stay unmeasured pending gradual comparable evidence during authorized development.

## Rollback

1. Stop the pilot Codex process with `/exit` or Ctrl+C.
2. Revoke only the pilot hook trust in its `/hooks` UI. Global Codex trust/config is separate and was not changed.
3. The entire pilot state and fixture are under `/tmp/sanro-tokeneconomizer-pilot-20261125`; no cleanup is necessary for safety. If later cleaning it, preserve the evidence first and remove only that exact pilot directory.

## Next action

Owner sign-in and bundled five-hook trust in the isolated pilot are pending. After Owner confirms restart, run one brief smoke and record runtime config, hook events, filesystem placement, tool/test availability and latency. Token savings are not measured. Global activation is NO-GO without separate Owner approval. Draft PR #2 remains unmerged and undeployed.
