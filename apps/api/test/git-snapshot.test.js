import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,rmSync,writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {execFileSync} from 'node:child_process';
import {gitSnapshot} from '../src/director.js';

test('real Git evidence enforces clean tree, configured repository and feature branch before execution',async t=>{
  const dir=mkdtempSync(join(tmpdir(),'workforce-git-fixture-'));t.after(()=>rmSync(dir,{recursive:true,force:true}));
  const git=(...args)=>execFileSync('git',['-C',dir,...args],{stdio:'pipe'}).toString().trim();
  git('init','-b','feature/synthetic');git('remote','add','origin','https://github.com/synthetic/pilot.git');
  writeFileSync(join(dir,'fixture.txt'),'synthetic only');git('add','fixture.txt');git('-c','user.name=Synthetic Fixture','-c','user.email=fixture@example.invalid','commit','-m','synthetic fixture');
  const project={repository:'synthetic/pilot',branch:'feature/synthetic'};
  assert.equal(await gitSnapshot(dir,project),git('rev-parse','HEAD'));
  await assert.rejects(gitSnapshot(dir,{...project,repository:'wrong/project'}),/repository or branch/);
  await assert.rejects(gitSnapshot(dir,{...project,branch:'main'}),/repository or branch/);
  writeFileSync(join(dir,'untracked.txt'),'must block');await assert.rejects(gitSnapshot(dir,project),/clean/);
});
