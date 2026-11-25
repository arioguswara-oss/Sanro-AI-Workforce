# Job History

| Job ID | Project | Worker | Profile | Queue | Result | Herdr evidence |
|---|---|---|---|---|---|---|
| `788abd731ec242509dc359df4d746f0b` | `sanro-ai-workforce` | `sanro-workforce-pilot` / `t3` | `synthetic` (`/usr/bin/sleep 2`) | Serial/FIFO | `COMPLETED`, exit `0`; queued → running → succeeded | OSC 7501 record `done`; terminal remains live/idle |

The job used no AI provider or model quota. Its execution verified the Workforce API, scoped approval, HermesAdapter FIFO queue, Herdr supervisor registration, and per-job Herdr status reporting. It did not invoke a Hermes model/session or prove an AI response. Android Spaces and Inbox visual checks remain pending.

Owner later reported the pilot visible/openable in Android but with a blank terminal and brief OFFLINE badge. A read-only server check confirmed t3 live/idle and the prior Core job record `done`/`reported=true`; terminal screen was empty. No new job was executed in the follow-up because the active API dispatch path was not identified. See [partial acceptance evidence](evidence/HERDR_ANDROID_PARTIAL_ACCEPTANCE_20261125.json).

| `50cd39f892d641e1a67c065a17f49c55` | `sanro-ai-workforce` | `sanro-workforce-pilot` / `t4` | `visible` fixed printf synthetic | Serial/FIFO | `COMPLETED`, exit `0`; queue succeeded | Terminal shows running/completed lines; Core OSC 7501 record `done`, `reported=true` |

The job used no AI provider or model quota. It was submitted through the Workforce API, consumed by HermesAdapter's FIFO worker queue, and reported by the Herdr supervisor. Owner's final Android Spaces/Inbox visual check for t4 remains pending.
