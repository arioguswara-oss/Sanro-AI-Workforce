# TokenEconomizer authentication diagnosis — 2026-11-25

## Classification and scope

TokenEconomizer is **OPTIONAL / EXPERIMENTAL**. It is not a dependency of Codex CLI, SANRO AI Workforce, or the primary development workflow. The isolated pilot is not a release or runtime gate. The existing installation and current global configuration were left unchanged; no additional global activation occurred.

## Evidence gathered without credentials

- The official Device Code request in pilot session 34885 failed before producing a code: `failed to request device code`, endpoint `https://auth.openai.com/api/accounts/deviceauth/usercode`, client error `-32603`.
- A normal, credential-free DNS probe resolved `auth.openai.com`. A separate HTTPS GET to the official host returned HTTP `302` with TLS verification result `0` (certificate verification succeeded). No sign-in request or credentials were sent by this probe.
- A normal probe inside the restricted sandbox could not resolve the host. An earlier pilot-context probe through the launcher also failed DNS resolution (curl exit 6); the TLS phase was not reached.
- `/etc/resolv.conf` points to the local systemd-resolved stub at `127.0.0.53`.
- Static review of the existing launcher shows `env -i` and a deliberately reduced environment. The Landlock helper handles TCP bind/connect and grants outbound TCP connect only on port 443. It has no explicit DNS exception. Its filesystem restrictions and credential-exclusion preflight were retained.

## Root cause

Authentication failed at the pilot's confined DNS/network boundary, before TLS or OAuth credentials could be evaluated. The ordinary network path resolves the official host and completes TLS; the pilot path cannot resolve it. This is not evidence of an account, password, or Codex auth-config failure. The exact resolver syscall that is denied was not separately instrumented; the proven blocker is DNS unavailability inside the pilot boundary.

## Disposition

- The pilot terminal was stopped after the failed official auth attempt. No repeat Device Code request was made.
- No credential, API key, token, or global auth file was read, copied, or written. No hook was trusted or invoked; no smoke test or token benchmark ran.
- TokenEconomizer remains untrusted in the pilot, and there was no global hook/config change, reinstall, Codex update, worker interruption, merge, or production deployment.
- **NO-GO** for pilot authentication, hook trust, and runtime smoke until the pilot can resolve required official auth hosts through an approved, narrowly scoped egress path.

## One concrete resolution

Provide a dedicated pilot egress proxy or network-namespace policy that permits DNS for an explicit resolver and HTTPS only to the official OpenAI authentication/runtime host allowlist, while retaining the current Landlock filesystem rules and denying direct arbitrary egress. Do not inject proxy credentials into the agent environment. Revisit the pilot only after that policy is independently reviewed and approved.
