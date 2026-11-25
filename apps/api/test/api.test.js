import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,chmodSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash,randomBytes} from 'node:crypto';
import {EventEmitter} from 'node:events';
import {Writable} from 'node:stream';
import {spawn,spawnSync} from 'node:child_process';
import {DatabaseSync} from 'node:sqlite';
import {createApp} from '../src/server.js';
import {HerdrWorkerController} from '../src/herdr-worker-controller.js';

const repoRoot=fileURLToPath(new URL('../../../',import.meta.url));
const landlock=Number(spawnSync('python3',['-c','from landlock_sandbox import landlock_abi; print(landlock_abi())'],{cwd:repoRoot,encoding:'utf8'}).stdout?.trim()??0);
async function fixture(t,{herdrBackend=false,herdrRunner,workerManage=false,secondProject=false}={}){
  const token=randomBytes(32).toString('hex');
  const dir=mkdtempSync(join(tmpdir(),'workforce-api-test-')),workspace=join(dir,'project-a');mkdirSync(workspace,{mode:0o700});
  const workspaceB=join(dir,'project-b');mkdirSync(workspaceB,{mode:0o700});const scopes=['read','thread:write','task:create','workflow:director','workflow:developer','workflow:qa','engineering:execute','engineering:read','engineering:cancel','engineering:recover',...(workerManage?['worker:manage','worker:read']:[])];const projectAccess={'project-a':{workspace,scopes,approval_refs:['test-approval-1']}};if(secondProject)projectAccess['project-b']={workspace:workspaceB,scopes,approval_refs:['test-approval-b']};const config={version:1,projects:[{id:'project-a',name:'Project A',workspace},{id:'project-b',name:'Project B',workspace:workspaceB}],principals:[{subject:'owner-test',token_sha256:createHash('sha256').update(token).digest('hex'),projects:projectAccess}],approvals:{'test-approval-1':{project_id:'project-a',subject:'owner-test',status:'APPROVED',scopes:['engineering:execute','engineering:recover'],expires_at:new Date(Date.now()+3600000).toISOString()},...(secondProject?{'test-approval-b':{project_id:'project-b',subject:'owner-test',status:'APPROVED',scopes:['engineering:execute','engineering:recover'],expires_at:new Date(Date.now()+3600000).toISOString()}}:{})},command_profiles:{print:{command:['/usr/bin/printf','synthetic-result\\n'],projects:secondProject?['project-a','project-b']:['project-a'],approval_required:true},sleep:{command:['/usr/bin/sleep','5'],projects:['project-a'],approval_required:true}}};
  const authPath=join(dir,'auth.json');writeFileSync(authPath,JSON.stringify(config),{mode:0o600});chmodSync(authPath,0o600);const stateDir=join(dir,'state');mkdirSync(stateDir,{mode:0o700});
  const names=['WORKFORCE_WORKER_BACKEND','WORKFORCE_HERDR_PROJECT_ID','WORKFORCE_HERDR_MACHINE','WORKFORCE_HERDR_CORE_ENV_ATTESTED'];const previous=Object.fromEntries(names.map(name=>[name,process.env[name]]));
  if(herdrBackend){process.env.WORKFORCE_WORKER_BACKEND='herdr';process.env.WORKFORCE_HERDR_PROJECT_ID='project-a';process.env.WORKFORCE_HERDR_CORE_ENV_ATTESTED='1';delete process.env.WORKFORCE_HERDR_MACHINE;}
  let app;
  try{app=createApp({authPath,stateDir,allowWorkerControl:herdrBackend,herdrRunner});}finally{for(const name of names){if(previous[name]===undefined)delete process.env[name];else process.env[name]=previous[name];}}
  let childWorker;
  async function invoke(handler,path,{method='GET',body,credential=token}={}){const req=new EventEmitter();req.method=method;req.url=path;req.headers=credential?{authorization:`Bearer ${credential}`,'content-type':'application/json'}:{};process.nextTick(()=>{if(body!==undefined)req.emit('data',Buffer.from(JSON.stringify(body)));req.emit('end');});let status=0,output='';const res=new Writable({write(chunk,_encoding,callback){output+=chunk.toString();callback();}});res.writeHead=(code)=>{status=code;};await handler(req,res);return {status,data:JSON.parse(output||'{}')};}
  const request=(path,options)=>invoke(app.handler,path,options);
  t.after(async()=>{if(childWorker&&childWorker.exitCode===null){childWorker.kill('SIGTERM');await new Promise(r=>childWorker.once('exit',r));}try{await app.stopWorker();}catch{}try{app.store.close();}catch{}try{rmSync(dir,{recursive:true,force:true});}catch{}});
  return {app,dir,workspace,stateDir,request,invoke,token,get childWorker(){return childWorker;},set childWorker(v){childWorker=v;}};
}
const post=(path,body,credential)=>({method:'POST',path,body,credential});
const waitExit=child=>child.exitCode!==null?Promise.resolve(child.exitCode):new Promise((resolve,reject)=>{child.once('exit',resolve);child.once('error',reject);});

