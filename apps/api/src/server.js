import http from 'node:http';
import {randomUUID,createHash} from 'node:crypto';
import {mkdirSync,lstatSync,chmodSync,readFileSync} from 'node:fs';
import {join,resolve} from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {loadAuth,authenticate,projectAccess} from './auth.js';
import {Store,AGENTS} from './store.js';
import {WorkerController} from './worker-controller.js';

const root=resolve(fileURLToPath(new URL('../../../',import.meta.url)));
const date=()=>new Date().toISOString();
const safeId=/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$/;
const roles={DIRECTOR_REVIEW:'director',DEVELOPER_ACTIVE:'developer',QA_PENDING:'qa',QA_FAILED:'qa',DEVELOPER_SELF_FIX:'developer',QA_PASSED:'qa',RELEASE_CANDIDATE:'director'};
const transitions={
  CREATED:{assign_director:{next:'DIRECTOR_REVIEW',scope:'workflow:director'}},
  DIRECTOR_REVIEW:{assign_developer:{next:'DEVELOPER_ACTIVE',scope:'workflow:director'}},
  DEVELOPER_ACTIVE:{submit_qa:{next:'QA_PENDING',scope:'workflow:developer'}},
  QA_PENDING:{qa_fail:{next:'QA_FAILED',scope:'workflow:qa'},qa_pass:{next:'QA_PASSED',scope:'workflow:qa'}},
  QA_FAILED:{bounded_self_fix:{next:'DEVELOPER_SELF_FIX',scope:'workflow:developer'}},
  DEVELOPER_SELF_FIX:{resubmit_qa:{next:'QA_PENDING',scope:'workflow:developer'}},
  QA_PASSED:{prepare_release_candidate:{next:'RELEASE_CANDIDATE',scope:'workflow:director'}},
  RELEASE_CANDIDATE:{save_checkpoint:{next:'CHECKPOINTED',scope:'workflow:director'}},
  CHECKPOINTED:{report_owner:{next:'REPORTED',scope:'workflow:director'}},
};
const capabilities=JSON.parse(readFileSync(join(root,'capability_registry.json'),'utf8')).capabilities;

function readBody(req,max=64*1024){return new Promise((resolve,reject)=>{let data='';req.on('data',chunk=>{data+=chunk;if(data.length>max){reject(Object.assign(new Error('request too large'),{status:413}));req.destroy();}});req.on('end',()=>{try{resolve(data?JSON.parse(data):{});}catch{reject(Object.assign(new Error('invalid JSON'),{status:400}));}});req.on('error',reject);});}
function reply(res,status,data){res.writeHead(status,{'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff','referrer-policy':'no-referrer'});res.end(JSON.stringify(data));}
function approvalStatus(auth,principal,projectId,ref,scope='engineering:execute'){
  if(!ref||!principal.projects?.[projectId]?.approval_refs?.includes(ref))return null;
  const record=auth.approvals[ref];if(!record||record.project_id!==projectId||record.subject!==principal.subject||record.status!=='APPROVED'||!Array.isArray(record.scopes)||!record.scopes.includes(scope))return null;
  if(!record.expires_at||!Number.isFinite(Date.parse(record.expires_at))||Date.parse(record.expires_at)<=Date.now())return null;
  return {id:ref,project_id:projectId,scope,status:'APPROVED',scopes:record.scopes.slice(),expires_at:record.expires_at};
}
function privateDirectory(path){mkdirSync(path,{recursive:true,mode:0o700});const s=lstatSync(path);if(s.isSymbolicLink()||!s.isDirectory()||s.uid!==process.getuid())throw new Error('state directory must be real and owned by current user');if((s.mode&0o077)!==0)throw new Error('state directory permissions must be 0700');}
async function workerCall(stateDir,auth,principal,project,request){
  const payload={...request,principal,project:{id:project.id,workspace:project.workspace},projects:Object.fromEntries([...auth.projects].map(([k,v])=>[k,{workspace:v.workspace}])),profiles:auth.profiles};
  const env={PATH:'/usr/bin:/bin',HOME:stateDir,TMPDIR:join(stateDir,'tmp'),LANG:'C.UTF-8',PYTHONNOUSERSITE:'1',WORKFORCE_WORKER_STATE:stateDir};
  return await new Promise((resolve,reject)=>{
    const child=spawn(process.env.PYTHON??'python3',[join(root,'workforce_worker_bridge.py')],{cwd:root,env,stdio:['pipe','pipe','ignore'],shell:false});
    let stdout='',settled=false;child.stdout.setEncoding('utf8');const timer=setTimeout(()=>{settled=true;child.kill('SIGKILL');reject(Object.assign(new Error('worker adapter deadline exceeded'),{status:503}));},8000);
    child.stdout.on('data',x=>{stdout+=x;if(stdout.length>128*1024)child.kill('SIGKILL');});
    child.on('error',()=>{if(settled)return;settled=true;clearTimeout(timer);reject(Object.assign(new Error('worker adapter unavailable'),{status:503}));});
    child.on('close',code=>{if(settled)return;settled=true;clearTimeout(timer);let result;try{result=JSON.parse(stdout);}catch{reject(Object.assign(new Error('worker adapter failed'),{status:503}));return;}
      if(code!==0){const denied=result.error==='PermissionError';reject(Object.assign(new Error(denied?'operation is not authorized':'worker adapter request failed'),{status:denied?403:400}));return;}resolve(result);});
    child.stdin.on('error',()=>{});child.stdin.end(JSON.stringify(payload));
  });
}

