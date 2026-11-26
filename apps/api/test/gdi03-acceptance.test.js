import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,chmodSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {execFileSync} from 'node:child_process';
import {randomBytes,createHash} from 'node:crypto';
import {EventEmitter} from 'node:events';
import {Writable} from 'node:stream';
import {createApp} from '../src/server.js';

async function invoke(handler,path,{token,method='GET',body}={}){
  const req=new EventEmitter();Object.assign(req,{method,url:path,headers:token?{authorization:`Bearer ${token}`,'content-type':'application/json'}:{}});
  process.nextTick(()=>{if(body!==undefined)req.emit('data',Buffer.from(JSON.stringify(body)));req.emit('end');});
  let status=0,text='';const res=new Writable({write(chunk,_encoding,callback){text+=chunk.toString();callback();}});res.writeHead=code=>{status=code;};await handler(req,res);return {status,data:JSON.parse(text||'{}')};
}

test('GDI-03 isolated orchestration: Director→admission→Hermes FIFO/lock→Codex fixture→QA→checkpoint→monitor',async t=>{
  const root=mkdtempSync(join(tmpdir(),'gdi03-orchestration-')),workspace=join(root,'project'),state=join(root,'state');
  mkdirSync(workspace,{mode:0o700});mkdirSync(state,{mode:0o700});
  execFileSync('git',['init','--quiet',workspace]);execFileSync('git',['-C',workspace,'checkout','--quiet','-b','feature/synthetic']);execFileSync('git',['-C',workspace,'config','user.name','Synthetic Owner']);execFileSync('git',['-C',workspace,'config','user.email','owner@example.invalid']);execFileSync('git',['-C',workspace,'remote','add','origin','https://github.com/synthetic/gdi03.git']);execFileSync('git',['-C',workspace,'commit','--quiet','--allow-empty','-m','synthetic baseline']);
  const fakeCodex=join(workspace,'.git','codex');
  writeFileSync(fakeCodex,"#!/usr/bin/python3\nimport json,sys\na=sys.argv\nrequired=['exec','--cd','--sandbox','workspace-write','--approve-for-me','--json','--ephemeral']\nif a[1]!='exec' or '--sandbox' not in a or a[a.index('--sandbox')+1]!='workspace-write' or '--approve-for-me' not in a or '--cd' not in a: raise SystemExit(31)\np=json.loads(a[-1].split('\\n',1)[1])['admission']\nif not all(p.get(k) for k in ('project_id','worker_id','job_id','workspace','checkpoint_sha')): raise SystemExit(32)\nprint('synthetic Codex executor completed')\n",{mode:0o700});chmodSync(fakeCodex,0o700);
  const owner=randomBytes(32).toString('hex'),monitor=randomBytes(32).toString('hex'),scopes=['read','task:create','workflow:run','workflow:director','workflow:developer','workflow:qa','engineering:execute','engineering:read'];
  const project={id:'gdi03',name:'GDI-03 synthetic',workspace,repository:'synthetic/gdi03',branch:'feature/synthetic',environment:'isolated-development',worker_id:'worker-gdi03',pipeline:{developer:'developer',qa:'qa',self_fix:'developer'}};
  const approval={project_id:'gdi03',subject:'owner',status:'APPROVED',repository:project.repository,branch:project.branch,environment:project.environment,owner_actor:'owner',max_cost_usd:0,allowed_actions:['engineering:execute','qa:execute'],forbidden_actions:['merge','production:deploy','paid-api','other-repository:write'],scopes:['engineering:execute'],expires_at:new Date(Date.now()+5*60_000).toISOString()};
  const config={version:1,projects:[project],principals:[{subject:'owner',token_sha256:createHash('sha256').update(owner).digest('hex'),projects:{gdi03:{workspace,scopes,approval_refs:['gdi03-approval']}}},{subject:'monitor',token_sha256:createHash('sha256').update(monitor).digest('hex'),projects:{gdi03:{workspace,scopes:['monitor:read']}}}],approvals:{'gdi03-approval':approval},command_profiles:{developer:{command:[fakeCodex],projects:['gdi03'],role:'developer',executor:'codex'},qa:{command:['/usr/bin/true'],projects:['gdi03'],role:'qa',executor:'local-ci'}}};
  const authPath=join(root,'auth.json');writeFileSync(authPath,JSON.stringify(config),{mode:0o600});chmodSync(authPath,0o600);
  const app=createApp({authPath,stateDir:state,startWorker:true});
  t.after(async()=>{try{await app.stopWorker();}catch{}try{app.store.close();}catch{}rmSync(root,{recursive:true,force:true});});
  const task=await invoke(app.handler,'/api/projects/gdi03/tasks',{token:owner,method:'POST',body:{title:'Synthetic GDI-03 task',description:'Use only the fake Codex and local QA profile.'}});assert.equal(task.status,201);
  const submitted=await invoke(app.handler,'/api/projects/gdi03/runs',{token:owner,method:'POST',body:{task_id:task.data.id,approval_ref:'gdi03-approval',idempotency_key:'gdi03-acceptance-01'}});assert.equal(submitted.status,202);
  let run;
  for(let i=0;i<36;i++){await app.director.tick();run=app.director.get(submitted.data.run_id);if(run.state!=='ACTIVE')break;await new Promise(resolve=>setTimeout(resolve,70));}
  assert.equal(run.state,'REPORTED',run.blocker??'run did not reach a terminal state');assert.equal(run.test_status,'PASS');
  const jobs=app.store.db.prepare('SELECT job_id,profile,checkpoint_json FROM worker_jobs WHERE project_id=? ORDER BY created_at').all('gdi03');assert.equal(jobs.length,2);
  for(const job of jobs){const cp=JSON.parse(job.checkpoint_json);assert.ok(cp.admission);assert.equal(cp.admission.project_id,'gdi03');assert.equal(cp.admission.worker_id,'worker-gdi03');assert.equal(cp.admission.workspace,workspace);assert.ok(cp.admission.checkpoint_sha);assert.equal(cp.status,'COMPLETED');}
  const checkpoint=JSON.parse(app.store.db.prepare('SELECT checkpoint FROM tasks WHERE id=?').get(task.data.id).checkpoint);assert.equal(checkpoint.test_status,'PASS');assert.equal(checkpoint.qa_job_id,run.job_id);
  const result=await invoke(app.handler,`/api/projects/gdi03/jobs/${run.job_id}/result`,{token:owner});assert.equal(result.status,200);assert.equal(result.data.status,'COMPLETED');
  const monitorResult=await invoke(app.handler,'/api/monitoring/v1/projects/gdi03',{token:monitor});assert.equal(monitorResult.status,200);assert.equal(monitorResult.data.jobs[0].working_directory,workspace);assert.equal(monitorResult.data.jobs[0].last_checkpoint.test_status,'PASS');assert.equal(monitorResult.data.hermes_health.status,'UNAVAILABLE');
});
