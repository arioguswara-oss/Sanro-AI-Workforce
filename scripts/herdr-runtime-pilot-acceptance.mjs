#!/usr/bin/env node
// Owner-authorized, single-project runtime acceptance. No production auth is read.
import {createHash, randomBytes} from 'node:crypto';
import {mkdtempSync, writeFileSync, chmodSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {EventEmitter} from 'node:events';
import {Writable} from 'node:stream';
import {DatabaseSync} from 'node:sqlite';
import {createApp} from '../apps/api/src/server.js';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';

const execFileAsync=promisify(execFile);
const projectId='sanro-ai-workforce';
const workerName='sanro-workforce-pilot';
const workspace='/home/sanro/.local/state/sanro-ai-workforce-herdr-pilot/workspace';
const stateDir='/home/sanro/.local/state/sanro-ai-workforce-herdr-pilot/state';
const queueDb=join(stateDir,'jobs.sqlite3');
const authRoot=mkdtempSync(join(tmpdir(),'sanro-herdr-pilot-auth-'));
const authPath=join(authRoot,'auth.json');
const token=randomBytes(32).toString('hex');
const approvalRef='owner-authorized-herdr-pilot-followup';
const scopes=['read','engineering:execute','engineering:read','engineering:cancel','worker:read','worker:manage'];
const config={version:1,projects:[{id:projectId,name:'SANRO AI Workforce pilot',workspace}],principals:[{
  subject:'owner-authorized-synthetic-pilot',token_sha256:createHash('sha256').update(token).digest('hex'),
  projects:{[projectId]:{workspace,scopes,approval_refs:[approvalRef]}}
}],approvals:{[approvalRef]:{project_id:projectId,subject:'owner-authorized-synthetic-pilot',status:'APPROVED',scopes:['engineering:execute'],expires_at:new Date(Date.now()+10*60_000).toISOString()}},
command_profiles:{visible:{command:['/usr/bin/printf','SANRO_HERDR_PILOT_OUTPUT\n'],projects:[projectId],approval_required:true}}};
writeFileSync(authPath,JSON.stringify(config),{mode:0o600});chmodSync(authPath,0o600);

const names=['WORKFORCE_WORKER_BACKEND','WORKFORCE_HERDR_PROJECT_ID','WORKFORCE_HERDR_MACHINE','WORKFORCE_HERDR_CORE_ENV_ATTESTED','WORKFORCE_HERDR_WORKER_NAME','WORKFORCE_WORKER_AUTOSTART'];
const prior=Object.fromEntries(names.map(name=>[name,process.env[name]]));
Object.assign(process.env,{WORKFORCE_WORKER_BACKEND:'herdr',WORKFORCE_HERDR_PROJECT_ID:projectId,WORKFORCE_HERDR_CORE_ENV_ATTESTED:'1',WORKFORCE_HERDR_WORKER_NAME:workerName});
delete process.env.WORKFORCE_HERDR_MACHINE;delete process.env.WORKFORCE_WORKER_AUTOSTART;
let app;
async function invoke(path,{method='GET',body}={}){
  const req=new EventEmitter();req.method=method;req.url=path;req.headers={authorization:`Bearer ${token}`,'content-type':'application/json'};
  process.nextTick(()=>{if(body!==undefined)req.emit('data',Buffer.from(JSON.stringify(body)));req.emit('end');});
  let status=0,output='';const res=new Writable({write(chunk,_encoding,callback){output+=chunk.toString();callback();}});res.writeHead=code=>{status=code;};
  await app.handler(req,res);return {status,data:JSON.parse(output||'{}')};
}
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
try{
  app=createApp({authPath,stateDir,allowWorkerControl:true});
  const core=JSON.parse((await execFileAsync('hc',['server','status','--json'])).stdout);
  if(core.version!=='0.1.22'||core.live!==1)throw new Error('existing pinned Herdr Core is not live or has unexpected version');
  const before=await app.workerController.snapshot();
  if(before.status!=='RUNNING'||before.session!=='t3'||before.worker_name!==workerName||before.project_id!==projectId)throw new Error('expected pilot t3 identity is not the sole active project worker');
  const detail=JSON.parse((await execFileAsync('hc',['get','--json','t3'])).stdout);
  if(detail.pid!==2933754||detail.state!=='live'||detail.name!==workerName||detail.labels?.['sanro.project_id']!==projectId||detail.labels?.['sanro.worker_name']!==workerName)throw new Error('pilot terminal/process identity changed');
  const db=new DatabaseSync(queueDb,{readOnly:true});
  const active=db.prepare("SELECT id,state FROM jobs WHERE state IN ('queued','running','cancel_requested')").all();db.close();
  if(active.length)throw new Error('pilot queue has an active job; refusing restart');
  const existing=await app.workerController.discover();
  if(existing.filter(t=>t.state==='live').length!==1)throw new Error('duplicate live Workforce Herdr terminal detected');

  // The owner authorized stopping/restarting this idle pilot only.
  const stopped=await app.stopWorker();
  if(!stopped.stopped||stopped.session!=='t3')throw new Error('pilot stop did not target the verified t3 session');
  const started=await app.workerController.start({projectId,workspace,scopes:new Set(['worker:manage'])});
  if(started.status!=='RUNNING'||started.worker_name!==workerName||started.project_id!==projectId)throw new Error('updated pilot did not start through the Workforce Herdr controller');
  let ready;
  for(let i=0;i<50;i++){ready=await app.workerController.snapshot();if(ready.status==='RUNNING'&&ready.session!==null)break;await sleep(100);}
  if(ready?.status!=='RUNNING')throw new Error('updated pilot terminal did not become live');
  const live=await app.workerController.discover();
  if(live.filter(t=>t.state==='live').length!==1)throw new Error('restart created duplicate live pilot terminals');
  const runtimeDetail=JSON.parse((await execFileAsync('hc',['get','--json',ready.session])).stdout);
  if(runtimeDetail.state!=='live'||runtimeDetail.pid===detail.pid||runtimeDetail.name!==workerName)throw new Error('new pilot process identity verification failed');
  const runtimeSource=await execFileAsync('sha256sum',[resolve(new URL('../worker.py',import.meta.url).pathname)]);

  const submitted=await invoke(`/api/projects/${projectId}/jobs`,{method:'POST',body:{profile:'visible',idempotency_key:`owner-pilot-${Date.now()}`,approval_ref:approvalRef,timeout:15}});
  if(submitted.status!==202||!/^[a-f0-9]{32}$/.test(submitted.data.job_id??''))throw new Error(`Workforce API rejected synthetic job (${submitted.status})`);
  const jobId=submitted.data.job_id;let job;
  for(let i=0;i<100;i++){const result=await invoke(`/api/projects/${projectId}/jobs/${jobId}`);job=result.data;if(job.status==='COMPLETED'||job.status==='FAILED')break;await sleep(100);}
  if(job?.status!=='COMPLETED'||job.exit_code!==0)throw new Error(`synthetic job did not complete successfully (${job?.status??'unknown'})`);
  const logs=await invoke(`/api/projects/${projectId}/jobs/${jobId}/logs`);
  if(logs.status!==200||!logs.data.logs.includes('SANRO_HERDR_PILOT_OUTPUT'))throw new Error('synthetic command output missing from Workforce job log');
  const finalSnapshot=await app.workerController.snapshot();
  const record=finalSnapshot.job_records?.find(item=>item.job_id===jobId);
  if(!record||record.status!=='done')throw new Error('Herdr Core has no done record for the synthetic job');
  const terminal=await app.workerController.output(200);
  if(!terminal.output.includes(`[SANRO] project=${projectId} worker=${workerName} job=${jobId} state=running`)||!terminal.output.includes(`[SANRO] project=${projectId} worker=${workerName} job=${jobId} state=completed`))throw new Error('visible terminal lifecycle text missing');
  const detailAfter=JSON.parse((await execFileAsync('hc',['get','--json',finalSnapshot.session])).stdout);
  if(detailAfter.records?.[jobId]?.state!=='done'||detailAfter.records?.[jobId]?.app!=='sanro-workforce'||detailAfter.reported!==true)throw new Error('official Herdr OSC 7501 completion record missing');
  const dbAfter=new DatabaseSync(queueDb,{readOnly:true});
  const lifecycle=dbAfter.prepare('SELECT state,started,finished,exit_code FROM jobs WHERE id=?').get(jobId);dbAfter.close();
  if(lifecycle?.state!=='succeeded'||!lifecycle.started||!lifecycle.finished||lifecycle.exit_code!==0)throw new Error('durable FIFO lifecycle record incomplete');

  console.log(JSON.stringify({result:'PASS_SYNTHETIC_RUNTIME',core_id:core.core.id,core_pid:core.pid,old_terminal:'t3',old_pid:detail.pid,new_terminal:finalSnapshot.session,new_pid:detailAfter.pid,worker_name:workerName,project_id:projectId,job_id:jobId,job_state:lifecycle.state,exit_code:lifecycle.exit_code,herdr_record:record.status,reported:detailAfter.reported,terminal_output:terminal.output,runtime_source_sha256:runtimeSource.stdout.trim().split(/\s+/)[0]}));
}finally{
  if(app?.store)app.store.close();
  for(const name of names){if(prior[name]===undefined)delete process.env[name];else process.env[name]=prior[name];}
  rmSync(authRoot,{recursive:true,force:true});
}
