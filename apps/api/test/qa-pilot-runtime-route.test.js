import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,chmodSync,rmSync,mkdirSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash,randomBytes} from 'node:crypto';
import {EventEmitter} from 'node:events';
import {Writable} from 'node:stream';
import {createApp} from '../src/server.js';
import {SANRO_QA_PILOT,SANRO_QA_PILOT_PERMISSION_PROFILE} from '../src/sanro-qa-pilot-binding.js';

async function post(handler,token,body){
  const req=new EventEmitter();Object.assign(req,{method:'POST',url:`/api/projects/${SANRO_QA_PILOT.project_id}/runtime-acceptance`,headers:{authorization:`Bearer ${token}`,'content-type':'application/json'}});
  process.nextTick(()=>{req.emit('data',Buffer.from(JSON.stringify(body)));req.emit('end');});
  let status=0,text='';const res=new Writable({write(chunk,_encoding,callback){text+=chunk.toString();callback();}});res.writeHead=code=>{status=code;};
  await handler(req,res);return {status,data:JSON.parse(text||'{}')};
}

test('read-only pilot reaches the fixed runtime seam but launches no job without native approval',async t=>{
  const root=mkdtempSync(join(tmpdir(),'sanro-qa-route-')),state=join(root,'state');mkdirSync(state,{mode:0o700});
  const token=randomBytes(32).toString('hex'),subject='owner:synthetic';
  const project={id:SANRO_QA_PILOT.project_id,name:'SANRO QA',workspace:SANRO_QA_PILOT.workspace,
    repository:SANRO_QA_PILOT.repository,branch:SANRO_QA_PILOT.branch,source_sha:SANRO_QA_PILOT.source_sha,
    mainline_qa_only:true,worker_id:SANRO_QA_PILOT.worker_id,environment:'isolated-development',
    permission_profile:{...SANRO_QA_PILOT_PERMISSION_PROFILE}};
  const authPath=join(root,'auth.json');writeFileSync(authPath,JSON.stringify({version:1,projects:[project],
    principals:[{subject,token_sha256:createHash('sha256').update(token).digest('hex'),projects:{[project.id]:{
      workspace:project.workspace,scopes:['read','runtime:browser'],approval_refs:[SANRO_QA_PILOT.approval_id]}}}],
    approvals:{[SANRO_QA_PILOT.approval_id]:{id:SANRO_QA_PILOT.approval_id,project_id:project.id,subject,
      owner_actor:subject,status:'APPROVED',repository:project.repository,branch:project.branch,
      environment:'isolated-development',max_cost_usd:0,scopes:['runtime:browser'],
      allowed_actions:['qa:execute','runtime:browser'],forbidden_actions:['engineering:execute','git:write','worker:manage','ssh:staging','merge','production:deploy','paid-api','other-repository:write'],
      expires_at:SANRO_QA_PILOT.expires_at}},command_profiles:{sanro_qa_browser:{command:['/usr/bin/true'],
      projects:[project.id],executor:'local-ci',role:'qa',runtime_operation:SANRO_QA_PILOT.operation,runtime_timeout_seconds:180}}}),{mode:0o600});chmodSync(authPath,0o600);
  const calls=[];const app=createApp({authPath,stateDir:state,runtimeExecutor:async context=>{
    calls.push(context);return {status:'BLOCKED',job_id:context.request.idempotency_key,checkpoint_sha256:'a'.repeat(64)};
  }});
  t.after(async()=>{try{await app.stopWorker();}catch{}try{app.store.close();}catch{}rmSync(root,{recursive:true,force:true});});
  const result=await post(app.handler,token,{profile:'sanro_qa_browser',approval_ref:SANRO_QA_PILOT.approval_id,idempotency_key:'sanroqa-route-job-001'});
  assert.equal(result.status,503);assert.equal(result.data.status,'BLOCKED');
  assert.equal(calls.length,1);assert.equal(calls[0].admission.branch,'main');
  assert.equal(calls[0].admission.checkpoint_sha,SANRO_QA_PILOT.source_sha);
  assert.equal(calls[0].admission.worker_id,'sanro-qa');assert.equal(calls[0].nativeApprovalRequired,true);
});
