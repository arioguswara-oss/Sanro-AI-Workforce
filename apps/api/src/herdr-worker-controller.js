import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {createHash} from 'node:crypto';

const execFileAsync=promisify(execFile);
export const PINNED_HERDR_CORE_VERSION='0.1.22';

function parseJson(stdout,what){try{return JSON.parse(stdout);}catch{throw new Error(`Herdr ${what} returned invalid JSON`);}}
function terminalOf(value){return value?.terminal??value?.result?.terminal??value;}
function statusOf(terminal){
  if(!terminal)return {status:'STOPPED'};
  if(terminal.state==='live')return {status:'RUNNING',session:terminal.address??terminal.name??null,agent_status:terminal.status?.state??null};
  if(terminal.state==='finished'){
    const reason=terminal.reason??'';
    const status=reason==='killed'?'CANCELLED':reason==='holder_lost'||reason==='stopped_by_restart'||reason==='server_stop'?'INTERRUPTED':terminal.exit_code===0?'COMPLETED':'FAILED';
    return {status,session:terminal.address??terminal.name??null,exit_code:terminal.exit_code??null,reason};
  }
  return {status:'INTERRUPTED',session:terminal.address??terminal.name??null,reason:terminal.reason??'unknown'};
}
function projectIdentity(projectId,workerName){
  const slug=projectId.toLowerCase().replace(/[^a-z0-9_-]+/g,'-').replace(/[-_]{2,}/g,'-').replace(/^-|-$/g,'').slice(0,17)||'project';
  const tag=createHash('sha256').update(projectId).digest('hex').slice(0,8);
  if(workerName!==undefined&&workerName!==null&&!/^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$/.test(workerName))throw new TypeError('invalid workerName');
  return {name:workerName??`wf-${slug}-${tag}`.slice(0,32),tag};
}

/**
 * Optional Herdr view/supervisor for the existing serial Workforce worker.
 * It only starts the fixed Workforce queue consumer. Per-job FIFO, approval,
 * timeout, ACL, cancellation and recovery remain enforced by the existing API
 * and worker queue. This does not turn Herdr into a sandbox.
 */
