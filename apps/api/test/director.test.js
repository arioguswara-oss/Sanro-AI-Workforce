import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {randomUUID} from 'node:crypto';
import {Store} from '../src/store.js';
import {Director} from '../src/director.js';

function fixture(t,{failures=1}={}){
  const dir=mkdtempSync(join(tmpdir(),'director-test-'));const store=new Store(join(dir,'state.sqlite3'));t.after(()=>{store.close();rmSync(dir,{recursive:true,force:true});});
  const project={id:'pilot',workspace:dir,repository:'synthetic/pilot',branch:'feature/test',environment:'isolated-development',pipeline:{developer:'dev',qa:'qa',self_fix:'fix'}};
  const principal={subject:'owner',projects:{pilot:{workspace:dir,scopes:['read','workflow:run','workflow:director','workflow:developer','workflow:qa','engineering:execute','engineering:read']}}};
  const profiles=Object.fromEntries(['dev','qa','fix'].map(id=>[id,{projects:['pilot'],role:id==='qa'?'qa':'developer',executor:id==='qa'?'local-ci':'codex'}]));
  const auth={principals:new Map([['synthetic',principal]]),projects:new Map([['pilot',project]]),profiles};
  const jobs=new Map(),keys=new Map(),instructions=[];let sha='a'.repeat(40),qaCount=0,approved=true;
  const executor=async(_principal,_project,request)=>{
    if(request.action==='submit'){
      if(keys.has(request.idempotency_key))return {job_id:keys.get(request.idempotency_key),status:'QUEUED'};
      instructions.push(JSON.parse(request.instruction));const id=randomUUID();keys.set(request.idempotency_key,id);
      let status='COMPLETED';if(request.profile==='qa'&&qaCount++<failures)status='FAILED';
      jobs.set(id,{status,exit_code:status==='COMPLETED'?0:1});if(request.profile==='fix')sha='b'.repeat(40);
      return {job_id:id,status:'QUEUED'};
    }
    return jobs.get(request.job_id);
  };
  const options={db:store.db,auth,workerCall:executor,authorize:()=>approved,snapshot:async()=>sha};
  let director=new Director(options);
  const task=randomUUID(),now=new Date().toISOString();store.db.prepare('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)').run(task,'pilot','owner','Synthetic task','Make the fixture pass','CREATED','owner',null,now,now);
  const submit=()=>director.submit(principal,project,{task_id:task,approval_ref:'approved',idempotency_key:'one-owner-instruction'});
  return {store,auth,project,principal,jobs,keys,instructions,submit,task,options,get director(){return director;},restart(){director=new Director(options);return director;},revoke(){approved=false;},setSha(value){sha=value;}};
}

test('one instruction automatically reaches Developer, QA, bounded self-fix, checkpoint and consolidated outbox across restart',async t=>{
  const f=fixture(t),run=f.submit();assert.equal(f.submit().id,run.id);
  await f.director.tick();const first=f.director.get(run.id);assert.ok(first.job_id);
  // Simulate crash after durable executor enqueue but before run stores job ID.
  f.store.db.prepare('UPDATE director_runs SET job_id=NULL WHERE id=?').run(run.id);
  f.restart();await f.director.tick();assert.equal(f.director.get(run.id).job_id,first.job_id);assert.equal(f.jobs.size,1);
  for(let i=0;i<9;i++)await f.director.tick();
  const done=f.director.get(run.id);assert.equal(done.state,'REPORTED');assert.equal(done.attempt,1);assert.equal(done.test_status,'PASS');assert.equal(done.candidate_sha,'b'.repeat(40));
  assert.deepEqual(f.instructions.map(x=>x.stage),['DEVELOPER','QA','SELF_FIX','QA']);
  assert.equal(f.instructions[0].instruction,'Make the fixture pass');assert.ok(f.instructions.every(x=>x.project_id==='pilot'));
  const checkpoint=JSON.parse(f.store.db.prepare('SELECT checkpoint FROM tasks WHERE id=?').get(f.task).checkpoint);assert.equal(checkpoint.qa_job_id,done.job_id);assert.equal(checkpoint.manifest_sha,done.candidate_sha);
  let sent=0;const transport={send:async payload=>{assert.equal(payload.commit_sha,done.candidate_sha);sent++;return {acknowledged:true};}};
  await f.director.deliverReports(transport);f.restart();await f.director.deliverReports(transport);assert.equal(sent,1);
  assert.equal(f.jobs.size,4);assert.ok(f.store.db.prepare('SELECT * FROM audit_events').all().length>8);
});

test('Director fails closed on revocation, project scope, profile mismatch and exhausted self-fix',async t=>{
  const f=fixture(t,{failures:2});assert.throws(()=>f.director.submit({...f.principal,subject:'other'},f.project,{task_id:f.task,approval_ref:'approved',idempotency_key:'other-task'}),/not found/);
  const run=f.submit();for(let i=0;i<10;i++)await f.director.tick();assert.equal(f.director.get(run.id).blocker,'SELF_FIX_LIMIT_REACHED');assert.equal(f.jobs.size,4);
  const g=fixture(t,{failures:0}),r=g.submit();g.revoke();await g.director.tick();assert.equal(g.director.get(r.id).blocker,'MANDATE_EXPIRED_OR_REVOKED');assert.equal(g.jobs.size,0);
  const h=fixture(t);h.auth.profiles.dev.executor='unverified-model';assert.throws(()=>h.submit(),/mandate/);
  h.auth.profiles.dev.executor='codex';h.project.environment='production';assert.throws(()=>h.submit(),/mandate/);
});

test('uncertain execution blocks without replay and QA cannot validate a moving candidate',async t=>{
  const f=fixture(t,{failures:0}),r=f.submit();await f.director.tick();const job=f.director.get(r.id).job_id;f.jobs.set(job,{status:'INTERRUPTED'});await f.director.tick();await f.director.tick();assert.equal(f.director.get(r.id).blocker,'SIDE_EFFECT_REVIEW_REQUIRED');assert.equal(f.jobs.size,1);
  const g=fixture(t,{failures:0}),s=g.submit();await g.director.tick();await g.director.tick();await g.director.tick();g.setSha('c'.repeat(40));await g.director.tick();assert.equal(g.director.get(s.id).blocker,'CANDIDATE_CHANGED_DURING_QA');assert.equal(g.store.db.prepare('SELECT COUNT(*) n FROM report_outbox').get().n,0);
});

test('explicit recovery preserves checkpoint and uses a new deduplicated execution generation',async t=>{
  const f=fixture(t,{failures:0}),run=f.submit();await f.director.tick();const original=f.director.get(run.id).job_id;
  f.jobs.set(original,{status:'INTERRUPTED'});await f.director.tick();
  const review={side_effects_reconciled:true,recovery_note:'Reviewed synthetic side effects',approval_ref:'approved'};
  await assert.rejects(f.director.resume(f.principal,f.project,run.id,review),/mandate/);
  f.principal.projects.pilot.scopes.push('engineering:recover');await f.director.resume(f.principal,f.project,run.id,review);
  for(let i=0;i<5;i++)await f.director.tick();const done=f.director.get(run.id);
  assert.equal(done.state,'REPORTED');assert.equal(done.recovery_count,1);assert.notEqual(done.job_id,original);assert.equal(f.jobs.size,3);
  assert.equal(JSON.stringify(f.store.db.prepare('SELECT * FROM audit_events').all()).includes(review.recovery_note),false);
});
