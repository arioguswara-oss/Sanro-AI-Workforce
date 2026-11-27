# Approval Registry Snapshot

This file records the bounded owner authorization used for the runtime pilot. It is an evidence snapshot, not a live credential or a production policy file.

| Approval | Subject | Scope | Project | Environment | Allowed | Forbidden | Status |
|---|---|---|---|---|---|---|---|
| `owner-worker-manage-herdr-pilot-20261125` | Owner authorization in this session | One `worker:manage` activation and one approved synthetic `engineering:execute` job | `sanro-ai-workforce` | Isolated synthetic pilot on existing VPS Herdr Core | Start one named supervisor; run one fixed `/usr/bin/sleep 2` job; inspect pilot status | Existing worker changes, Gateway/config changes, secrets/auth changes, hooks, production, paid calls, merge/deploy | Consumed for the one pilot; no reusable token or auth file retained |
| `SANRO-QA-PILOT-OPS-V1` | Rio (Owner) | One project-scoped synthetic `qa:execute` + `runtime:browser`; branch `main` is read-only; 0 USD; valid through `2026-12-28T23:59:59Z` | `sanro-browser-qa` / `arioguswara-oss/SANRO-Browser-QA` / pinned SHA `4436660bfc4dbdf11aadb0800b043c2c75ce6eaa`; worker `sanro-qa` | Isolated Local CI synthetic browser acceptance | Run the fixed Workforce-owned QA entrypoint with Chromium sandbox enabled and per-job evidence outside the pilot checkout | engineering/write, git write, worker management, SSH, merge, production, paid APIs, other repository write, network egress | Owner mandate recorded; private host registration pending; native per-job approval remains separately required |

The API fixture's short-lived synthetic token hash and authorization file were deleted after app initialization. The synthetic job completed before the approval window ended. This record does not authorize future jobs or activation for other projects/workers.

The Owner's later instruction authorized troubleshooting and restarting this same idle pilot plus one further synthetic job with visible lifecycle output, keeping Core, Hermes, production configuration, hooks, and existing workers outside scope. The bounded follow-up was consumed by job `50cd39f892d641e1a67c065a17f49c55`; no reusable authorization is implied. See [final runtime acceptance evidence](evidence/HERDR_RUNTIME_FINAL_ACCEPTANCE_20261125.json).