test('API denies by default, scopes project reads, and persists threads/messages/tasks',async t=>{
  const f=await fixture(t);
  assert.equal((await f.request('/api/projects',{credential:''})).status,401);
  const projects=await f.request('/api/projects');assert.deepEqual(projects.data.projects.map(x=>x.id),['project-a']);
  assert.equal((await f.request('/api/projects/project-b/threads')).status,404);
  assert.deepEqual((await f.request('/api/projects/project-a/approvals')).data.approvals.map(a=>a.id),['test-approval-1']);
  const created=await f.request('/api/projects/project-a/threads',post('',{kind:'personal',agent_id:'director',title:'Checkpoint thread'}));assert.equal(created.status,201);
  const message=await f.request(`/api/projects/project-a/threads/${created.data.id}/messages`,post('',{body:'Owner task, synthetic only'}));assert.equal(message.status,201);
  const task=await f.request('/api/projects/project-a/tasks',post('',{title:'Synthetic workflow'}));assert.equal(task.status,201);
  const advance=async(event,extra={})=>f.request(`/api/projects/project-a/tasks/${task.data.id}/advance`,post('',{event,...extra}));
  for(const event of ['assign_director','assign_developer','submit_qa','qa_fail','bounded_self_fix','resubmit_qa','qa_pass','prepare_release_candidate'])assert.equal((await advance(event)).status,200,event);
  const syntheticSecret=['Bear','er ','sk-','1234567890123456'].join('');assert.equal((await advance('save_checkpoint',{manifest_sha:'a'.repeat(40),test_status:'PASS',report:syntheticSecret})).status,200);
  assert.equal((await advance('report_owner')).status,200);
  assert.equal((await f.request('/api/projects/project-a/threads')).data.threads.length,1);
  assert.equal((await f.request(`/api/projects/project-a/threads/${created.data.id}/messages`)).data.messages[0].body,'Owner task, synthetic only');
  const savedTask=(await f.request('/api/projects/project-a/tasks')).data.tasks[0];assert.equal(savedTask.state,'REPORTED');assert.equal(JSON.parse(savedTask.checkpoint).report,'[REDACTED]');
  const failingTask=await f.request('/api/projects/project-a/tasks',post('',{title:'Bounded retry'}));
  const advanceFailing=async(event,extra={})=>f.request(`/api/projects/project-a/tasks/${failingTask.data.id}/advance`,post('',{event,...extra}));
  for(const event of ['assign_director','assign_developer','submit_qa','qa_fail','bounded_self_fix','resubmit_qa','qa_fail'])assert.equal((await advanceFailing(event)).status,200,event);
  assert.equal((await advanceFailing('bounded_self_fix')).status,409);
  assert.ok((await f.request('/api/projects/project-a/activity')).data.events.length>=10);
  f.app.store.close();const restarted=createApp({authPath:join(f.dir,'auth.json'),stateDir:f.stateDir});
  assert.equal((await f.invoke(restarted.handler,`/api/projects/project-a/threads/${created.data.id}/messages`)).data.messages.length,1);
  assert.equal((await f.invoke(restarted.handler,'/api/projects/project-a/tasks')).data.tasks[0].state,'REPORTED');restarted.store.close();
});

