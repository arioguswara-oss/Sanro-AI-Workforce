import test from 'node:test';
import assert from 'node:assert/strict';
import {HerdrWorkerController,PINNED_HERDR_CORE_VERSION} from '../src/herdr-worker-controller.js';

const config={workspace:'/srv/sanro/workforce/project-a',stateDir:'/srv/sanro/workforce/state',workerScript:'/srv/sanro/workforce/worker.py',projectId:'studio-dev',coreEnvironmentAttested:true};
const authorized={projectId:'studio-dev',scopes:new Set(['worker:manage'])};
const version=`herdr-core ${PINNED_HERDR_CORE_VERSION}\n`;

test('Herdr controller denies unauthorized start and refuses an unattested core',async()=>{
  const calls=[];const runner=async args=>{calls.push(args);return {stdout:args[0]==='--version'?version:'{"terminals":[]}'};};
  const controller=new HerdrWorkerController({...config,runner});
  await assert.rejects(controller.start({projectId:'studio-dev',scopes:[]}),/worker management scope/);
  await assert.rejects(new HerdrWorkerController({...config,coreEnvironmentAttested:false,runner}).start(authorized),/not attested/);
  assert.equal(calls.length,0);
});

test('Herdr starts only the fixed serial local Workforce queue consumer using argv, never a request command',async()=>{
  const calls=[];const runner=async args=>{calls.push(args);if(args[0]==='--version')return {stdout:version};if(args[0]==='ls')return {stdout:'{"terminals":[]}'};return {stdout:'{"address":"vps/t7"}'};};
  const controller=new HerdrWorkerController({...config,runner});
  const result=await controller.start(authorized);
  assert.deepEqual(result,{started:true,status:'RUNNING',session:'vps/t7',worker_name:controller.project.name,project_id:config.projectId});
  const args=calls[2];assert.equal(args[0],'run');assert.ok(args.includes('--bg'));assert.ok(args.includes('--no-parent'));assert.equal(args.includes('--on'),false);
  assert.equal(args[args.indexOf('--name')+1],controller.project.name);
  assert.ok(args.includes(`sanro.project=${controller.project.tag}`));
  assert.ok(args.includes(`sanro.project_id=${config.projectId}`));
  assert.ok(args.includes(`sanro.worker_name=${controller.project.name}`));
  assert.ok(args.includes('sanro.execution_engine=hermes'));
  assert.ok(controller.project.name.length<=32);
  assert.deepEqual(args.slice(args.indexOf('--')+1),['/usr/bin/env','-i','PATH=/usr/bin:/bin',`HOME=${config.workspace}`,`TMPDIR=${config.stateDir}/tmp`,'LANG=C.UTF-8','PYTHONNOUSERSITE=1','WORKFORCE_HERDR_STATUS=1',`WORKFORCE_HERDR_PROJECT_ID=${config.projectId}`,`WORKFORCE_HERDR_WORKER_NAME=${controller.project.name}`,'python3',config.workerScript,'--root',config.stateDir,'serve']);
  assert.equal(args.some(x=>x.includes('shell;')||x.includes('$(id)')),false);
});

test('remote Herdr machine is rejected until the durable Workforce queue can be colocated',()=>{
  assert.throws(()=>new HerdrWorkerController({...config,machine:'remote-vps'}),/remote Herdr machines are unsupported/);
});

test('existing project worker is reused instead of creating a duplicate session',async()=>{
  let starts=0;const runner=async args=>{
    if(args[0]==='--version')return {stdout:version};
    if(args[0]==='ls')return {stdout:JSON.stringify({terminals:[
      {address:'vps/t8',state:'live',labels:{'sanro.workforce':'jack-worker','sanro.project':'other1234'}},
      {address:'vps/t9',state:'live',labels:{'sanro.workforce':'jack-worker','sanro.project':new HerdrWorkerController({...config,runner}).project.tag}},
    ]})};
    starts++;return {stdout:'{}'};
  };
  const controller=new HerdrWorkerController({...config,runner});
  assert.deepEqual(await controller.start(authorized),{started:false,status:'RUNNING',session:'vps/t9'});
  assert.equal(starts,0);
});