export function createApp({authPath=process.env.WORKFORCE_AUTH_FILE,stateDir=process.env.WORKFORCE_STATE_DIR,startWorker=process.env.WORKFORCE_WORKER_AUTOSTART==='1',allowWorkerControl=process.env.WORKFORCE_ALLOW_WORKER_CONTROL==='1'}={}){
  const auth=loadAuth(authPath);
  if(!stateDir)throw new Error('WORKFORCE_STATE_DIR is required');
  stateDir=resolve(stateDir);privateDirectory(stateDir);privateDirectory(join(stateDir,'tmp'));
  const dbPath=join(stateDir,'workforce.sqlite3');
  try{const s=lstatSync(dbPath);if(s.isSymbolicLink()||!s.isFile()||s.uid!==process.getuid()||(s.mode&0o077)!==0)throw new Error('unsafe database file');}catch(e){if(e.code!=='ENOENT')throw e;}
  process.umask(0o077);const store=new Store(dbPath);chmodSync(dbPath,0o600);store.seedProjects([...auth.projects.values()]);
  const db=store.db;
  const workerController=new WorkerController(stateDir);if(startWorker)workerController.start();
  async function handler(req,res){
    try{
      const url=new URL(req.url,'http://localhost');const path=url.pathname;
      if(req.method==='GET'&&path==='/api/health')return reply(res,200,{status:'READY',execution:'isolated-adapter-disabled-unless-authorized'});
      const principal=authenticate(auth,req.headers.authorization);if(!principal)return reply(res,401,{error:'authentication required'});
      if(req.method==='GET'&&path==='/api/agents')return reply(res,200,{agents:AGENTS});
      if(req.method==='GET'&&path==='/api/capabilities')return reply(res,200,{capabilities});
      let m;
      m=path.match(/^\/api\/projects\/([^/]+)\/worker$/);
      if(m){const projectId=m[1],access=projectAccess(auth,principal,projectId,'read');if(!access)return reply(res,404,{error:'not found'});
        if(req.method==='GET'&&access.grants.scopes.includes('worker:read'))return reply(res,200,{status:workerController.status()});
        if(req.method==='POST'&&access.grants.scopes.includes('worker:manage')){if(!allowWorkerControl)return reply(res,403,{error:'local worker control is disabled'});const b=await readBody(req);if(b.action==='start')return reply(res,200,{started:workerController.start(),status:workerController.status()});if(b.action==='stop')return reply(res,200,{stopped:await workerController.shutdown(),status:workerController.status()});return reply(res,400,{error:'action must be start or stop'});}
        return reply(res,403,{error:'worker management scope required'});
      }
      if(req.method==='GET'&&path==='/api/projects'){
        const projects=[...auth.projects.values()].filter(p=>projectAccess(auth,principal,p.id,'read')).map(({id,name})=>({id,name}));return reply(res,200,{projects});
      }
      m=path.match(/^\/api\/projects\/([^/]+)\/(threads|tasks|approvals|jobs|activity|command-profiles)$/);
      if(m){const [,projectId,resource]=m;if(!safeId.test(projectId))return reply(res,404,{error:'not found'});const access=projectAccess(auth,principal,projectId,'read');if(!access)return reply(res,404,{error:'not found'});const project=access.project;
        if(resource==='threads'&&req.method==='GET'){
          const rows=db.prepare('SELECT id,kind,agent_id,title,created_at FROM threads WHERE project_id=? AND owner=? ORDER BY created_at').all(projectId,principal.subject);return reply(res,200,{threads:rows});
        }
        if(resource==='threads'&&req.method==='POST'){
          if(!access.grants.scopes.includes('thread:write'))return reply(res,403,{error:'thread write scope required'});const b=await readBody(req);if(!['personal','group'].includes(b.kind)||!AGENTS.some(a=>a.id===b.agent_id)||typeof b.title!=='string'||!b.title.trim()||b.title.length>160)return reply(res,400,{error:'invalid thread'});
          const id=randomUUID(),created=date();db.prepare('INSERT INTO threads VALUES(?,?,?,?,?,?,?)').run(id,projectId,principal.subject,b.kind,b.agent_id,b.title.trim(),created);audit(projectId,principal.subject,'THREAD_CREATED',id);return reply(res,201,{id,project_id:projectId,kind:b.kind,agent_id:b.agent_id,title:b.title.trim(),created_at:created});
        }
        if(resource==='tasks'&&req.method==='GET'){
          const rows=db.prepare('SELECT id,title,description,state,assigned_role,checkpoint,created_at,updated_at FROM tasks WHERE project_id=? AND owner=? ORDER BY created_at').all(projectId,principal.subject);return reply(res,200,{tasks:rows});
        }
        if(resource==='tasks'&&req.method==='POST'){
          if(!access.grants.scopes.includes('task:create'))return reply(res,403,{error:'task:create scope required'});const b=await readBody(req);if(typeof b.title!=='string'||!b.title.trim()||b.title.length>200||typeof (b.description??'')!=='string'||(b.description??'').length>12000)return reply(res,400,{error:'invalid task'});
          const id=randomUUID(),now=date();db.prepare('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)').run(id,projectId,principal.subject,b.title.trim(),b.description??'','CREATED','owner',null,now,now);audit(projectId,principal.subject,'TASK_CREATED',id);return reply(res,201,{id,project_id:projectId,state:'CREATED',created_at:now});
        }
        if(resource==='approvals'&&req.method==='GET'){
          const approvals=(access.grants.approval_refs??[]).map(ref=>approvalStatus(auth,principal,projectId,ref)).filter(Boolean);return reply(res,200,{approvals});
        }
        if(resource==='activity'&&req.method==='GET'){
          const rows=db.prepare('SELECT id,actor_id,event,entity_id,created_at FROM audit_events WHERE project_id=? ORDER BY created_at DESC LIMIT 100').all(projectId);return reply(res,200,{events:rows});
        }
        if(resource==='command-profiles'&&req.method==='GET'){
          if(!access.grants.scopes.includes('engineering:execute'))return reply(res,200,{profiles:[]});const profiles=Object.entries(auth.profiles).filter(([,profile])=>profile.projects?.includes(projectId)).map(([id])=>({id,approval_required:true}));return reply(res,200,{profiles});
        }
        if(resource==='jobs'&&req.method==='GET'){
          if(!access.grants.scopes.includes('engineering:read'))return reply(res,403,{error:'engineering:read scope required'});const owned=db.prepare('SELECT * FROM worker_jobs WHERE project_id=? AND owner=? ORDER BY created_at').all(projectId,principal.subject);const jobs=[];for(const j of owned){try{const status=await workerCall(stateDir,auth,principal,project,{action:'status',job_id:j.job_id});persistCheckpoint(j,status);jobs.push({...status,profile:j.profile,created_at:j.created_at,parent_job_id:j.parent_job_id});}catch(e){return reply(res,e.status??503,{error:'worker adapter unavailable'});}}return reply(res,200,{jobs});
        }
        if(resource==='jobs'&&req.method==='POST'){
          if(!access.grants.scopes.includes('engineering:execute'))return reply(res,403,{error:'engineering:execute scope required'});const b=await readBody(req);if(typeof b.profile!=='string'||typeof b.idempotency_key!=='string'||b.idempotency_key.length<8||b.idempotency_key.length>200)return reply(res,400,{error:'profile and bounded idempotency_key required'});
          const profile=auth.profiles[b.profile];if(!profile||!Array.isArray(profile.projects)||!profile.projects.includes(projectId))return reply(res,403,{error:'command profile is not permitted for this project'});
          const approval=b.approval_ref;if(!approvalStatus(auth,principal,projectId,approval))return reply(res,403,{error:'valid, unexpired project approval required'});
          const result=await workerCall(stateDir,auth,principal,project,{action:'submit',profile:b.profile,approval_ref:approval,idempotency_key:b.idempotency_key,timeout:b.timeout});const created=date();db.prepare('INSERT OR IGNORE INTO worker_jobs(job_id,project_id,owner,profile,created_at,checkpoint_json) VALUES(?,?,?,?,?,?)').run(result.job_id,projectId,principal.subject,b.profile,created,JSON.stringify({status:'QUEUED',updated_at:created,project_id:projectId,owner:principal.subject,profile:b.profile}));audit(projectId,principal.subject,'ENGINEERING_JOB_SUBMITTED',result.job_id);return reply(res,202,{...result,project_id:projectId});
        }
      }
      m=path.match(/^\/api\/projects\/([^/]+)\/jobs\/([a-f0-9-]+)(?:\/(logs|result|cancel|checkpoint|resume))?$/);
      if(m){const [,projectId,jobId,action]=m;const scope=action==='cancel'?'engineering:cancel':action==='resume'?'engineering:execute':'engineering:read';const access=projectAccess(auth,principal,projectId,scope);if(!access)return reply(res,404,{error:'not found'});
        if((action==='cancel'||action==='resume')&&req.method!=='POST')return reply(res,405,{error:'POST required'});if(!action&&req.method!=='GET')return reply(res,405,{error:'GET required'});if(['logs','result','checkpoint'].includes(action)&&req.method!=='GET')return reply(res,405,{error:'GET required'});
        const owned=db.prepare('SELECT * FROM worker_jobs WHERE job_id=? AND project_id=? AND owner=?').get(jobId,projectId,principal.subject);if(!owned)return reply(res,404,{error:'not found'});
        if(action==='checkpoint'){const status=await workerCall(stateDir,auth,principal,access.project,{action:'status',job_id:jobId});persistCheckpoint(owned,status);const latest=db.prepare('SELECT checkpoint_json FROM worker_jobs WHERE job_id=?').get(jobId);let checkpoint={};try{checkpoint=JSON.parse(latest.checkpoint_json??'{}');}catch{}return reply(res,200,{job_id:jobId,parent_job_id:owned.parent_job_id,checkpoint});}
        if(action==='resume'&&req.method==='POST'){
          const body=await readBody(req);if(!access.grants.scopes.includes('engineering:recover'))return reply(res,403,{error:'engineering:recover scope required'});if(body.side_effects_reconciled!==true||typeof body.recovery_note!=='string'||body.recovery_note.trim().length<8||body.recovery_note.length>1000||typeof body.profile!=='string'||typeof body.resume_key!=='string'||body.resume_key.length<8||body.resume_key.length>160)return reply(res,400,{error:'resume requires reconciled side effects, bounded review note, profile and idempotent resume key'});
          const profile=auth.profiles[body.profile];if(!profile||!profile.projects?.includes(projectId))return reply(res,403,{error:'command profile is not permitted for this project'});
          const approval=approvalStatus(auth,principal,projectId,body.approval_ref,'engineering:recover');if(!approval||!approvalStatus(auth,principal,projectId,body.approval_ref,'engineering:execute'))return reply(res,403,{error:'active recovery and execution approvals are required'});
          const prior=await workerCall(stateDir,auth,principal,access.project,{action:'status',job_id:jobId});if(prior.status!=='INTERRUPTED')return reply(res,409,{error:'only an interrupted job can be resumed'});
          const result=await workerCall(stateDir,auth,principal,access.project,{action:'submit',profile:body.profile,approval_ref:body.approval_ref,idempotency_key:`resume:${jobId}:${body.resume_key}`,timeout:body.timeout});const checkpoint=JSON.stringify({status:result.status,parent_job_id:jobId,side_effects_reconciled:true,recovery_note_sha256:createHash('sha256').update(body.recovery_note).digest('hex'),updated_at:date()});db.prepare('INSERT OR IGNORE INTO worker_jobs(job_id,project_id,owner,profile,created_at,parent_job_id,resume_key,checkpoint_json) VALUES(?,?,?,?,?,?,?,?)').run(result.job_id,projectId,principal.subject,body.profile,date(),jobId,body.resume_key,checkpoint);audit(projectId,principal.subject,'ENGINEERING_JOB_RESUMED_FROM_INTERRUPTED',result.job_id);return reply(res,202,{...result,project_id:projectId,parent_job_id:jobId});
        }
        const operation=action==='logs'?'logs':action==='result'?'result':action==='cancel'?'cancel':'status';const result=await workerCall(stateDir,auth,principal,access.project,{action:operation,job_id:jobId});persistCheckpoint(owned,result);if(action==='cancel')audit(projectId,principal.subject,'ENGINEERING_JOB_CANCEL_REQUESTED',jobId);return reply(res,200,result);
      }
      m=path.match(/^\/api\/projects\/([^/]+)\/threads\/([a-f0-9-]+)\/messages$/);
      if(m){const [,projectId,threadId]=m;const access=projectAccess(auth,principal,projectId,'read');if(!access)return reply(res,404,{error:'not found'});const thread=db.prepare('SELECT * FROM threads WHERE id=? AND project_id=? AND owner=?').get(threadId,projectId,principal.subject);if(!thread)return reply(res,404,{error:'not found'});
        if(req.method==='GET'){const rows=db.prepare('SELECT id,actor_id,role,body,created_at FROM messages WHERE thread_id=? ORDER BY created_at').all(threadId);return reply(res,200,{messages:rows});}
        if(req.method==='POST'){if(!access.grants.scopes.includes('thread:write'))return reply(res,403,{error:'thread write scope required'});const b=await readBody(req);if(typeof b.body!=='string'||!b.body.trim()||b.body.length>12000)return reply(res,400,{error:'invalid message'});const id=randomUUID(),created=date();db.prepare('INSERT INTO messages VALUES(?,?,?,?,?,?,?)').run(id,threadId,projectId,principal.subject,'owner',b.body.trim(),created);audit(projectId,principal.subject,'MESSAGE_CREATED',id);return reply(res,201,{id,thread_id:threadId,actor_id:principal.subject,role:'owner',body:b.body.trim(),created_at:created});}
      }
      m=path.match(/^\/api\/projects\/([^/]+)\/tasks\/([a-f0-9-]+)\/advance$/);
      if(m&&req.method==='POST'){const [,projectId,taskId]=m;const access=projectAccess(auth,principal,projectId,'read');if(!access)return reply(res,404,{error:'not found'});const task=db.prepare('SELECT * FROM tasks WHERE id=? AND project_id=? AND owner=?').get(taskId,projectId,principal.subject);if(!task)return reply(res,404,{error:'not found'});const b=await readBody(req);const t=transitions[task.state]?.[b.event];if(!t||!access.grants.scopes.includes(t.scope))return reply(res,403,{error:'workflow transition is not authorized'});
        let checkpoint;try{checkpoint=JSON.parse(task.checkpoint??'{}');}catch{checkpoint={self_fix_attempt:Number(task.checkpoint?.match(/self_fix_attempt=(\d+)/)?.[1]??0)};}
        const attempts=Number(checkpoint.self_fix_attempt??0),selfFix=task.state==='QA_FAILED';if(selfFix&&attempts>=1)return reply(res,409,{error:'bounded self-fix limit reached; owner review required'});
        if(b.event==='save_checkpoint'){if(typeof b.manifest_sha!=='string'||!/^([a-f0-9]{40}|[a-f0-9]{64})$/i.test(b.manifest_sha)||b.test_status!=='PASS'||typeof b.report!=='string'||!b.report.trim()||b.report.length>4000)return reply(res,400,{error:'checkpoint requires a manifest SHA, passing test status and bounded report'});checkpoint={...checkpoint,manifest_sha:b.manifest_sha.toLowerCase(),test_status:b.test_status,report:b.report.replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi,'[REDACTED]').replace(/\b(?:sk|gh[pousr]_[A-Za-z0-9]{8,})[A-Za-z0-9_-]*\b/g,'[REDACTED]'),evidence_status:'OWNER_SUBMITTED_NOT_INDEPENDENTLY_VERIFIED',checkpointed_at:date()};}
        if(selfFix)checkpoint.self_fix_attempt=attempts+1;const updated=date();const checkpointValue=JSON.stringify(checkpoint);db.prepare('UPDATE tasks SET state=?,assigned_role=?,checkpoint=?,updated_at=? WHERE id=?').run(t.next,roles[t.next]??'owner',checkpointValue,updated,taskId);audit(projectId,principal.subject,`WORKFLOW_${t.next}`,taskId);return reply(res,200,{id:taskId,state:t.next,assigned_role:roles[t.next]??'owner',checkpoint:checkpointValue,updated_at:updated});
      }
      return reply(res,404,{error:'not found'});
    }catch(e){return reply(res,e.status??400,{error:e.status===503?'worker adapter unavailable':String(e.message??'request failed').slice(0,240)});}
  }
  function persistCheckpoint(row,result){let previous={};try{previous=JSON.parse(row.checkpoint_json??'{}');}catch{}const checkpoint={...previous,status:result.status,updated_at:date(),...(result.exit_code!==undefined?{exit_code:result.exit_code}:{}),...(result.error?{error:result.error}: {})};db.prepare('UPDATE worker_jobs SET checkpoint_json=? WHERE job_id=?').run(JSON.stringify(checkpoint),row.job_id);}
  function audit(projectId,actor,event,entity){db.prepare('INSERT INTO audit_events VALUES(?,?,?,?,?,?)').run(randomUUID(),projectId,actor,event,entity,date());}
  const server=http.createServer((req,res)=>{void handler(req,res);});server.on('close',()=>{store.close();void workerController.shutdown();});
  return {server,handler,auth,store,stateDir,workerController};
}

if(import.meta.url===`file://${process.argv[1]}`){
  const host=process.env.WORKFORCE_HOST??'127.0.0.1';if(!['127.0.0.1','::1','localhost'].includes(host))throw new Error('API host must be loopback-only');
  const {server,workerController}=createApp();const port=Number(process.env.PORT??8787);server.listen(port,host,()=>process.stdout.write(`Workforce API listening on ${host}:${port}\n`));
  let stopping=false;const stop=()=>{if(stopping)return;stopping=true;void workerController.shutdown().finally(()=>server.close(()=>process.exit(0)));};process.on('SIGINT',stop);process.on('SIGTERM',stop);
}