test('Herdr backend is opt-in and binds its controller to one provisioned project',async t=>{
  const f=await fixture(t),names=['WORKFORCE_WORKER_BACKEND','WORKFORCE_HERDR_PROJECT_ID','WORKFORCE_HERDR_MACHINE','WORKFORCE_HERDR_CORE_ENV_ATTESTED'];
  const previous=Object.fromEntries(names.map(name=>[name,process.env[name]]));
  try{
    process.env.WORKFORCE_WORKER_BACKEND='herdr';process.env.WORKFORCE_HERDR_PROJECT_ID='project-a';
    delete process.env.WORKFORCE_HERDR_MACHINE;delete process.env.WORKFORCE_HERDR_CORE_ENV_ATTESTED;
    const app=createApp({authPath:join(f.dir,'auth.json'),stateDir:join(f.dir,'herdr-state')});
    assert.ok(app.workerController instanceof HerdrWorkerController);
    assert.equal(app.workerController.projectId,'project-a');
    app.store.close();
  }finally{
    for(const name of names){if(previous[name]===undefined)delete process.env[name];else process.env[name]=previous[name];}
  }
});

test('approved Herdr job runs a project worker end to end through a synthetic hc session',{skip:landlock?false:'NOT TESTED: Landlock unavailable; real worker remains fail-closed'},async t=>{
  const calls=[];const version='herdr-core 0.1.22\n';let f,child,runArgs;
  const herdrRunner=async args=>{
    calls.push(args);
    if(args[0]==='--version')return {stdout:version};
    if(args[0]==='server')return {stdout:'{"pid":1200}'};
    if(args[0]==='ls'){
      const terminals=child?[{address:'t-pilot',name:runArgs[runArgs.indexOf('--name')+1],state:child.exitCode===null?'live':'finished',exit_code:child.exitCode,finished_ms:Date.now(),labels:{'sanro.workforce':'jack-worker','sanro.project':f.app.workerController.project.tag},status:{state:child.exitCode===null?'working':'idle'}}]:[];
      return {stdout:JSON.stringify({terminals})};
    }
    if(args[0]==='run'){
      runArgs=args;const command=args.slice(args.indexOf('--')+1);const executable=command.indexOf('python3');
      const env=Object.fromEntries(command.slice(2,executable).map(item=>{const split=item.indexOf('=');return [item.slice(0,split),item.slice(split+1)];}));
      child=spawn('python3',command.slice(executable+1),{cwd:env.HOME,env,stdio:'ignore'});return {stdout:'{"address":"t-pilot"}'};
    }
    if(args[0]==='kill'){if(child&&child.exitCode===null){child.kill('SIGTERM');await new Promise(resolve=>child.once('exit',resolve));}return {stdout:'{"terminal":{"address":"t-pilot","state":"finished","reason":"killed","exit_code":null}}'};}
    if(args[0]==='read')return {stdout:'{"text":"synthetic worker status","complete":true}'};
    throw new Error(`unexpected hc command ${args[0]}`);
  };
  f=await fixture(t,{herdrBackend:true,herdrRunner,workerManage:true});
  const submissionStart=performance.now();
  const response=await f.request('/api/projects/project-a/jobs',post('',{profile:'print',idempotency_key:'herdr-auto-job-001',approval_ref:'test-approval-1'}));
  const herdrSubmitUs=(performance.now()-submissionStart)*1000;
  assert.ok(herdrSubmitUs<2_000_000,`Herdr job submission ${(herdrSubmitUs/1000).toFixed(1)}ms`);
  assert.equal(response.status,202,JSON.stringify(response.data));assert.match(response.data.job_id,/^[a-f0-9]{32}$/);
  const startupDeadline=Date.now()+2000;while(!calls.some(args=>args[0]==='run')&&Date.now()<startupDeadline)await new Promise(resolve=>setTimeout(resolve,5));
  const run=calls.find(args=>args[0]==='run');assert.ok(run,'automatic Herdr terminal creation');
  assert.equal(run[run.indexOf('--cwd')+1],f.workspace);assert.equal(run[run.indexOf('--name')+1],f.app.workerController.project.name);assert.ok(run.includes(`sanro.project=${f.app.workerController.project.tag}`));
  const deadline=Date.now()+5000;let jobs=[];while(Date.now()<deadline){jobs=(await f.request('/api/projects/project-a/jobs')).data.jobs;if(jobs[0]?.status==='COMPLETED')break;await new Promise(resolve=>setTimeout(resolve,25));}
  assert.equal(jobs[0]?.job_id,response.data.job_id);assert.equal(jobs[0]?.status,'COMPLETED');
  assert.match((await f.request(`/api/projects/project-a/jobs/${response.data.job_id}/logs`)).data.logs,/synthetic-result/);
  assert.equal((await f.request(`/api/projects/project-a/jobs/${response.data.job_id}/result`)).data.status,'COMPLETED');
  const workerStatus=await f.request('/api/projects/project-a/worker');assert.equal(workerStatus.status,200);assert.equal(workerStatus.data.status,'RUNNING');
  console.log(`HERDR_METRIC submission_us=${herdrSubmitUs.toFixed(1)}`);
});

