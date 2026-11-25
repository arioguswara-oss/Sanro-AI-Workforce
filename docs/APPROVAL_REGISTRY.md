# Approval Registry Snapshot

This file records the bounded owner authorization used for the runtime pilot. It is an evidence snapshot, not a live credential or a production policy file.

| Approval | Subject | Scope | Project | Environment | Allowed | Forbidden | Status |
|---|---|---|---|---|---|---|---|
| `owner-worker-manage-herdr-pilot-20261125` | Owner authorization in this session | One `worker:manage` activation and one approved synthetic `engineering:execute` job | `sanro-ai-workforce` | Isolated synthetic pilot on existing VPS Herdr Core | Start one named supervisor; run one fixed `/usr/bin/sleep 2` job; inspect pilot status | Existing worker changes, Gateway/config changes, secrets/auth changes, hooks, production, paid calls, merge/deploy | Consumed for the one pilot; no reusable token or auth file retained |

The API fixture's short-lived synthetic token hash and authorization file were deleted after app initialization. The synthetic job completed before the approval window ended. This record does not authorize future jobs or activation for other projects/workers.
