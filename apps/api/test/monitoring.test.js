import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash,randomBytes,randomUUID} from 'node:crypto';
import {EventEmitter} from 'node:events';
import {Writable} from 'node:stream';
import {createApp} from '../src/server.js';
import {freshness} from '../src/monitoring.js';

async function invoke(app,path,{method='GET',body,token}={}){
  const req=new EventEmitter();Object.assign(req,{method,url:path,headers:token?{authorization:`Bearer ${token}`}:{}});
  process.nextTick(()=>{if(body!==undefined)req.emit('data',Buffer.from(JSON.stringify(body)));req.emit('end');});
  let status,output='';const res=new Writable({write(chunk,_e,cb){output+=chunk;cb();}});res.writeHead=code=>{status=code;};await app.handler(req,res);return {status,data:JSON.parse(output)};
}
function fixture(t){
  const dir=mkdtempSync(join(tmpdir(),'monitor-test-'));const workspace=join(dir,'workspace');mkdirSync(workspace,{mode:0o700});const workspaceB=join(dir,'other');mkdirSync(workspaceB,{mode:0o700});const stateDir=join(dir,'state');mkdirSync(stateDir,{mode:0o700});
  const owner=randomBytes(32).toString('hex'),monitor=randomBytes(32).toString('hex');
  const scopes=['read','task:create','workflow:run','workflow:director','workflow:developer','workflow:qa','engineering:execute','engineering:read','engineering:recover'];
  const project={id:'pilot',name:'Synthetic pilot',workspace,repository:'synthetic/pilot',branch:'feature/test',environment:'isolated-development',draft_pr:'https://github.com/synthetic/pilot/pull/2',pipeline:{developer:'dev',qa:'qa',self_fix:'fix'}};
  const config={version:1,projects:[project,{id:'other',name:'Other',workspace:workspaceB}],principals:[{subject:'owner',token_sha256:createHash('sha256').update(owner).digest('hex'),projects:{pilot:{workspace,scopes,approval_refs:['approved']}}},{subject:'monitor',token_sha256:createHash('sha256').update(monitor).digest('hex'),projects:{pilot:{workspace,scopes:['monitor:read']}}}],approvals:{approved:{project_id:'pilot',subject:'owner',status:'APPROVED',repository:'synthetic/pilot',branch:'feature/test',environment:'isolated-development',owner_actor:'owner',max_cost_usd:0,allowed_actions:['engineering:execute','qa:execute'],forbidden_actions:['merge','production:deploy','paid-api','other-repository:write'],scopes:['engineering:execute','engineering:recover'],expires_at:new Date(Date.now()+3600000).toISOString()},pending:{project_id:'pilot',status:'PENDING'}},command_profiles:Object.fromEntries(['dev','qa','fix'].map(id=>[id,{command:['/usr/bin/true'],projects:['pilot'],role:id==='qa'?'qa':'developer',executor:id==='qa'?'local-ci':'codex'}]))};
  const authPath=join(dir,'auth.json');writeFileSync(authPath,JSON.stringify(config),{mode:0o600});
  const jobs=new Map();let executorCalls=0;
  const app=createApp({authPath,stateDir,snapshot:async()=> 'a'.repeat(40),executor:async(_p,_project,request)=>{executorCalls++;if(request.action==='submit'){const job_id=randomUUID();jobs.set(job_id,{status:'COMPLETED',exit_code:0});return {job_id};}return jobs.get(request.job_id);}});
  t.after(async()=>{app.director.stop();await app.workerController.shutdown();app.store.close();rmSync(dir,{recursive:true,force:true});});
  return {app,owner,monitor,dir,workspace,authPath,config,get executorCalls(){return executorCalls;},request:(path,options={})=>invoke(app,path,{token:owner,...options})};
}

