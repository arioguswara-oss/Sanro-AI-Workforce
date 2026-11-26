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

async function invoke(handler,path,{token,body}={}){
  const req=new EventEmitter();Object.assign(req,{method:'POST',url:path,headers:{authorization:`Bearer ${token}`,'content-type':'application/json'}});
  process.nextTick(()=>{req.emit('data',Buffer.from(JSON.stringify(body)));req.emit('end');});
  let status=0,text='';const res=new Writable({write(chunk,_encoding,callback){text+=chunk.toString();callback();}});res.writeHead=code=>{status=code;};await handler(req,res);return {status,data:JSON.parse(text||'{}')};
}

function fixture(t,runtimeScope='runtime:browser',hostAdapter=null){
  const root=mkdtempSync(join(tmpdir(),'workforce-runtime-api-')),workspace=join(root,'project'),state=join(root,'state');
  mkdirSync(workspace,{mode:0o700});mkdirSync(state,{mode:0o700});
  const git=(...args)=>execFileSync('git',['-C',workspace,...args],{encoding:'utf8'}).trim();
  execFileSync('git',['init','--quiet','-b','feature/runtime-test',workspace]);git('config','user.name','Synthetic Owner');git('config','user.email','owner@example.invalid');
  git('remote','add','origin','https://github.com/synthetic/runtime-api.git');git('commit','--quiet','--allow-empty','-m','baseline');
  const owner=randomBytes(32).toString('hex'),project={id:'runtime-api',name:'Runtime API synthetic',workspace,repository:'synthetic/runtime-api',branch:'feature/runtime-test',environment:'isolated-development',worker_id:'runtime-worker'};
  const scopes=['read','engineering:execute','runtime:browser','runtime:mariadb'];
  const approval={project_id:project.id,subject:'owner',status:'APPROVED',repository:project.repository,branch:project.branch,environment:project.environment,owner_actor:'owner',max_cost_usd:0,allowed_actions:['engineering:execute','qa:execute',runtimeScope],forbidden_actions:['merge','production:deploy','paid-api','other-repository:write'],scopes:['engineering:execute',runtimeScope],expires_at:new Date(Date.now()+60000).toISOString()};
  const authPath=join(root,'auth.json');writeFileSync(authPath,JSON.stringify({version:1,projects:[project],principals:[{subject:'owner',token_sha256:createHash('sha256').update(owner).digest('hex'),projects:{[project.id]:{workspace,scopes,approval_refs:['runtime-approval']}}}],approvals:{'runtime-approval':approval},command_profiles:{browser:{command:['/usr/bin/true'],projects:[project.id],role:'qa',executor:'local-ci',runtime_operation:'browser_smoke',runtime_timeout_seconds:120}}}),{mode:0o600});chmodSync(authPath,0o600);
  const calls=[];const app=createApp({authPath,stateDir:state,runtimeExecutor:async context=>{calls.push(context);if(hostAdapter)return hostAdapter(context);return {status:'BLOCKED',job_id:context.request.idempotency_key,checkpoint_sha256:'a'.repeat(64)};}});
  t.after(async()=>{try{await app.stopWorker();}catch{}try{app.store.close();}catch{}rmSync(root,{recursive:true,force:true});});
  return {app,owner,calls,project};
}

test('runtime acceptance API applies project admission and operation-specific approval before adapter call',async t=>{
  const f=fixture(t);
  const result=await invoke(f.app.handler,'/api/projects/runtime-api/runtime-acceptance',{token:f.owner,body:{profile:'browser',approval_ref:'runtime-approval',idempotency_key:'runtime-api-test-001'}});
  assert.equal(result.status,503); // injected adapter returns BLOCKED; this is not runtime PASS evidence.
  assert.equal(result.data.status,'BLOCKED');assert.equal(f.calls.length,1);
  assert.equal(f.calls[0].admission.project_id,'runtime-api');assert.equal(f.calls[0].admission.branch,'feature/runtime-test');
  assert.equal(f.calls[0].profile.runtime_operation,'browser_smoke');
  assert.equal(f.calls[0].nativeApprovalRequired,true);
});

test('runtime acceptance rejects missing operation-specific approval before invoking adapter',async t=>{
  const f=fixture(t,'runtime:mariadb');
  const result=await invoke(f.app.handler,'/api/projects/runtime-api/runtime-acceptance',{token:f.owner,body:{profile:'browser',approval_ref:'runtime-approval',idempotency_key:'runtime-api-test-002'}});
  assert.equal(result.status,403);assert.equal(f.calls.length,0);
});

test('runtime host callback cannot bypass the native approval evidence binding',async t=>{
  const f=fixture(t,'runtime:browser',async context=>context.invokeAfterNativeApproval(true));
  const result=await invoke(f.app.handler,'/api/projects/runtime-api/runtime-acceptance',{token:f.owner,body:{profile:'browser',approval_ref:'runtime-approval',idempotency_key:'runtime-api-test-003'}});
  assert.equal(result.status,403);assert.equal(f.calls.length,1);
});
