import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {acquireWorktreeLock} from '../src/worktree-lock.js';

test('worktree lock excludes concurrent jobs and releases only its own token',async()=>{
  const root=await mkdtemp(join(tmpdir(),'wf-lock-')),state=join(root,'state'),workspace=join(root,'workspace');
  await mkdir(state);await mkdir(workspace);
  try{
    const first=await acquireWorktreeLock(state,workspace,'job-a');
    await assert.rejects(acquireWorktreeLock(state,workspace,'job-b'),/already locked/);
    await first.release();
    const second=await acquireWorktreeLock(state,workspace,'job-b');
    await second.release();
  }finally{await rm(root,{recursive:true,force:true});}
});