export class HerdrWorkerController {
  constructor({projectId,workspace,stateDir,workerScript,hc='hc',python='python3',machine=null,
    coreEnvironmentAttested=false,requiredVersion=PINNED_HERDR_CORE_VERSION,runner=null,workerName=null}={}){
    if(!projectId||!workspace||!stateDir||!workerScript)throw new TypeError('projectId, workspace, stateDir and workerScript are required');
    if(!/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$/.test(projectId))throw new TypeError('invalid projectId');
    this.projectId=projectId;
    this.project=projectIdentity(projectId,workerName);
    this.workspace=resolve(workspace);this.stateDir=resolve(stateDir);this.workerScript=resolve(workerScript);
    if(machine!==null)throw new Error('remote Herdr machines are unsupported until Workforce queue and workspace are colocated');
    this.hc=hc;this.python=python;this.coreEnvironmentAttested=coreEnvironmentAttested;
    this.requiredVersion=requiredVersion;this.runner=runner??(async(args,timeout=8000)=>{
      const result=await execFileAsync(this.hc,args,{timeout,maxBuffer:1024*1024,windowsHide:true});
      return {stdout:result.stdout,stderr:result.stderr};
    });
    this.starting=null;this.address=null;this.startError=null;
  }
  async call(args,timeout){return this.runner(args,timeout);}
  async assertVersion(){
    const {stdout}=await this.call(['--version']);
    const match=stdout.match(/(?:herdr-core|hc)\s+(\d+\.\d+\.\d+)/i);
    if(!match||match[1]!==this.requiredVersion)throw new Error(`Herdr Core must be pinned at ${this.requiredVersion}`);
  }
  authorize(context){
    const scopes=context?.scopes instanceof Set?context.scopes:new Set(context?.scopes??[]);
    if(!scopes.has('worker:manage'))throw new Error('worker management scope required');
    if(context?.projectId!==undefined&&!/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$/.test(context.projectId))throw new Error('invalid project scope');
    if(context?.projectId!==this.projectId)throw new Error('cross-project worker access denied');
    if(context?.workspace!==undefined&&resolve(context.workspace)!==this.workspace)throw new Error('cross-workspace worker access denied');
  }
  async discover(){
    const {stdout}=await this.call(['ls','--all','--json','--label','sanro.workforce=jack-worker','--label',`sanro.project=${this.project.tag}`]);
    const payload=parseJson(stdout,'terminal list');
    const terminals=Array.isArray(payload)?payload:(payload.terminals??[]);
    const verified=[];
    for(const listed of terminals){
      const address=listed?.address??listed?.name;
      if(typeof address!=='string'||!address)continue;
      const detail=terminalOf(parseJson((await this.call(['get','--json',address])).stdout,'terminal detail'));
      if(detail?.labels?.['sanro.workforce']==='jack-worker'&&detail?.labels?.['sanro.project']===this.project.tag)verified.push(detail);
    }
    return verified;
  }
  async coreRunning(){
    await this.assertVersion();
    try{const {stdout}=await this.call(['server','status','--json']);const core=parseJson(stdout,'server status');return Number.isInteger(core.pid)&&core.pid>0;}
    catch(error){if(error?.code===1||error?.exitCode===1)return false;throw error;}
  }
  async start(context){
    this.authorize(context);
    if(!this.coreEnvironmentAttested)throw new Error('Herdr core environment is not attested for the isolated worker');
    if(this.starting)return this.starting;
    this.startError=null;
    this.starting=(async()=>{
      await this.assertVersion();
      const existing=await this.discover();
      const active=existing.find(t=>t.state==='live');
      if(active){this.address=active.address??active.name;return {started:false,status:'RUNNING',session:this.address};}
      const name=this.project.name;
      const args=['run','--bg','--json','--name',name,'--cwd',this.workspace,'--no-parent','--outlive-parent',
        '--label','sanro.workforce=jack-worker','--label',`sanro.project=${this.project.tag}`,'--label',`sanro.project_id=${this.projectId}`,
        '--label',`sanro.worker_name=${name}`,'--label','sanro.worker_role=serial-workforce-supervisor','--label','sanro.execution_engine=hermes','--label','sanro.queue=serial'];
      args.push('--','/usr/bin/env','-i','PATH=/usr/bin:/bin',`HOME=${this.workspace}`,`TMPDIR=${this.stateDir}/tmp`,'LANG=C.UTF-8','PYTHONNOUSERSITE=1','WORKFORCE_HERDR_STATUS=1',`WORKFORCE_HERDR_PROJECT_ID=${this.projectId}`,`WORKFORCE_HERDR_WORKER_NAME=${name}`,this.python,this.workerScript,'--root',this.stateDir,'serve');
      const {stdout}=await this.call(args,15000);
      const payload=parseJson(stdout,'worker start');
      this.address=payload.address??payload.terminal?.address??payload.name;
      if(typeof this.address!=='string'||!this.address)throw new Error('Herdr did not return a session address');
      return {started:true,status:'RUNNING',session:this.address,worker_name:name,project_id:this.projectId};
    })();
    try{return await this.starting;}catch(error){this.startError=error?.name??'startup failed';throw error;}finally{this.starting=null;}
  }
  async snapshot(){
    if(this.starting)return {status:'STARTING',backend:'herdr',worker_name:this.project.name,project_id:this.projectId};
    if(this.startError)return {status:'FAILED',backend:'herdr',worker_name:this.project.name,project_id:this.projectId,error:this.startError};
    if(!await this.coreRunning()){this.address=null;return {status:'STOPPED',backend:'herdr'};}
    const sessions=await this.discover();
    const live=sessions.find(t=>t.state==='live');
    const terminal=live??sessions.sort((a,b)=>(b.finished_ms??0)-(a.finished_ms??0))[0]??null;
    if(!terminal){this.address=null;return {status:'STOPPED',backend:'herdr',worker_name:this.project.name,project_id:this.projectId};}
    this.address=terminal.address??terminal.name??null;
    const statusRecords=terminal.records??terminal.status?.records??{};
    const jobRecords=Object.entries(statusRecords).filter(([jobId,record])=>/^[a-f0-9]{32}$/.test(jobId)&&record?.app==='sanro-workforce').map(([jobId,record])=>({job_id:jobId,status:record.state??'unknown',title:typeof record.title==='string'?record.title:null}));
    return {...statusOf(terminal),backend:'herdr',worker_name:this.project.name,project_id:this.projectId,job_records:jobRecords};
  }
  async output(lines=100){
    if(!Number.isInteger(lines)||lines<1||lines>1000)throw new RangeError('lines must be 1..1000');
    const snapshot=await this.snapshot();if(!snapshot.session)return {status:snapshot.status,output:''};
    const {stdout}=await this.call(['read','--json','--lines',String(lines),snapshot.session]);
    const payload=parseJson(stdout,'terminal read');return {status:snapshot.status,output:String(payload.text??'').slice(-256*1024)};
  }
  async shutdown(context){
    this.authorize(context);
    const snapshot=await this.snapshot();if(!snapshot.session||snapshot.status!=='RUNNING')return {stopped:false,status:snapshot.status};
    const {stdout}=await this.call(['kill','--json',snapshot.session],10000);
    const terminal=terminalOf(parseJson(stdout,'terminal kill'));
    return {stopped:true,...statusOf(terminal),session:snapshot.session};
  }
}
