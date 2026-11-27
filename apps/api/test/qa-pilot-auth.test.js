import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,chmodSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {loadAuth} from '../src/auth.js';
import {SANRO_QA_PILOT,SANRO_QA_PILOT_PERMISSION_PROFILE} from '../src/sanro-qa-pilot-binding.js';

function fixture(t,projectUpdate={},profileUpdate={}){
  const root=mkdtempSync(join(tmpdir(),'sanro-qa-pilot-auth-'));
  const project={id:SANRO_QA_PILOT.project_id,name:'SANRO Browser QA pilot',workspace:SANRO_QA_PILOT.workspace,
    repository:SANRO_QA_PILOT.repository,branch:SANRO_QA_PILOT.branch,source_sha:SANRO_QA_PILOT.source_sha,
    worker_id:SANRO_QA_PILOT.worker_id,mainline_qa_only:true,environment:'isolated-development',
    permission_profile:{...SANRO_QA_PILOT_PERMISSION_PROFILE},...projectUpdate};
  const profile={command:['/usr/bin/true'],projects:[SANRO_QA_PILOT.project_id],executor:'local-ci',role:'qa',
    runtime_operation:SANRO_QA_PILOT.operation,runtime_timeout_seconds:120,...profileUpdate};
  const token='synthetic-owner-token-000000000000';
  const path=join(root,'auth.json');
  writeFileSync(path,JSON.stringify({version:1,projects:[project],principals:[{subject:'owner:synthetic',
    token_sha256:createHash('sha256').update(token).digest('hex'),projects:{[project.id]:{workspace:project.workspace,
      scopes:['read','runtime:browser'],approval_refs:[SANRO_QA_PILOT.approval_id]}}}],
    approvals:{[SANRO_QA_PILOT.approval_id]:{id:SANRO_QA_PILOT.approval_id,project_id:project.id,subject:'owner:synthetic',owner_actor:'owner:synthetic',status:'APPROVED',
      repository:project.repository,branch:project.branch,environment:project.environment,max_cost_usd:0,scopes:['runtime:browser'],
      allowed_actions:['qa:execute','runtime:browser'],forbidden_actions:['engineering:execute','git:write','worker:manage','ssh:staging','merge','production:deploy','paid-api','other-repository:write'],
      expires_at:SANRO_QA_PILOT.expires_at}},
    command_profiles:{sanro_qa_browser:profile}}),{mode:0o600});
  chmodSync(path,0o600);t.after(()=>rmSync(root,{recursive:true,force:true}));return path;
}

test('loads the pinned read-only pilot binding and fixed Local CI QA profile',t=>{
  const auth=loadAuth(fixture(t));
  const project=auth.projects.get(SANRO_QA_PILOT.project_id);
  assert.equal(project.worker_id,'sanro-qa');
  assert.equal(project.source_sha,SANRO_QA_PILOT.source_sha);
  assert.equal(project.permission_profile.read_only,true);
  assert.deepEqual(auth.profiles.sanro_qa_browser.projects,['sanro-browser-qa']);
});

test('rejects any change to pinned repo, workspace, branch, SHA, worker or permission scope',t=>{
  for(const update of [
    {worker_id:'other-worker'},
    {branch:'feature/not-main'},
    {source_sha:'f'.repeat(40)},
    {repository:'other/repo'},
    {permission_profile:{version:1,read_only:false,write_scope:'project-worktree',allow_network:false,allow_process_creation:false}},
    {workspace:'/tmp'},
  ])assert.throws(()=>loadAuth(fixture(t,update)),/pinned read-only project identity/);
});

test('pilot cannot receive an engineering or unrelated profile',t=>{
  assert.throws(()=>loadAuth(fixture(t,{}, {runtime_operation:'browser_smoke'})),/exactly one fixed read-only QA runtime profile/);
});
