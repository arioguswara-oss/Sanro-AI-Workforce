import {spawn} from 'node:child_process';
import {join,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const repoRoot=resolve(fileURLToPath(new URL('../../../',import.meta.url)));
export class WorkerController {
  constructor(stateDir,{python='python3',workerScript=join(repoRoot,'worker.py')}={}){this.stateDir=resolve(stateDir);this.python=python;this.workerScript=workerScript;this.process=null;}
  status(){return this.process&&this.process.exitCode===null&&this.process.signalCode===null?'RUNNING':'STOPPED';}
  start(){if(this.status()==='RUNNING')return false;const env={PATH:'/usr/bin:/bin',HOME:this.stateDir,TMPDIR:join(this.stateDir,'tmp'),LANG:'C.UTF-8',PYTHONNOUSERSITE:'1'};this.process=spawn(this.python,[this.workerScript,'--root',this.stateDir,'serve'],{cwd:repoRoot,env,stdio:'ignore',detached:true});this.process.on('error',()=>{});return true;}
  async shutdown(timeoutMs=5000){if(this.status()!=='RUNNING')return true;const child=this.process;try{process.kill(-child.pid,'SIGTERM');}catch{return true;}
    const stopped=child.exitCode!==null||child.signalCode!==null?Promise.resolve(true):new Promise(resolve=>child.once('exit',()=>resolve(true)));
    let timer;const result=await Promise.race([stopped,new Promise(resolve=>{timer=setTimeout(()=>resolve(false),timeoutMs);})]);clearTimeout(timer);
    if(result)return true;try{process.kill(-child.pid,'SIGKILL');}catch{}if(child.exitCode===null&&child.signalCode===null)await new Promise(resolve=>child.once('exit',resolve));return false;
  }
}