test('isolated API acceptance: Owner instruction through Director to read-only monitor, with zero monitor mutations',async t=>{
  const f=fixture(t),path='/api/monitoring/v1/projects/pilot';
  assert.equal((await f.request(path,{token:''})).status,401);assert.equal((await f.request(path)).status,404,'owner lacks dedicated scope');
  assert.equal((await f.request('/api/monitoring/v1/projects/other',{token:f.monitor})).status,404);
  const task=await f.request('/api/projects/pilot/tasks',{method:'POST',body:{title:'Secret-looking synthetic title',description:'private instruction must never enter monitoring'}});assert.equal(task.status,201);
  const run=await f.request('/api/projects/pilot/runs',{method:'POST',body:{task_id:task.data.id,approval_ref:'approved',idempotency_key:'acceptance-run-0001'}});assert.equal(run.status,202);
  for(let i=0;i<5;i++)await f.app.director.tick();
  const db=f.app.store.db;
  const before=db.prepare('SELECT total_changes() n').get().n,calls=f.executorCalls;
  const result=await f.request(path,{token:f.monitor});assert.equal(result.status,200);assert.equal(result.data.runs[0].state,'REPORTED');assert.equal(result.data.runs[0].progress.percent,100);assert.equal(result.data.runs[0].latest_checkpoint.commit_sha,'a'.repeat(40));assert.equal(result.data.approval.pending_count,1);assert.equal(result.data.hermes_health.status,'UNAVAILABLE');assert.ok(result.data.jobs[0].project_id==='pilot');assert.equal(result.data.jobs[0].working_directory,f.workspace);assert.ok(result.data.jobs[0].worker_id);assert.ok(result.data.jobs[0].current_task.task_id);assert.equal(result.data.jobs[0].last_checkpoint.test_status,'PASS');assert.ok(['CURRENT','STALE','UNAVAILABLE'].includes(result.data.jobs[0].freshness.state));
  const raw=JSON.stringify(result.data);for(const prohibited of ['private instruction','Secret-looking','token_sha256','approval_ref','authorization','Bearer'])assert.equal(raw.includes(prohibited),false,prohibited);
  for(const method of ['POST','PUT','PATCH','DELETE','HEAD','OPTIONS'])assert.equal((await f.request(path,{token:f.monitor,method,body:{action:'start'}})).status,405);
  assert.equal((await f.request(path+'?action=start',{token:f.monitor})).status,400);
  for(const route of ['/api/projects/pilot/tasks','/api/projects/pilot/jobs','/api/projects/pilot/worker','/api/projects/pilot/runs','/api/agents','/api/monitoring/v1/projects/pilot/execute']){
    for(const method of ['GET','POST'])assert.equal((await f.request(route,{token:f.monitor,method,body:{action:'start'}})).status,403,`${method} ${route}`);
  }
  assert.equal(db.prepare('SELECT total_changes() n').get().n,before);assert.equal(f.executorCalls,calls);assert.equal(f.app.workerController.status(),'STOPPED');
  console.log('ACCEPTANCE owner→director→developer→qa→checkpoint→monitor PASS; monitor_db_writes=0 monitor_executor_calls=0');
});

test('monitoring freshness and projections reject stale/future data, forged evidence and raw errors',async t=>{
  const f=fixture(t),db=f.app.store.db,now=Date.now();
  db.prepare('INSERT INTO worker_heartbeats VALUES(?,?,?,?,?,?,?)').run('developer','pilot','developer','working',null,null,new Date(now-120000).toISOString());
  let result=(await f.request('/api/monitoring/v1/projects/pilot',{token:f.monitor})).data;
  assert.equal(result.workers.find(x=>x.worker_id==='developer').data_state,'STALE');assert.equal(result.workers.find(x=>x.worker_id==='developer').status,'unknown');
  db.prepare('INSERT INTO worker_jobs(job_id,project_id,owner,profile,created_at,checkpoint_json) VALUES(?,?,?,?,?,?)').run(randomUUID(),'pilot','owner','dev',new Date().toISOString(),JSON.stringify({status:'UNKNOWN Bearer private',error:'private error',updated_at:new Date(now+300000).toISOString(),instruction:'private'}));
  result=(await f.request('/api/monitoring/v1/projects/pilot',{token:f.monitor})).data;
  assert.equal(result.jobs[0].status,'UNAVAILABLE');assert.equal(result.jobs[0].freshness.state,'UNAVAILABLE');assert.equal(JSON.stringify(result).includes('private'),false);
  assert.equal(freshness(undefined).state,'UNAVAILABLE');assert.equal(freshness(new Date().toISOString()).state,'CURRENT');
  const mixed=structuredClone(f.config);mixed.principals[1].projects.pilot.scopes.push('engineering:execute');writeFileSync(f.authPath,JSON.stringify(mixed),{mode:0o600});assert.throws(()=>createApp({authPath:f.authPath,stateDir:join(f.dir,'bad-state')}),/dedicated read-only scope/);
});

test('real isolated HTTP listener returns dedicated monitoring contract without operational writes',async t=>{
  const f=fixture(t);
  let address;
  try{
    await new Promise((resolve,reject)=>{f.app.server.once('error',reject);f.app.server.listen(0,'127.0.0.1',resolve);});address=f.app.server.address();
  }catch(error){if(['EPERM','EACCES'].includes(error.code)){t.skip('environment denies loopback listener');return;}throw error;}
  const before=f.app.store.db.prepare('SELECT total_changes() n').get().n;
  try{
    const response=await fetch(`http://127.0.0.1:${address.port}/api/monitoring/v1/projects/pilot`,{headers:{authorization:`Bearer ${f.monitor}`}});
    assert.equal(response.status,200);assert.equal((await response.json()).read_only,true);
    const denied=await fetch(`http://127.0.0.1:${address.port}/api/projects/pilot/worker`,{method:'POST',headers:{authorization:`Bearer ${f.monitor}`,'content-type':'application/json'},body:JSON.stringify({action:'start'})});assert.equal(denied.status,403);
    assert.equal(f.app.store.db.prepare('SELECT total_changes() n').get().n,before);
  }finally{
    // Avoid firing app close callback before fixture cleanup closes the store.
    f.app.server.removeAllListeners('close');await new Promise(resolve=>f.app.server.close(resolve));
  }
});
