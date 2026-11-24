# Rencana Implementasi SANRO AI Workforce
Tanggal keputusan: 22 November 2026
Status: **DECIDED / PLANNED**. Dokumen ini bukan bukti implementasi, aktivitas VPS, atau persetujuan deployment.

## 1. Sasaran dan batas produk
Bangun platform karyawan AI **internal SANRO**, bukan SaaS untuk pelanggan, dengan:
1. **Web Chat mirip ChatGPT:** sidebar percakapan, pilihan proyek, chat individu per agent, group chat, @mention, riwayat, status job realtime, evidence dan Approval Center.
2. **Telegram Group privat:** empat bot terpisah (Director, Developer, QA, DevOps) dengan identitas/avatar masing-masing, Topics per proyek, dan pesan yang tersinkron dengan web.
3. **Satu backend dan ledger:** agent routing, event/queue, checkpoint, memory dan job evidence. Telegram hanyalah antarmuka, bukan sumber eksekusi.
4. **Development dari konsep hingga Draft PR:** Owner menetapkan tujuan/mandat; Director membagi pekerjaan; Developer coding; QA tes; DevOps menangani build/staging berizin; hasil dikembalikan untuk acceptance.
5. **Minimal approval:** tidak perlu GO tiap langkah dalam mandat aktif, tetapi merge, deploy production, transaksi/DB nyata, secrets/akses, penghapusan data, biaya, dan perluasan cakupan memerlukan approval spesifik.

### Non-goals fase awal
Tidak membangun SaaS/billing publik, tidak menambah VPS/bot gateway berbayar/database server baru, tidak membuat model AI sendiri, tidak migrasi repo/proyek lama, tidak mengubah worker aktif, tidak auto-merge/production deploy.

## 2. Sumber kebenaran dan aset existing
- Repository pengembangan: `arioguswara-oss/Sanro-AI-Workforce` (public atas keputusan Owner). **Jangan commit token, secret, data customer, chat privat, raw evidence, atau mandat aktif.**
- Reuse: existing worker/supervisor, locking, knowledge, billing, and QA capabilities only after source, commit, and runtime status are independently verified. A pull request or candidate is not evidence that a capability is installed or active.
- Hermes runtime: possible worker/CI integration target. Runtime services, authentication, sandbox, queue, network, and resource state must be verified read-only before any activation.
- Pilot project: a separately approved non-production project; do not change production or staging without the corresponding authorization.
- Repo proyek SANRO yang sudah ada tetap pada tempatnya. SANRO AI Supervisor tetap sumber reusable executor; Workforce menjadi control plane baru dan dua antarmuka komunikasi.

## 3. Rancangan arsitektur
```text
OWNER ── Web Chat (personal/group) ─┐
      └─ Telegram Group (4 bots) ───┤
                                   ▼
                    Unified Communication API
                       ├─ Identity & Access
                       ├─ Thread + Message Store
                       ├─ Telegram adapters + outbox
                       └─ Web realtime events (SSE)
                                   ▼
                  AI Director / Policy Orchestrator
                     Project & Approval Registry
                       Task Ledger / Job Queue
                    Checkpoint / Evidence Index
                                   ▼
                 Hermes / Supervisor adapter (read-only first)
                      ├─ Developer (Codex)
                      ├─ QA (CI / Playwright)
                      └─ DevOps (build / staging berizin)
                                   ▼
                      Draft PR + evidence + report
```
- Node.js backend + React web frontend; gunakan SSE untuk update satu arah dan HTTP untuk pengiriman chat/job. Evaluasi persisten store lokal yang sudah ada; jangan pasang layanan DB eksternal tanpa kebutuhan dan approval.
- Satu backend otoritatif; semua message/job memiliki stable IDs dan `project_id`, `thread_id`, `actor_id`, `origin`, `correlation_id`, `job_id` (jika relevan).
- Bot Telegram **tidak mengambil keputusan dari pesan bot lain**. Event internal yang telah diverifikasi memicu pekerjaan; pengiriman bot hanya memantulkan aktivitas. Gunakan idempotency, rate limits, origin flags, dan outbox retry agar tidak terjadi loop/duplikasi.
- Chat personal tiap agent dipisah dari grup; pesan pribadi tidak otomatis dipublikasikan ke Telegram. Tidak semua pesan teknis perlu dikirim ke Telegram; cukup aktivitas penting.
- Backend mengikat identitas Telegram Owner ke akun Owner, bot, group ID, dan thread topic IDs; akses web memakai login/session/CSRF sesuai threat model.

## 4. Peran dan kontrak pekerjaan
| Agent | Input | Output | Kewenangan |
|---|---|---|---|
| Director | tujuan, mandat, checkpoint, issues | prioritas max 5 tugas, assignment, laporan | tidak boleh memperluas izin |
| Developer | task terstruktur, repo/branch/SHA, allowlist | patch, test awal, commit, Draft PR berizin | worktree terisolasi |
| QA | SHA kandidat, acceptance, skrip CI/E2E | PASS/FAIL, evidence terikat SHA | tes terbatas; no production write |
| DevOps | manifest build/staging, izin environment | build/status/staging evidence | tidak deploy prod tanpa approval |

