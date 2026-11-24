import {AGENTS} from './store.js';

const id=value=>typeof value==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$/.test(value)?value:null;
const sha=value=>typeof value==='string'&&/^[a-f0-9]{40}(?:[a-f0-9]{24})?$/.test(value)?value:null;
const known=(value,values,fallback='UNAVAILABLE')=>values.includes(value)?value:fallback;
const states=['ACTIVE','BLOCKED','REPORTED'];
const jobStates=['QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED','INTERRUPTED'];
const blockers=['MANDATE_EXPIRED_OR_REVOKED','SIDE_EFFECT_REVIEW_REQUIRED','SELF_FIX_LIMIT_REACHED','ENGINEERING_JOB_FAILED','CANDIDATE_CHANGED_DURING_QA','QA_EXIT_CODE_NOT_VERIFIED','EXECUTOR_UNAVAILABLE_OR_CANDIDATE_UNSAFE'];
const parse=value=>{try{const p=JSON.parse(value);return p&&typeof p==='object'&&!Array.isArray(p)?p:{};}catch{return {};}};
export function freshness(value,{now=Date.now(),maxAgeMs=60000}={}){
  const time=typeof value==='string'?Date.parse(value):NaN;
  if(!Number.isFinite(time)||time>now+5000)return {state:'UNAVAILABLE',observed_at:null,age_seconds:null};
  return {state:now-time<=maxAgeMs?'CURRENT':'STALE',observed_at:new Date(time).toISOString(),age_seconds:Math.max(0,Math.floor((now-time)/1000))};
}
const draftPr=(value,repository)=>{
  if(typeof value!=='string'||!repository)return null;
  try{const url=new URL(value);return url.protocol==='https:'&&url.hostname==='github.com'&&!url.username&&!url.password&&!url.search&&!url.hash&&url.pathname.startsWith(`/${repository}/pull/`)&&/^\d+$/.test(url.pathname.split('/').at(-1))?url.href:null;}catch{return null;}
};

// Pure SELECT projection: no worker adapter, status refresh, lifecycle call or
// audit write. All free text, filesystem paths, credentials and raw logs omitted.
export function monitoringSnapshot({db,project,providerCatalog,approvalRegistry={},now=Date.now(),maxAgeMs=60000}){
  const clock={now,maxAgeMs};
  const runs=db.prepare('SELECT id,task_id,state,stage,job_id,candidate_sha,test_status,blocker,updated_at FROM director_runs WHERE project_id=? ORDER BY created_at DESC LIMIT 100').all(project.id);
  const heartbeats=db.prepare('SELECT worker_id,role,status,run_id,job_id,observed_at FROM worker_heartbeats WHERE project_id=?').all(project.id);
  const jobs=db.prepare('SELECT job_id,checkpoint_json,created_at FROM worker_jobs WHERE project_id=? ORDER BY created_at DESC LIMIT 100').all(project.id);
  const totalQueue=db.prepare('SELECT checkpoint_json FROM worker_jobs WHERE project_id=?').all(project.id);
  const histories=db.prepare('SELECT event,entity_id,created_at FROM audit_events WHERE project_id=? ORDER BY created_at DESC LIMIT 30').all(project.id);
  const workers=AGENTS.map(agent=>{
    const heartbeat=heartbeats.find(h=>h.worker_id===agent.id&&h.role===agent.role),f=freshness(heartbeat?.observed_at,clock);
    return {worker_id:agent.id,role:agent.role,status:f.state==='CURRENT'?known(heartbeat?.status,['online','idle','working','blocked','offline'],'unknown'):'unknown',data_state:f.state,last_heartbeat:f.observed_at,age_seconds:f.age_seconds,project_id:project.id,run_id:id(heartbeat?.run_id),job_id:id(heartbeat?.job_id),profile_only:!heartbeat};
  });
  const runViews=runs.map(run=>{
    const f=freshness(run.updated_at,clock),testStatus=known(run.test_status,['PASS','FAIL','NOT_TESTED'],'NOT_TESTED'),commit=sha(run.candidate_sha);
    const checkpointRow=db.prepare('SELECT checkpoint FROM tasks WHERE id=? AND project_id=?').get(run.task_id,project.id),checkpoint=parse(checkpointRow?.checkpoint);
    const verified=run.state==='REPORTED'&&testStatus==='PASS'&&commit&&checkpoint.manifest_sha===commit&&checkpoint.run_id===run.id&&checkpoint.qa_job_id===run.job_id&&checkpoint.test_status==='PASS'&&checkpoint.evidence_status==='FIXED_PROFILE_EXECUTOR_AND_GIT_SNAPSHOT';
    return {run_id:id(run.id),task_id:id(run.task_id),state:known(run.state,states),stage:known(run.stage,['DEVELOPER','QA','SELF_FIX']),job_id:id(run.job_id),commit_sha:commit,test_status:testStatus,blocker:known(run.blocker,blockers,null),progress:{percent:verified?100:0,basis:verified?'ISOLATED_EXECUTOR_EVIDENCE':'NO_COMPLETED_VERIFIED_CHECKPOINT'},latest_checkpoint:verified?{commit_sha:commit,qa_job_id:id(checkpoint.qa_job_id),test_status:'PASS',evidence_status:checkpoint.evidence_status}:null,freshness:f};
  });
  const cleanJobs=jobs.map(job=>{const c=parse(job.checkpoint_json);return {job_id:id(job.job_id),status:known(c.status,jobStates),freshness:freshness(c.updated_at,clock),run_id:id(c.run_id)};});
  const queueCounts=totalQueue.reduce((counts,job)=>{const c=parse(job.checkpoint_json);if(c.status==='QUEUED')counts.queued++;if(c.status==='RUNNING')counts.running++;return counts;},{queued:0,running:0});
  const reports=db.prepare('SELECT COUNT(*) AS queued, SUM(CASE WHEN delivered_at IS NOT NULL THEN 1 ELSE 0 END) AS acknowledged FROM report_outbox WHERE project_id=?').get(project.id);
  return {schema_version:1,project_id:project.id,generated_at:new Date(now).toISOString(),read_only:true,workers,runs:runViews,jobs:cleanJobs,queue:{...queueCounts,source:'PERSISTED_CHECKPOINTS',freshness:'PER_JOB',history_limit:100},models:(providerCatalog.providers??[]).map(p=>({provider_id:known(p.id,['9router','freellmapi']),availability:p.enabled===true?'UNAVAILABLE':'DISABLED',quota_status:'UNAVAILABLE',data_state:'UNAVAILABLE'})),approval:{pending_count:Object.values(approvalRegistry).filter(v=>v?.project_id===project.id&&v.status==='PENDING').length,source:'PRIVATE_REGISTRY_SNAPSHOT',live_native_status:'UNAVAILABLE'},reports:{queued:Number(reports.queued),acknowledged:Number(reports.acknowledged??0),transport:'EXISTING_HERMES_TRANSPORT',live_delivery:'NOT_TESTED'},draft_pr:draftPr(project.draft_pr,project.repository),hermes_health:{status:'UNAVAILABLE',data_state:'UNAVAILABLE',reason:'NO_AUTHORIZED_LIVE_HEALTH_SOURCE'},history:histories.filter(h=>/^(DIRECTOR_|WORKFLOW_|TASK_CREATED$|ENGINEERING_JOB_)/.test(h.event)&&/^[A-Z_]+$/.test(h.event)).map(h=>({event:h.event,entity_id:id(h.entity_id),freshness:freshness(h.created_at,clock)}))};
}