test('status, output and cancellation use verified Herdr CLI surfaces',async()=>{
  const projectTag=new HerdrWorkerController(config).project.tag;
  let state='live';const calls=[];const runner=async args=>{
    calls.push(args);
    if(args[0]==='--version')return {stdout:version};
    if(args[0]==='server')return {stdout:'{"pid":123}'};
    if(args[0]==='ls')return {stdout:JSON.stringify({terminals:[{address:'t7',name:new HerdrWorkerController(config).project.name,state,labels:{'sanro.workforce':'jack-worker','sanro.project':projectTag},status:{state:'working'},records:{'0123456789abcdef0123456789abcdef':{state:'done',app:'sanro-workforce',title:'synthetic job record'}}}]})};
    if(args[0]==='read')return {stdout:JSON.stringify({text:'worker synthetic output',complete:true,how:'history'})};
    if(args[0]==='kill'){state='finished';return {stdout:JSON.stringify({terminal:{address:'t7',state,reason:'killed',exit_code:null}})};}
    throw new Error('unexpected command');
  };
  const controller=new HerdrWorkerController({...config,runner});
  const snapshot=await controller.snapshot();assert.equal(snapshot.status,'RUNNING');
  assert.deepEqual(snapshot.job_records,[{job_id:'0123456789abcdef0123456789abcdef',status:'done',title:'synthetic job record'}]);
  assert.equal((await controller.output(20)).output,'worker synthetic output');
  assert.deepEqual(await controller.shutdown(authorized),{stopped:true,status:'CANCELLED',session:'t7',exit_code:null,reason:'killed'});
  assert.ok(calls.some(a=>a[0]==='get')===false);
  assert.ok(calls.some(a=>a[0]==='read'));
  assert.ok(calls.some(a=>a[0]==='kill'));
});

test('finished or lost Herdr session stays stopped/interrupted and is never auto-replayed',async()=>{
  const projectTag=new HerdrWorkerController(config).project.tag;
  let terminal={address:'t9',state:'finished',finished_ms:3,reason:'stopped_by_restart',labels:{'sanro.workforce':'jack-worker','sanro.project':projectTag}};
  const runner=async args=>args[0]==='--version'?{stdout:version}:args[0]==='server'?{stdout:'{"pid":123}'}:{stdout:JSON.stringify({terminals:[terminal]})};
  const controller=new HerdrWorkerController({...config,runner});
  assert.equal((await controller.snapshot()).status,'INTERRUPTED');
  terminal={address:'t10',state:'finished',finished_ms:4,reason:'exited',exit_code:0,labels:{'sanro.workforce':'jack-worker','sanro.project':projectTag}};
  assert.equal((await controller.snapshot()).status,'COMPLETED');
});

test('read-only status does not auto-start an absent Herdr Core',async()=>{
  const calls=[];const runner=async args=>{calls.push(args);if(args[0]==='--version')return {stdout:version};if(args[0]==='server')return {stdout:'{"pid":0}'};throw new Error('terminal listing must not start the core');};
  const controller=new HerdrWorkerController({...config,runner});
  assert.deepEqual(await controller.snapshot(),{status:'STOPPED',backend:'herdr'});
  assert.equal(calls.some(args=>args[0]==='ls'),false);
});

test('wrong project scope and excessive output request are rejected',async()=>{
  const controller=new HerdrWorkerController({...config,runner:async()=>({stdout:'{"terminals":[]}'})});
  await assert.rejects(controller.start({...authorized,projectId:'other-project'}),/cross-project worker access denied/);
  await assert.rejects(controller.start({...authorized,workspace:'/srv/sanro/other'}),/cross-workspace worker access denied/);
  await assert.rejects(controller.output(1001),/lines must be/);
});
