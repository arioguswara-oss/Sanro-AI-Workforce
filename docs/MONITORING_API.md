# Superadmin Virtual Office — read-only contract v1

`GET /api/monitoring/v1/projects/{project_id}` returns JSON. Loopback listener by default; no public exposure configured. A future Superadmin server-side proxy may use a dedicated private Bearer credential. Do not put the credential in a browser bundle, URL, query string or public repo. Transport/access deployment is a separate mandate; Superadmin repository is untouched.

Authorization: deny by default; exact project/workspace grant with ONLY `monitor:read`. Credentials combining monitoring and operational scopes are rejected at startup, including across projects. Monitoring principals are denied all operational endpoints. Missing auth → 401; unauthorized project → 404; non-GET → 405; query parameters → 400. No terminal, task submission, worker lifecycle, approval mutation, merge or deployment route exists under monitoring.

| Field | Meaning |
|---|---|
| `schema_version`, `project_id`, `generated_at`, `read_only` | Contract identity; generation time is response creation, not proof of live data |
| `workers[]` | Fixed logical identity/role, status, project, run/job IDs, heartbeat, data state and age; unobserved logical profile is `unknown`, not online |
| `runs[]` | Task/run/job ID, state/stage, commit SHA, test status, fixed blocker enum, evidence progress, latest checkpoint, freshness |
| `jobs[]`, `queue` | Sanitized persisted checkpoint history, queued/running counts; not a live worker probe |
| `models[]` | Provider ID, DISABLED or UNAVAILABLE, quota UNAVAILABLE until account source is integrated |
| `approval` | Pending count from private registry snapshot; live native approval status UNAVAILABLE |
| `reports` | Total queued records and acknowledged delivery count; queued report is not proof of Telegram receipt |
| `draft_pr` | Optional HTTPS GitHub PR URL strictly matching configured repository |
| `history[]` | Fixed event names, entity IDs and freshness; no actors, notes, instructions or logs |
| `hermes_health` | UNAVAILABLE until authorized live health source is connected |

Freshness uses a trusted server threshold (default 60 seconds, bounded 1 second–1 hour), never a client parameter. `CURRENT` means observation age within that threshold; `STALE` means older; missing/invalid/future timestamp means `UNAVAILABLE`. Stale worker status becomes unknown. Queue counts retain their persisted-state source label; inspect per-job freshness before interpreting them. Offline is reported only if explicitly observed.

Progress is conservative: 100% only for a completed isolated workflow with matching fixed-profile QA checkpoint/SHA; otherwise 0% (`NO_COMPLETED_VERIFIED_CHECKPOINT`). This is task evidence progress, not overall product completion or live autonomy. Manual/caller-supplied checkpoints are not promoted. Test status and source distinguish PASS, FAIL, NOT_TESTED. History is bounded to 100 jobs/runs and 30 events; queue counts include all persisted jobs.

The projection executes SELECT statements only. It never invokes the worker adapter, refreshes checkpoints, drains notifications, writes audit entries or makes network calls. It excludes task title/description, prompts, messages, private paths, command profiles, tokens, raw errors and logs. Literal enums and IDs/SHA are validated. Listener logs must not include authorization headers.

## Reusable component mapping

| Existing component/source | Future Superadmin destination | Decision |
|---|---|---|
| `apps/web/src/components/WorkforceMonitor.jsx` | Virtual Office worker/task tables | Reusable presentation-only component; receives DTO, has no fetch/token/mutation functions |
| `apps/web/src/main.jsx` project selector/task/job views | Host layout reference only | Preserve original source; standalone chat and submission controls excluded from monitoring |
| `apps/web/src/style.css`, `extra.css` | Optional design references | No Superadmin modification or deployment in this mandate |
| `apps/api/src/monitoring.js` | Server-side data contract | Keep in Workforce backend, project-scoped proxy in future mandate |

Build component independently with `npm exec vite build -- --config vite.monitor.config.js` from `apps/web`. Original app remains preserved and is not the recommended conversation surface. Hermes Web UI/Android/Telegram remain authoritative.
