import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,symlinkSync,rmSync,writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {execFileSync} from 'node:child_process';
import {canonicalWorkspace,validateJobAdmission} from '../src/admission.js';

function fixture(t){
  const root=mkdtempSync(join(tmpdir(),'workforce-admission-')),workspace=join(root,'project');
  execFileSync('git',['init','--quiet',workspace]);execFileSync('git',['-C',workspace,'checkout','--quiet','-b','feature/test']);execFileSync('git',['-C',workspace,'config','user.name','Synthetic Owner']);execFileSync('git',['-C',workspace,'config','user.email','owner@example.invalid']);execFileSync('git',['-C',workspace,'remote','add','origin','https://github.com/synthetic/project-a.git']);execFileSync('git',['-C',workspace,'commit','--quiet','--allow-empty','-m','baseline']);
  const sha=execFileSync('git',['-C',workspace,'rev-parse','HEAD'],{encoding:'utf8'}).trim();
  const project={id:'project-a',workspace,repository:'synthetic/project-a',branch:'feature/test',environment:'isolated-development',worker_id:'worker-a',permission_profile:{version:1,read_only:false,allow_network:false,allow_process_creation:false,write_scope:'project-worktree'}};
  const principal={subject:'owner',projects:{'project-a':{scopes:['engineering:execute'],approval_refs:['approval-a']}}};
  const mandate={status:'APPROVED',project_id:'project-a',repository:project.repository,branch:project.branch,environment:project.environment,owner_actor:'owner',max_cost_usd:0,allowed_actions:['engineering:execute','qa:execute'],forbidden_actions:['merge','production:deploy','paid-api','other-repository:write'],scopes:['engineering:execute'],expires_at:new Date(Date.now()+60_000).toISOString()};
  const auth={projects:new Map([[project.id,project]]),workspaceRegistry:new Map([[workspace,project.id]])};
  const request={action:'submit',profile:'dev',approval_ref:'approval-a',idempotency_key:'synthetic-job-01',instruction:JSON.stringify({project_id:project.id,run_id:'run-synthetic-1',executor:'codex',baseline_sha:sha})};
  t.after(()=>rmSync(root,{recursive:true,force:true}));
  return {root,workspace,sha,project,principal,mandate,auth,request,commandProfile:{executor:'codex',projects:['project-a']}};
}

test('job admission binds registry, mandate, worker, branch, repository and checkpoint',async t=>{
  const f=fixture(t),admission=await validateJobAdmission(f);
  assert.deepEqual({project_id:admission.project_id,repository:admission.repository,branch:admission.branch,worker_id:admission.worker_id,job_id:admission.job_id,checkpoint_sha:admission.checkpoint_sha},{project_id:'project-a',repository:'synthetic/project-a',branch:'feature/test',worker_id:'worker-a',job_id:'run-synthetic-1',checkpoint_sha:f.sha});
});

test('admission rejects expired, mismatched, unauthorized, dirty and stale-checkpoint jobs',async t=>{
  const f=fixture(t);
  await assert.rejects(validateJobAdmission({...f,mandate:{...f.mandate,expires_at:new Date(Date.now()-1000).toISOString()}}),/invalid or expired/);
  await assert.rejects(validateJobAdmission({...f,mandate:{...f.mandate,repository:'other/repository'}}),/invalid or expired/);
  await assert.rejects(validateJobAdmission({...f,principal:{...f.principal,projects:{'project-a':{scopes:[],approval_refs:[]}}}}),/not bound/);
  await assert.rejects(validateJobAdmission({...f,request:{...f.request,instruction:JSON.stringify({project_id:'project-a',run_id:'run-synthetic-1',executor:'codex',baseline_sha:'f'.repeat(40)})}}),/checkpoint/);
  writeFileSync(join(f.workspace,'untracked.txt'),'dirty');
  await assert.rejects(validateJobAdmission(f),/worktree clean/);
});

test('workspace registry rejects symlinks and traversal paths',t=>{
  const f=fixture(t),link=join(f.root,'workspace-link');symlinkSync(f.workspace,link);
  assert.throws(()=>canonicalWorkspace(link),/symlink/);
  assert.throws(()=>canonicalWorkspace(`${f.root}/../outside`),/traversal/);
});