Analyst, Designer, Documentation sebagai **mode kerja opsional**, bukan service/paket model baru.

### Task lifecycle / internal messages
`TASK_CREATED → TASK_ASSIGNED → CODE_READY → QA_RUNNING → QA_PASS | QA_FAIL → SELF_FIX (terbatas) → QA_PASS → DRAFT_PR_READY → REPORTED`.
- FAIL boleh kembali ke Developer dengan evidence dan `attempt_count`; dua kegagalan dengan metode sama: ganti pendekatan/eskalasi.
- Status terpisah: `DECIDED`, `IMPLEMENTED`, `VERIFIED`, `BLOCKED`, `NOT_TESTED`.
- Eksekusi Codex default **satu worker pada satu waktu**, global lock saat claim, isolated worktree dan manifest SHA. CI/build boleh paralel jika kapasitas memungkinkan.

## 5. Roadmap implementasi — Development First
Tahapan adalah dependency dan kriteria penerimaan, **bukan janji tanggal**.

### Fase 1 — Control-plane foundation & repository scaffold (P0)
Implementasikan struktur `apps/web`, `apps/api`, `packages/core`, `integrations/telegram`, `integrations/hermes`, `docs`. Bangun Project Registry, logical agent profiles, message/thread API, persistence, basic session access, event outbox dan Task Ledger sederhana.
**Selesai jika:** owner dapat membuat/membaca percakapan dan task yang tetap ada setelah restart; pesan/project terisolasi; sintaks/build/smoke minimal PASS. Tidak menyentuh VPS aktif.

### Fase 2 — Web Chat usable MVP (P0)
Bangun responsif desktop/Android: sidebar proyek/agent, chat personal, group chat, @mention, message history, status event via SSE, job/activity preview. Tampilkan status worker **sebenarnya**, jangan simulasi sebagai LIVE.
**Selesai jika:** login Owner, buat thread, kirim/baca pesan dua arah, ganti proyek/agent, refresh tanpa kehilangan riwayat; endpoint/akses tak berizin ditolak.

### Fase 3 — Four-bot Telegram group + two-way sync (P0)
Buat empat identitas bot via BotFather oleh Owner (token masuk langsung secret store runtime), satu private group dengan Topics. Build Telegram gateway / webhook atau polling yang terisolasi, inbound allowlist, outbound outbox, topic mapping, web-sync, anti-loop.
**Selesai jika:** masing-masing bot tampil sebagai pengirim berbeda; pesan Owner di topic yang benar muncul di Web Chat, respons penting dari Web muncul di Telegram, tidak terjadi echo/duplikasi; pesan dari non-Owner tidak bisa memberi mandat. Tidak mengganggu bot Hermes existing.

### P0 — Hermes Multi-Model Engine (WF-MME-001)
Lihat [spesifikasi modul](HERMES_MULTI_MODEL_ENGINE.md). Audit read-only sebagai bagian WF-001; pilot routing terisolasi sebelum aktivasi Fase 4; acceptance fallback/resume dan zero incremental AI spend menjadi release gate Fase 5. Status PLANNED / NOT TESTED.

### Fase 4 — Director + Hermes worker orchestration (P0)
Integrasikan profil proyek, approval/mandate policy, job queue, shared Codex lock, Supervisor bridge dan existing CI/Playwright; mulailah dari adapter READ-ONLY. Baru aktifkan Developer→QA→limited self-fix→Draft PR dalam lane terisolasi yang disetujui; DevOps hanya staging target berizin.
**Selesai jika:** satu job idempotent dengan SHA & evidence berpindah agent secara otomatis, task resume setelah gangguan, penolakan tindakan di luar mandat, Draft PR tanpa merge. Ketersediaan Codex dan biaya API diverifikasi dahulu.

### Fase 5 — Pilot SANRO Studio + hardening (P0 / release gate)
Jalankan satu issue development non-production yang nyata: Owner instruction → Director plan → Codex edit → QA → (fix jika perlu) → Draft PR → ringkasan Web dan empat bot di Telegram. Audit reliability, sandbox, secrets, monitoring, resource caps setelah fitur alur utuh ada.
**Selesai jika:** end-to-end tanpa perintah terminal manual per tahap, test evidence tepat SHA, retry/deny terbukti, tidak ada perubahan production, laporan berisi repo/branch/SHA/PR; Owner memberi acceptance terpisah untuk rilis/merge.

**Ekspansi P1:** onboarding POS Public, Superadmin, Account & Billing, Android, STOCK; UI dashboard yang lebih kaya, UI/UX agent, knowledge search. Hanya setelah pilot end-to-end VERIFIED.