test('Herdr one-project binding rejects another authorized project before job enqueue',async t=>{
  let workerStarts=0;const herdrRunner=async args=>{if(args[0]==='--version')return {stdout:'herdr-core 0.1.22\\n'};if(args[0]==='server')return {stdout:'{"pid":1200}'};if(args[0]==='ls')return {stdout:'{"terminals":[]}'};if(args[0]==='run'){workerStarts++;return {stdout:'{"address":"t-other"}'};}throw new Error(`unexpected hc command ${args[0]}`);};
  const f=await fixture(t,{herdrBackend:true,herdrRunner,workerManage:true,secondProject:true});
  const response=await f.request('/api/projects/project-b/jobs',post('',{profile:'print',idempotency_key:'cross-project-herdr-001',approval_ref:'test-approval-b'}));
  assert.equal(response.status,404,JSON.stringify(response.data));assert.equal(workerStarts,0);
  assert.equal(f.app.store.db.prepare('SELECT COUNT(*) AS n FROM worker_jobs WHERE project_id=?').get('project-b').n,0);
});

test('approved fixed-profile jobs are non-blocking, FIFO, deduplicated, cancellable and recover without replay',{skip:landlock?false:'NOT TESTED: Landlock unavailable; real worker remains fail-closed'},async t=>{
  const f=await fixture(t),path='/api/projects/project-a/jobs';
  const submit=async (profile,key,approval_ref='test-approval-1')=>f.request(path,post('',{profile,idempotency_key:key,approval_ref}));
  assert.equal((await submit('print','job-key-denied',null)).status,403);
  const start=performance.now(),first=await submit('print','stable-key-0001');const submitUs=(performance.now()-start)*1000;
  assert.equal(first.status,202,JSON.stringify(first.data));assert.ok(submitUs<2_000_000,`submission ${(submitUs/1000).toFixed(1)}ms`);
  assert.deepEqual((await submit('print','stable-key-0001')).data.job_id,first.data.job_id);
  assert.equal((await f.request(`/api/projects/project-b/jobs/${first.data.job_id}`)).status,404,'cross-project job read denied');
  const second=await submit('sleep','stable-key-0002');assert.equal(second.status,202);
  const worker=f.childWorker=spawn('python3',[join(repoRoot,'worker.py'),'--root',f.stateDir,'run'],{cwd:repoRoot,env:{PATH:'/usr/bin:/bin',HOME:f.stateDir,TMPDIR:join(f.stateDir,'tmp'),LANG:'C.UTF-8',PYTHONNOUSERSITE:'1'},stdio:'ignore'});
  const until=Date.now()+3000;let during;while(Date.now()<until){during=await f.request(path);if(during.data.jobs.some(j=>j.job_id===second.data.job_id&&j.status==='RUNNING'))break;await new Promise(r=>setTimeout(r,25));}
  assert.ok(during.data.jobs.some(j=>j.job_id===second.data.job_id&&j.status==='RUNNING'),`second job reached RUNNING: ${JSON.stringify(during.data.jobs)}`);
  const foregroundStart=performance.now();assert.equal((await f.request('/api/projects/project-a/threads')).status,200);const foregroundUs=(performance.now()-foregroundStart)*1000;assert.ok(foregroundUs<500_000,`foreground ${(foregroundUs/1000).toFixed(1)}ms`);
  assert.equal(await waitExit(worker),0,'worker exit');
  const jobs=(await f.request(path)).data.jobs;assert.deepEqual(jobs.slice(-2).map(j=>j.job_id),[first.data.job_id,second.data.job_id]);assert.ok(jobs.every(j=>j.status==='COMPLETED'),JSON.stringify(jobs));
  assert.match((await f.request(`${path}/${first.data.job_id}/logs`)).data.logs,/synthetic-result/);
  assert.equal((await f.request(`${path}/${first.data.job_id}/result`)).data.status,'COMPLETED');
  const cancelled=await submit('sleep','stable-key-0003');assert.equal(cancelled.status,202);
  const cancelWorker=f.childWorker=spawn('python3',[join(repoRoot,'worker.py'),'--root',f.stateDir,'run'],{cwd:repoRoot,env:{PATH:'/usr/bin:/bin',HOME:f.stateDir,TMPDIR:join(f.stateDir,'tmp'),LANG:'C.UTF-8',PYTHONNOUSERSITE:'1'},stdio:'ignore'});
  const cancelBy=Date.now()+2000;let running;while(Date.now()<cancelBy){running=await f.request(`${path}/${cancelled.data.job_id}`);if(running.data.status==='RUNNING')break;await new Promise(r=>setTimeout(r,20));}
  assert.equal(running.data.status,'RUNNING');assert.equal((await f.request(`${path}/${cancelled.data.job_id}/cancel`)).status,405,'GET cannot cancel a job');assert.equal((await f.request(`${path}/${cancelled.data.job_id}/cancel`,{method:'POST',body:{}})).status,200);
  assert.equal(await waitExit(cancelWorker),0,'cancel worker exit');
  assert.equal((await f.request(`${path}/${cancelled.data.job_id}`)).data.status,'CANCELLED');
  const q=new DatabaseSync(join(f.stateDir,'jobs.sqlite3'));q.prepare("UPDATE jobs SET state='running' WHERE id=?").run(first.data.job_id);q.close();
  const recovery=spawn('python3',[join(repoRoot,'worker.py'),'--root',f.stateDir,'run'],{cwd:repoRoot,env:{PATH:'/usr/bin:/bin',HOME:f.stateDir,TMPDIR:join(f.stateDir,'tmp'),LANG:'C.UTF-8',PYTHONNOUSERSITE:'1'},stdio:'ignore'});f.childWorker=recovery;assert.equal(await waitExit(recovery),0,'recovery worker exit');
  assert.equal((await f.request(`${path}/${first.data.job_id}`)).data.status,'INTERRUPTED','recovery marks interrupted work; does not replay');
  const oldLogs=(await f.request(`${path}/${first.data.job_id}/logs`)).data.logs;assert.equal((oldLogs.match(/\] start /g)??[]).length,1,'interrupted command was never replayed');
  const checkpoint=(await f.request(`${path}/${first.data.job_id}/checkpoint`)).data;assert.equal(checkpoint.checkpoint.status,'INTERRUPTED',JSON.stringify(checkpoint));
  const resumePath=`${path}/${first.data.job_id}/resume`,resumeBody={side_effects_reconciled:true,recovery_note:'Synthetic review confirmed safe retry',profile:'print',resume_key:'resume-key-0001',approval_ref:'test-approval-1'};
  assert.equal((await f.request(resumePath,post('',{...resumeBody,approval_ref:'unapproved'}))).status,403);
  const resumed=await f.request(resumePath,post('',resumeBody));assert.equal(resumed.status,202);assert.notEqual(resumed.data.job_id,first.data.job_id);assert.equal(resumed.data.parent_job_id,first.data.job_id);
  assert.equal((await f.request(resumePath,post('',resumeBody))).data.job_id,resumed.data.job_id,'resume idempotency');
  const resumedCheckpoint=(await f.request(`${path}/${resumed.data.job_id}/checkpoint`)).data;assert.equal(resumedCheckpoint.parent_job_id,first.data.job_id);assert.equal(resumedCheckpoint.checkpoint.side_effects_reconciled,true);assert.equal(JSON.stringify(resumedCheckpoint).includes('Synthetic review'),false);
  f.app.store.close();const restarted=createApp({authPath:join(f.dir,'auth.json'),stateDir:f.stateDir});
  const persisted=await f.invoke(restarted.handler,'/api/projects/project-a/tasks');assert.equal(persisted.status,200);assert.equal(persisted.data.tasks.length,0);restarted.store.close();
  console.log(`METRIC submission_us=${submitUs.toFixed(1)} foreground_us=${foregroundUs.toFixed(1)}`);
});
