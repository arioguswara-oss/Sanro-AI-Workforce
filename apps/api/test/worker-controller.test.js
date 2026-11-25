import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {WorkerController} from '../src/worker-controller.js';

test('worker controller starts one isolated process and shuts it down cleanly',async t=>{
  const root=mkdtempSync(join(tmpdir(),'workforce-worker-control-'));t.after(()=>rmSync(root,{recursive:true,force:true}));
  const controller=new WorkerController(root);assert.equal(controller.status(),'STOPPED');assert.equal(controller.start(),true);
  await new Promise(resolve=>setTimeout(resolve,150));
  assert.equal(controller.status(),'RUNNING','worker process must survive startup');assert.equal(controller.start(),false);assert.equal(await controller.shutdown(),true);assert.equal(controller.status(),'STOPPED');
});
