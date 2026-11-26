import {open,readFile,unlink} from 'node:fs/promises';
import {createHash,randomUUID} from 'node:crypto';
import {join} from 'node:path';

const keyFor=workspace=>createHash('sha256').update(workspace).digest('hex');

// Advisory project lock in the private Workforce state directory. Existing locks fail closed.
export async function acquireWorktreeLock(stateDir,workspace,jobId){
  const path=join(stateDir,'locks',`${keyFor(workspace)}.lock`),token=randomUUID();
  const {mkdir}=await import('node:fs/promises');await mkdir(join(stateDir,'locks'),{recursive:true,mode:0o700});
  let handle;
  try{handle=await open(path,'wx',0o600);}catch(error){if(error.code==='EEXIST')throw new Error('project worktree is already locked');throw error;}
  await handle.writeFile(JSON.stringify({pid:process.pid,job_id:jobId,token,created_at:new Date().toISOString()}));await handle.close();
  let released=false;
  return {path,release:async()=>{if(released)return;released=true;try{const record=JSON.parse(await readFile(path,'utf8'));if(record.token===token)await unlink(path);}catch(error){if(error.code!=='ENOENT')throw error;}}};
}
