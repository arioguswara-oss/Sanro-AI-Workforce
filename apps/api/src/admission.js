import {lstatSync} from 'node:fs';
import {isAbsolute,parse,resolve,join,sep} from 'node:path';
import {gitSnapshot} from './director.js';
import {SANRO_QA_PILOT,isSanroQaPilotRuntime,hasSanroQaPilotPermissionProfile} from './sanro-qa-pilot-binding.js';

const safeId=/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
const sha=/^[a-f0-9]{40}(?:[a-f0-9]{24})?$/i;
const requiredAllowed=['engineering:execute','qa:execute'];
const requiredForbidden=['merge','production:deploy','paid-api','other-repository:write'];

export function canonicalWorkspace(path){
  if(typeof path!=='string'||!isAbsolute(path)||path.split(sep).includes('..'))throw Object.assign(new Error('workspace path must be absolute and traversal-free'),{status:403});
  const absolute=resolve(path),root=parse(absolute).root;let cursor=root;
  for(const part of absolute.slice(root.length).split(sep).filter(Boolean)){
    cursor=join(cursor,part);const entry=lstatSync(cursor);
    if(entry.isSymbolicLink())throw Object.assign(new Error('workspace path contains a symlink'),{status:403});
  }
  return absolute;
}

export async function validateJobAdmission({auth,principal,project,request,mandate,commandProfile}){
  const registered=auth.projects.get(project.id),workerId=registered?.worker_id;
  if(!registered||registered.workspace!==project.workspace||auth.workspaceRegistry?.get(registered.workspace)!==project.id||!safeId.test(project.id)||!safeId.test(workerId??''))throw Object.assign(new Error('project or worker identity is not registered'),{status:403});
  const workspace=canonicalWorkspace(registered.workspace);
  const profile=registered.permission_profile;
  const pilotQa=isSanroQaPilotRuntime(registered,request,commandProfile);
  const normalProfile=profile?.version===1&&profile.read_only===false&&profile.write_scope==='project-worktree'&&profile.allow_network===false&&profile.allow_process_creation===false;
  const pilotProfile=pilotQa&&hasSanroQaPilotPermissionProfile(profile)&&registered.mainline_qa_only===true;
  if(!normalProfile&&!pilotProfile)throw Object.assign(new Error('project permission profile is not eligible for this operation'),{status:403});
  const branchValid=registered.branch&&!['main','master'].includes(registered.branch)||pilotProfile;
  if(!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(registered.repository??'')||!branchValid||registered.environment!=='isolated-development')throw Object.assign(new Error('project repository branch mandate is invalid'),{status:403});
  const allowed=pilotProfile?['qa:execute',SANRO_QA_PILOT.scope]:requiredAllowed;
  const forbidden=pilotProfile?[...requiredForbidden,'engineering:execute','git:write','worker:manage','ssh:staging']:requiredForbidden;
  if(!mandate||mandate.status!=='APPROVED'||mandate.project_id!==registered.id||mandate.repository!==registered.repository||mandate.branch!==registered.branch||mandate.environment!=='isolated-development'||mandate.owner_actor!==principal.subject||mandate.max_cost_usd!==0||!Number.isFinite(Date.parse(mandate.expires_at))||Date.parse(mandate.expires_at)<=Date.now()||!allowed.every(x=>mandate.allowed_actions?.includes(x))||!forbidden.every(x=>mandate.forbidden_actions?.includes(x)))throw Object.assign(new Error('active project mandate is invalid or expired'),{status:403});
  if(pilotProfile&&(mandate.id!==SANRO_QA_PILOT.approval_id||mandate.expires_at!==SANRO_QA_PILOT.expires_at||mandate.scopes?.includes('engineering:execute')||mandate.allowed_actions?.length!==2||!['qa:execute',SANRO_QA_PILOT.scope].every(x=>mandate.allowed_actions?.includes(x))))throw Object.assign(new Error('SANRO QA pilot Owner mandate binding is invalid'),{status:403});
  if(commandProfile?.executor==='codex'&&!request.instruction)throw Object.assign(new Error('Codex admission requires a checkpoint-bound Director instruction'),{status:400});
  const approvalRef=request.approval_ref,grants=principal.projects?.[registered.id];
  const requiredScope=pilotProfile?SANRO_QA_PILOT.scope:'engineering:execute';
  if(!grants?.scopes?.includes(requiredScope)||!grants.approval_refs?.includes(approvalRef)||!mandate.scopes?.includes(requiredScope))throw Object.assign(new Error('mandate approval is not bound to this principal'),{status:403});
  const currentSha=await gitSnapshot(workspace,{repository:registered.repository,branch:registered.branch});
  let instruction=null;
  if(request.instruction){try{instruction=JSON.parse(request.instruction);}catch{throw Object.assign(new Error('job instruction is invalid'),{status:400});}}
  if(instruction&&(instruction.project_id!==registered.id||!safeId.test(instruction.run_id??'')||instruction.executor!==commandProfile?.executor||!sha.test(instruction.baseline_sha??'')||instruction.baseline_sha!==currentSha||(instruction.candidate_sha&&instruction.candidate_sha!==currentSha)))throw Object.assign(new Error('job instruction checkpoint does not match the authorized workspace'),{status:409});
  if(pilotProfile&&currentSha!==SANRO_QA_PILOT.source_sha)throw Object.assign(new Error('SANRO QA pilot source SHA differs from the approved pin'),{status:409});
  if(instruction){const expected=instruction.executor==='codex'?['engineering']:instruction.executor==='local-ci'?['local_ci']:null;if(!expected||!Array.isArray(instruction.required_capabilities)||instruction.required_capabilities.length!==expected.length||!expected.every(cap=>instruction.required_capabilities.includes(cap)))throw Object.assign(new Error('job capability requirements do not match the authorized executor'),{status:403});}
  const idempotencyKey=request.idempotency_key;
  if(typeof idempotencyKey!=='string'||idempotencyKey.length<8||idempotencyKey.length>200)throw Object.assign(new Error('job idempotency identity is invalid'),{status:400});
  return {project_id:registered.id,repository:registered.repository,branch:registered.branch,environment:registered.environment,workspace,worker_id:workerId,job_id:instruction?.run_id??idempotencyKey,checkpoint_sha:instruction?.baseline_sha??currentSha,required_capabilities:instruction?.required_capabilities??[],command_profile:commandProfile?.executor??'local',permission_profile:{version:profile.version,read_only:profile.read_only,write_scope:profile.write_scope,allow_network:profile.allow_network,allow_process_creation:profile.allow_process_creation},mandate_expires_at:mandate.expires_at,validated_at:new Date().toISOString()};
}
