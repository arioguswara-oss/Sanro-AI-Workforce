import {randomUUID,createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';

const exec=promisify(execFile);
const iso=()=>new Date().toISOString();
const shaPattern=/^[a-f0-9]{40}(?:[a-f0-9]{24})?$/;
const stageRoles={DEVELOPER:'developer',QA:'qa',SELF_FIX:'developer'};
const hash=value=>createHash('sha256').update(value).digest('hex');
export async function gitSnapshot(workspace,project){
  const options={timeout:5000,maxBuffer:65536,env:{PATH:'/usr/bin:/bin',LANG:'C.UTF-8',GIT_CONFIG_NOSYSTEM:'1'}};
  if(project){
    const branch=(await exec('git',['-C',workspace,'branch','--show-current'],options)).stdout.trim();
    const remote=(await exec('git',['-C',workspace,'config','--get','remote.origin.url'],options)).stdout.trim().replace(/\.git$/, '');
    if(branch!==project.branch||![`https://github.com/${project.repository}`,`git@github.com:${project.repository}`].includes(remote))throw new Error('repository or branch does not match mandate');
  }
  const sha=(await exec('git',['-C',workspace,'rev-parse','HEAD'],options)).stdout.trim();
  const dirty=(await exec('git',['-C',workspace,'status','--porcelain','--untracked-files=all'],options)).stdout.trim();
  if(!shaPattern.test(sha)||dirty)throw new Error('candidate must be committed and worktree clean');
  return sha;
}

// Deterministic Director: one scoped task, fixed profiles, one self-fix. No LLM is
// trusted to grant authority or execute tools; the existing worker remains FIFO.
export class Director {
  constructor({db,auth,workerCall,authorize,snapshot=gitSnapshot}){
    Object.assign(this,{db,auth,workerCall,authorize,snapshot});this.busy=false;this.timer=null;
    db.exec(`CREATE TABLE IF NOT EXISTS director_runs (
      id TEXT PRIMARY KEY, project_id TEXT NOT NULL, owner TEXT NOT NULL, task_id TEXT NOT NULL,
      approval_ref TEXT NOT NULL, idempotency_key TEXT NOT NULL, fingerprint TEXT NOT NULL,
      state TEXT NOT NULL, stage TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 0,
      job_id TEXT, candidate_sha TEXT, test_status TEXT NOT NULL DEFAULT 'NOT_TESTED',
      blocker TEXT, instruction_json TEXT, recovery_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(project_id,owner,idempotency_key));
      CREATE TABLE IF NOT EXISTS report_outbox (
      id TEXT PRIMARY KEY, project_id TEXT NOT NULL, owner TEXT NOT NULL, run_id TEXT NOT NULL, delivery_key TEXT UNIQUE NOT NULL,
      payload TEXT NOT NULL, created_at TEXT NOT NULL, delivered_at TEXT);
      CREATE TABLE IF NOT EXISTS worker_heartbeats (
      worker_id TEXT NOT NULL, project_id TEXT NOT NULL, role TEXT NOT NULL, status TEXT NOT NULL,
      run_id TEXT, job_id TEXT, observed_at TEXT NOT NULL, PRIMARY KEY(worker_id,project_id));`);
    const runColumns=new Set(db.prepare('PRAGMA table_info(director_runs)').all().map(row=>row.name));
    if(!runColumns.has('instruction_json'))db.exec('ALTER TABLE director_runs ADD COLUMN instruction_json TEXT');
  }
  active(principal,project,approval){
    const registered=this.auth.projects.get(project.id);
    if(!registered||registered.workspace!==project.workspace||(this.auth.workspaceRegistry&&this.auth.workspaceRegistry.get(registered.workspace)!==project.id))return false;
    const grants=principal?.projects?.[project.id];
    const scopes=['read','workflow:run','workflow:director','workflow:developer','workflow:qa','engineering:execute','engineering:read'];
    if(!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(project.repository??'')||!project.branch||['main','master'].includes(project.branch)||project.environment!=='isolated-development')return false;
    const mandate=this.authorize(principal,project.id,approval);
    if(!mandate||!Array.isArray(mandate.allowed_actions)||!Array.isArray(mandate.forbidden_actions)||mandate.repository!==project.repository||mandate.branch!==project.branch||mandate.environment!==project.environment||mandate.owner_actor!==principal.subject||mandate.max_cost_usd!==0||!['engineering:execute','qa:execute'].every(action=>mandate.allowed_actions?.includes(action))||!['merge','production:deploy','paid-api','other-repository:write'].every(action=>mandate.forbidden_actions?.includes(action)))return false;
    if(!grants||grants.workspace!==project.workspace||!scopes.every(s=>grants.scopes.includes(s)))return false;
    const p=project.pipeline;
    return p&&['developer','qa','self_fix'].every(stage=>{
      const profile=this.auth.profiles[p[stage]];
      return profile?.projects?.includes(project.id)&&profile.role===(stage==='qa'?'qa':'developer')&&profile.executor===(stage==='qa'?'local-ci':'codex');
    });
  }
  submit(principal,project,{task_id,approval_ref,idempotency_key}){
    if(!this.active(principal,project,approval_ref))throw Object.assign(new Error('active scoped pipeline mandate required'),{status:403});
    if(typeof idempotency_key!=='string'||idempotency_key.length<8||idempotency_key.length>160)throw Object.assign(new Error('bounded idempotency key required'),{status:400});
    const task=this.db.prepare('SELECT * FROM tasks WHERE id=? AND project_id=? AND owner=?').get(task_id,project.id,principal.subject);
    if(!task)throw Object.assign(new Error('task not found'),{status:404});
    const fingerprint=hash(JSON.stringify([task_id,approval_ref,task.title,task.description,project.pipeline]));
    const prior=this.db.prepare('SELECT * FROM director_runs WHERE project_id=? AND owner=? AND idempotency_key=?').get(project.id,principal.subject,idempotency_key);
    if(prior){if(prior.fingerprint!==fingerprint)throw Object.assign(new Error('idempotency content conflict'),{status:409});return prior;}
    if(task.state!=='CREATED')throw Object.assign(new Error('task already assigned'),{status:409});
    const id=randomUUID(),now=iso();
    this.db.exec('BEGIN IMMEDIATE');try{
      this.db.prepare(`INSERT INTO director_runs(id,project_id,owner,task_id,approval_ref,idempotency_key,fingerprint,state,stage,created_at,updated_at) VALUES(?,?,?,?,?,?,?,'ACTIVE','DEVELOPER',?,?)`).run(id,project.id,principal.subject,task_id,approval_ref,idempotency_key,fingerprint,now,now);
      this.db.prepare("UPDATE tasks SET state='DIRECTOR_REVIEW',assigned_role='director',updated_at=? WHERE id=?").run(now,task_id);
      this.audit(project.id,principal.subject,'DIRECTOR_PLANNED',id);this.db.exec('COMMIT');
    }catch(e){this.db.exec('ROLLBACK');throw e;}
    return this.get(id);
  }
  async resume(principal,project,id,{side_effects_reconciled,recovery_note,approval_ref}){
    const run=this.get(id),grants=principal?.projects?.[project.id];
    if(!run||run.project_id!==project.id||run.owner!==principal.subject)throw Object.assign(new Error('run not found'),{status:404});
    if(!this.active(principal,project,approval_ref)||!grants.scopes.includes('engineering:recover')||!this.authorize(principal,project.id,approval_ref,'engineering:recover'))throw Object.assign(new Error('recovery mandate required'),{status:403});
    if(run.state!=='BLOCKED'||run.blocker!=='SIDE_EFFECT_REVIEW_REQUIRED'||run.recovery_count>=2||side_effects_reconciled!==true||typeof recovery_note!=='string'||recovery_note.length<8||recovery_note.length>1000)throw Object.assign(new Error('bounded explicit side-effect review required'),{status:409});
    const prior=await this.workerCall(principal,project,{action:'status',job_id:run.job_id});
    if(!['INTERRUPTED','CANCELLED'].includes(prior.status))throw Object.assign(new Error('prior worker is not safely terminal'),{status:409});
    this.db.exec('BEGIN IMMEDIATE');try{
      this.db.prepare('UPDATE director_runs SET approval_ref=?,instruction_json=NULL,recovery_count=recovery_count+1 WHERE id=?').run(approval_ref,id);
      this.audit(project.id,principal.subject,`SIDE_EFFECT_REVIEW_${hash(recovery_note)}`,id);
      const next=this.change(this.get(id),{state:'ACTIVE',job_id:null,blocker:null});this.db.exec('COMMIT');return next;
    }catch(e){this.db.exec('ROLLBACK');throw e;}
  }
  get(id){return this.db.prepare('SELECT * FROM director_runs WHERE id=?').get(id);}
  audit(project,actor,event,entity){this.db.prepare('INSERT INTO audit_events VALUES(?,?,?,?,?,?)').run(randomUUID(),project,actor,event,entity,iso());}
  change(run,updates){
    const next={...run,...updates,updated_at:iso()};
    if(next.stage!==run.stage)this.db.prepare('UPDATE director_runs SET instruction_json=NULL WHERE id=?').run(run.id);
    this.db.prepare('UPDATE director_runs SET state=?,stage=?,attempt=?,job_id=?,candidate_sha=?,test_status=?,blocker=?,updated_at=? WHERE id=?').run(next.state,next.stage,next.attempt,next.job_id,next.candidate_sha,next.test_status,next.blocker,next.updated_at,next.id);
    const taskState=next.state==='REPORTED'?'REPORTED':next.state==='BLOCKED'?'BLOCKED':next.stage==='QA'?'QA_PENDING':next.stage==='SELF_FIX'?'DEVELOPER_SELF_FIX':'DEVELOPER_ACTIVE';
    this.db.prepare('UPDATE tasks SET state=?,assigned_role=?,updated_at=? WHERE id=?').run(taskState,stageRoles[next.stage]??'director',next.updated_at,next.task_id);
    this.audit(next.project_id,next.owner,`DIRECTOR_${next.state}_${next.stage}`,next.id);
    return next;
  }
  heartbeat(run,status){this.db.prepare(`INSERT INTO worker_heartbeats VALUES(?,?,?,?,?,?,?) ON CONFLICT(worker_id,project_id) DO UPDATE SET status=excluded.status,run_id=excluded.run_id,job_id=excluded.job_id,observed_at=excluded.observed_at`).run(stageRoles[run.stage]??'director',run.project_id,stageRoles[run.stage]??'director',status,run.id,run.job_id,iso());}
  block(run,reason){
    this.db.exec('BEGIN IMMEDIATE');try{
      const next=this.change(run,{state:'BLOCKED',blocker:reason});this.heartbeat(next,'blocked');
      const delivery_key=`blocker:${run.id}:${run.recovery_count}`;
      const payload={version:1,event:'BLOCKER',project_id:run.project_id,run_id:run.id,task_id:run.task_id,job_id:run.job_id,blocker:reason,delivery_key,approval_required:reason==='MANDATE_EXPIRED_OR_REVOKED'||reason==='SIDE_EFFECT_REVIEW_REQUIRED'};
      this.db.prepare('INSERT OR IGNORE INTO report_outbox VALUES(?,?,?,?,?,?,?,NULL)').run(randomUUID(),run.project_id,run.owner,run.id,delivery_key,JSON.stringify(payload),iso());
      this.db.exec('COMMIT');return next;
    }catch(e){this.db.exec('ROLLBACK');throw e;}
  }
  async tick(){
    if(this.busy)return false;this.busy=true;
    try{
      // One stage per tick; underlying executor holds the global FIFO lock.
      const runs=this.db.prepare("SELECT * FROM director_runs WHERE state='ACTIVE' ORDER BY created_at,rowid").all();
      for(const run of runs){
        const principal=[...this.auth.principals.values()].find(p=>p.subject===run.owner),project=this.auth.projects.get(run.project_id);
        if(!project||!this.active(principal,project,run.approval_ref)){this.block(run,'MANDATE_EXPIRED_OR_REVOKED');continue;}
        try{await this.step(run,principal,project);}catch{this.block(this.get(run.id),'EXECUTOR_UNAVAILABLE_OR_CANDIDATE_UNSAFE');}
      }
      return true;
    }finally{this.busy=false;}
  }
  async step(run,principal,project){
    const task=this.db.prepare('SELECT * FROM tasks WHERE id=?').get(run.task_id);
    if(!run.job_id){
      const profile=project.pipeline[run.stage==='SELF_FIX'?'self_fix':run.stage.toLowerCase()];
      let instruction=run.instruction_json;
      if(!instruction){
        const baseline_sha=await this.snapshot(project.workspace,project);
        if(run.stage==='QA'&&baseline_sha!==run.candidate_sha){this.block(run,'CANDIDATE_CHANGED_DURING_QA');return;}
        // Persist exact input BEFORE enqueue so a restart reuses identical argv.
        instruction=JSON.stringify({version:1,run_id:run.id,project_id:project.id,task_id:task.id,title:task.title,instruction:task.description,stage:run.stage,attempt:run.attempt,baseline_sha,candidate_sha:run.candidate_sha,boundaries:['NO_MERGE','NO_PRODUCTION','NO_PAID_API','NO_OTHER_REPOSITORY'],executor:run.stage==='QA'?'local-ci':'codex'});
        this.db.prepare('UPDATE director_runs SET instruction_json=? WHERE id=?').run(instruction,run.id);
      }
      const result=await this.workerCall(principal,project,{action:'submit',profile,approval_ref:run.approval_ref,idempotency_key:`director:${run.id}:${run.stage}:${run.attempt}:${run.recovery_count}`,instruction});
      if(typeof result.job_id!=='string'||!/^([a-f0-9]{32}|[a-f0-9-]{36})$/.test(result.job_id))throw new Error('invalid job response');
      this.db.exec('BEGIN IMMEDIATE');try{
        const next=this.change(run,{job_id:result.job_id});
        this.db.prepare('INSERT OR IGNORE INTO worker_jobs(job_id,project_id,owner,profile,created_at,checkpoint_json) VALUES(?,?,?,?,?,?)').run(result.job_id,project.id,principal.subject,profile,iso(),JSON.stringify({status:'QUEUED',run_id:run.id,updated_at:iso(),admission:result.admission}));
        this.heartbeat(next,'working');this.db.exec('COMMIT');
      }catch(e){this.db.exec('ROLLBACK');throw e;}
      return;
    }
    const result=await this.workerCall(principal,project,{action:'status',job_id:run.job_id});
    if(!['QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED','INTERRUPTED'].includes(result.status))throw new Error('invalid worker state');
    let priorCheckpoint={};try{priorCheckpoint=JSON.parse(this.db.prepare('SELECT checkpoint_json FROM worker_jobs WHERE job_id=?').get(run.job_id)?.checkpoint_json??'{}');}catch{}
    this.db.prepare('UPDATE worker_jobs SET checkpoint_json=? WHERE job_id=?').run(JSON.stringify({...priorCheckpoint,status:result.status,run_id:run.id,updated_at:iso(),exit_code:result.exit_code??null,...(result.admission?{admission:result.admission}:{})}),run.job_id);
    this.heartbeat(run,result.status==='QUEUED'?'idle':'working');
    if(['QUEUED','RUNNING'].includes(result.status))return;
    if(['INTERRUPTED','CANCELLED'].includes(result.status)){this.block(run,'SIDE_EFFECT_REVIEW_REQUIRED');return;}
    if(run.stage==='QA'){
      const currentSha=await this.snapshot(project.workspace,project);
      if(currentSha!==run.candidate_sha){this.block(run,'CANDIDATE_CHANGED_DURING_QA');return;}
      if(result.status==='FAILED'){
        if(run.attempt>=1){this.block(this.change(run,{test_status:'FAIL'}),'SELF_FIX_LIMIT_REACHED');return;}
        this.change(run,{stage:'SELF_FIX',attempt:run.attempt+1,job_id:null,test_status:'FAIL'});return;
      }
      if(result.exit_code!==0){this.block(run,'QA_EXIT_CODE_NOT_VERIFIED');return;}
      const checkpoint={manifest_sha:currentSha,test_status:'PASS',run_id:run.id,qa_job_id:run.job_id,evidence_status:'FIXED_PROFILE_EXECUTOR_AND_GIT_SNAPSHOT',checkpointed_at:iso()};
      this.db.exec('BEGIN IMMEDIATE');try{
        this.audit(project.id,run.owner,'RELEASE_CANDIDATE_READY',run.id);
        this.db.prepare('UPDATE tasks SET checkpoint=? WHERE id=?').run(JSON.stringify(checkpoint),task.id);
        this.audit(project.id,run.owner,'DURABLE_CHECKPOINT_SAVED',run.id);
        const payload={version:1,event:'RELEASE_CANDIDATE',project_id:project.id,run_id:run.id,task_id:task.id,commit_sha:currentSha,test_status:'PASS',delivery_key:`report:${run.id}`,draft_pr_status:'NOT_CREATED_BY_DIRECTOR',message:'Candidate ready for review; no merge or deployment.'};
        this.db.prepare('INSERT OR IGNORE INTO report_outbox VALUES(?,?,?,?,?,?,?,NULL)').run(randomUUID(),project.id,run.owner,run.id,payload.delivery_key,JSON.stringify(payload),iso());
        const next=this.change(run,{state:'REPORTED',test_status:'PASS',blocker:null});this.heartbeat(next,'idle');
        this.db.exec('COMMIT');
      }catch(e){this.db.exec('ROLLBACK');throw e;}
      return;
    }
    if(result.status!=='COMPLETED'||result.exit_code!==0){this.block(run,'ENGINEERING_JOB_FAILED');return;}
    const candidate_sha=await this.snapshot(project.workspace,project);
    this.change(run,{stage:'QA',job_id:null,candidate_sha,test_status:'NOT_TESTED'});
  }
  start(intervalMs=250){if(this.timer)return;this.timer=setInterval(()=>{void this.tick().catch(()=>{});},Math.max(100,intervalMs));this.timer.unref();}
  stop(){clearInterval(this.timer);this.timer=null;}
  async deliverReports(transport){
    // Inject ONLY the existing authenticated Hermes/Telegram transport. It must
    // deduplicate delivery_key; a crash after send can cause at-least-once retry.
    if(typeof transport?.send!=='function')throw new Error('existing report transport required');
    for(const row of this.db.prepare('SELECT * FROM report_outbox WHERE delivered_at IS NULL ORDER BY created_at').all()){
      const result=await transport.send(JSON.parse(row.payload));
      if(result?.acknowledged===true)this.db.prepare('UPDATE report_outbox SET delivered_at=? WHERE id=? AND delivered_at IS NULL').run(iso(),row.id);
    }
  }
}
