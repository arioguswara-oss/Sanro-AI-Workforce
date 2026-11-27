import React from 'react';

// Presentation-only: host supplies the sanitized monitoring DTO. No token,
// fetch, lifecycle controls, terminal, forms or approval mutation callbacks.
export function WorkforceMonitor({snapshot}){
  if(!snapshot||snapshot.schema_version!==1||snapshot.read_only!==true)return <section aria-label="Workforce monitoring"><p>Data workforce belum tersedia.</p></section>;
  return <section aria-label="Workforce monitoring">
    <h2>Virtual Office · {snapshot.project_id}</h2>
    <p>Hermes: {snapshot.hermes_health.status} · Antrean tercatat: {snapshot.queue.queued} · Berjalan tercatat: {snapshot.queue.running}</p>
    <table><caption>Status worker berdasarkan pengamatan terakhir</caption><thead><tr><th>Peran</th><th>Status</th><th>Kesegaran</th><th>Job</th><th>Heartbeat</th></tr></thead><tbody>{snapshot.workers.map(w=><tr key={w.worker_id}><td>{w.role}</td><td>{w.status}</td><td>{w.data_state}</td><td>{w.job_id??'—'}</td><td>{w.last_heartbeat??'Belum tersedia'}</td></tr>)}</tbody></table>
    <table><caption>Task dan bukti</caption><thead><tr><th>Run</th><th>Tahap</th><th>Status</th><th>Progres terbukti</th><th>Commit</th><th>Tes</th><th>Blocker</th></tr></thead><tbody>{snapshot.runs.map(r=><tr key={r.run_id}><td>{r.run_id}</td><td>{r.stage}</td><td>{r.state} · {r.freshness.state}</td><td>{r.progress.percent}%</td><td><code>{r.commit_sha??'—'}</code></td><td>{r.test_status}</td><td>{r.blocker??'—'}</td></tr>)}</tbody></table>
    <p>Approval pending tercatat: {snapshot.approval.pending_count} · Status native: {snapshot.approval.live_native_status}</p>
    <p>Laporan diantrekan: {snapshot.reports.queued} · Diterima transport: {snapshot.reports.acknowledged}</p>
    <ul>{snapshot.models.map(m=><li key={m.provider_id}>{m.provider_id}: {m.availability} · Kuota: {m.quota_status}</li>)}</ul>
    {snapshot.draft_pr&&<a href={snapshot.draft_pr} target="_blank" rel="noopener noreferrer">Draft PR kandidat</a>}
  </section>;
}