## 6. Ketentuan mandat dan approval
Approval Registry harus menyimpan `owner_actor`, `project_id`, `repo`, `branch/paths`, `environment`, `allowed_actions`, `forbidden_actions`, `risk/cost_budget`, `expires_at`, `evidence`.
- READ-ONLY default saat izin tidak jelas.
- DEVELOPMENT hanya di repo+worktree yang ada dalam mandat.
- STAGING write hanya target yang disetujui dan data sintetis.
- CRITICAL selalu memerlukan izin Owner spesifik: merge, production deploy, perubahan DB/keuangan nyata, hapus data, secrets/hak akses, billing/biaya, perluasan scope.
- Bot-to-bot/LLM messages tidak dapat meningkatkan izin; perubahan mandat hanya dari Owner terautentikasi.
- Token bot, session secret, private message, runtime evidence, kunci model disimpan di Hermes dengan izin file minimum, bukan repo public.
- Telemetry, retry, dan token/model quota wajib diberi batas; tanpa approval, tidak aktifkan provider berbiaya.

## 7. Urutan backlog pertama (maksimal lima tugas per putaran)
1. **WF-001** — GitHub & Supervisor/Hermes read-only capability reconciliation, hasil mapping reuse vs gap.
2. **WF-002** — Monorepo Node.js/React scaffold + foundational thread/identity/store API.
3. **WF-003** — Web Chat personal/group yang bekerja dengan mock agent berlabel DEMO.
4. **WF-004** — Telegram multi-bot adapter, project topics dan anti-loop (belum pakai token nyata pada public repo).
5. **WF-005** — Director task/event ledger + bridge READ-ONLY ke Hermes/Supervisor.

Urutan mengikuti dependency; setelah WF-002/WF-003 stabil, fokus pada fitur eksekusi Fase 4, bukan audit berulang.

## 8. Laporan, evidence, dan go/no-go
Setiap siklus development: (1) progres sebelum→sekarang + delta dan dasar; (2) tabel fase/status; (3) fitur IMPLEMENTED; (4) repo/branch/SHA/PR/evidence; (5) PASS/FAIL/NOT TESTED + cakupan; (6) blocker + maksimum lima next; (7) GO/NO-GO dan approval kritis.
Persentase hanya naik jika implementasi **terverifikasi**; perubahan dokumen ini tidak menambah progres software.
Untuk setiap fase, status awal adalah `DECIDED` / `NOT IMPLEMENTED`; tingkatkan berdasarkan bukti test dan runtime aktual.

## 9. Kondisi saat rencana dicatat
- Repo baru dibuat public oleh Owner; dokumentasi dasar sudah diinisialisasi.
- Existing Hermes tools dan kandidat Supervisor pernah didemonstrasikan, namun **runtime Hermes tidak diaudit langsung** pada pembuatan rencana ini.
- Empat Telegram bot baru, Telegram Group, Web App, unified messaging, Director baru, dan E2E autonomous **BELUM DIBUAT / BELUM TERVERIFIKASI**.
- Tidak ada pembelian, pembuatan bot/token, deploy, merge, atau perubahan production oleh dokumen ini.


## Development checkpoint — 2026-11-24

The following isolated engineering candidates are now present in this repository. Status labels distinguish source implementation from live activation; no runtime was activated.

| Capability | Status | Evidence |
|---|---|---|
| JD-03 fail-closed approval classifier | IMPLEMENTED / VERIFIED (synthetic characterization) | `integrations/hermes/approval-gate/`; 11 tests pass. Known keyword false positives remain; it is not a parser and has not replaced native approval. |
| JD-03 structured metadata inspection | IMPLEMENTED / VERIFIED (isolated synthetic plugin contract) | `integrations/hermes/structured-inspection/`; 18 tests pass across inspection and producer suites. Live identity/configuration remains NOT TESTED. |
| JD-04 serial engineering worker and native plugin shim | IMPLEMENTED / VERIFIED (isolated synthetic Hermes pilot) | Root worker modules and `.hermes/plugins/jd04_engineering_worker/`; current 27-test suite passes (imported-tree submission 0.001230 s; foreground status 0.013692 s). Live activation and authenticated Telegram conversation are NOT TESTED. |
| Conversation/job separation | IMPLEMENTED / VERIFIED (simulation) | Immediate submission and foreground status checks during synthetic job execution; no live Telegram concurrency test. |
| Free-only routing policy | IMPLEMENTED / VERIFIED (local policy tests only) | `model_routing.py` rejects paid/unknown cost and restricts tool eligibility. No router/provider was installed or called. |
| Web app/API, Telegram bots/group, Director orchestration, autonomous end-to-end | NOT IMPLEMENTED / NOT TESTED | No production or paid services were started. |

This checkpoint does not change the original approval, merge, deployment, production, or cost gates. Landlock constrains filesystem access but is not process, network, or complete credential isolation; live engineering activation remains BLOCKED.
