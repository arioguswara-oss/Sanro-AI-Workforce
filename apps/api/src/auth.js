import {createHash,timingSafeEqual} from 'node:crypto';
import {realpathSync,readFileSync,lstatSync,statSync} from 'node:fs';
import {isAbsolute,parse,resolve,join,sep} from 'node:path';
import {SANRO_QA_PILOT,hasSanroQaPilotPermissionProfile} from './sanro-qa-pilot-binding.js';

const hash = value => createHash('sha256').update(value).digest();
function canonicalWorkspace(path){
  if(typeof path!=='string'||!isAbsolute(path)||path.split(sep).includes('..'))throw new Error('workspace must be absolute and traversal-free');
  const absolute=resolve(path),root=parse(absolute).root;let cursor=root;
  for(const part of absolute.slice(root.length).split(sep).filter(Boolean)){cursor=join(cursor,part);if(lstatSync(cursor).isSymbolicLink())throw new Error('workspace path cannot contain symlinks');}
  const canonical=realpathSync(absolute);if(canonical!==absolute)throw new Error('workspace must use its canonical path');return canonical;
}
export function loadAuth(path) {
  if (!path) throw new Error('WORKFORCE_AUTH_FILE is required; authorization is deny-by-default');
  const fileStat=lstatSync(path);if(fileStat.isSymbolicLink()||!fileStat.isFile()||fileStat.uid!==process.getuid()||(fileStat.mode&0o077)!==0)throw new Error('authorization file must be a real file owned by current user with mode 0600');
  const config = JSON.parse(readFileSync(path,'utf8'));
  if (config.version !== 1 || !Array.isArray(config.principals) || !Array.isArray(config.projects)) throw new Error('invalid authorization file schema');
  const principals = new Map();
  for (const p of config.principals) {
    if (!/^[a-f0-9]{64}$/.test(p.token_sha256) || !p.subject || !p.projects || typeof p.projects !== 'object') throw new Error('invalid principal entry');
    for(const grant of Object.values(p.projects)){
      if(!grant||!Array.isArray(grant.scopes))throw new Error('invalid project scopes');
      if(grant.scopes.includes('monitor:read')&&grant.scopes.some(scope=>scope!=='monitor:read'))throw new Error('monitor credentials must have dedicated read-only scope');
    }
    if(Object.values(p.projects).some(g=>g.scopes.includes('monitor:read'))&&Object.values(p.projects).some(g=>g.scopes.some(s=>s!=='monitor:read')))throw new Error('monitor credentials cannot carry operational grants');
    principals.set(p.token_sha256,p);
  }
  const projects = new Map(), workspaceOwners = new Map();
  for (const p of config.projects) {
    if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$/.test(p.id) || !p.name || !p.workspace) throw new Error('invalid project entry');
    const workspace = canonicalWorkspace(p.workspace);
    const wsStat=statSync(workspace);if(!wsStat.isDirectory())throw new Error('project workspace must be a directory');
    if(workspaceOwners.has(workspace))throw new Error('workspace is already registered to another project');
    const permissionProfile=p.permission_profile??{version:1,read_only:false,allow_network:false,allow_process_creation:false,write_scope:'project-worktree'};
    const validWriteScope=permissionProfile?.read_only===true?permissionProfile.write_scope==='none':permissionProfile?.write_scope==='project-worktree';
    if(!permissionProfile||permissionProfile.version!==1||typeof permissionProfile.read_only!=='boolean'||typeof permissionProfile.allow_network!=='boolean'||typeof permissionProfile.allow_process_creation!=='boolean'||!validWriteScope)throw new Error('invalid project permission profile');
    workspaceOwners.set(workspace,p.id);
    const worker_id=p.worker_id??`workforce-${p.id}`;
    if(!/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(worker_id))throw new Error('invalid project worker id');
    let drive_delivery=null;
    if(p.drive_delivery!==undefined){
      const mapping=p.drive_delivery;
      if(!mapping||mapping.project_id!==p.id||typeof mapping.account_id!=='string'||!/^[A-Za-z0-9._@-]{3,160}$/.test(mapping.account_id)||typeof mapping.folder_id!=='string'||!/^[A-Za-z0-9_-]{8,200}$/.test(mapping.folder_id)||mapping.visibility!=='private')throw new Error('invalid project-scoped private Drive mapping');
      drive_delivery={...mapping};
    }
    if(p.repository!==undefined&&!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(p.repository))throw new Error('invalid project repository identity');
    if(p.branch!==undefined&&(!/^[A-Za-z0-9._/-]{1,120}$/.test(p.branch)||p.branch.includes('..')||p.branch.startsWith('-')))throw new Error('invalid project branch identity');
    if(p.id===SANRO_QA_PILOT.project_id){
      if(p.repository!==SANRO_QA_PILOT.repository||workspace!==SANRO_QA_PILOT.workspace||p.branch!==SANRO_QA_PILOT.branch||p.source_sha!==SANRO_QA_PILOT.source_sha||worker_id!==SANRO_QA_PILOT.worker_id||p.mainline_qa_only!==true||!hasSanroQaPilotPermissionProfile(permissionProfile))throw new Error('SANRO QA pilot binding must match the pinned read-only project identity');
    }else if(p.mainline_qa_only!==undefined)throw new Error('mainline QA exception is reserved for the pinned SANRO QA pilot');
    projects.set(p.id,{...p,workspace,worker_id,permission_profile:permissionProfile,...(drive_delivery?{drive_delivery}:{})});
  }
  const profiles=config.command_profiles??{},approvals=config.approvals??{};
  if(!profiles||typeof profiles!=='object'||Array.isArray(profiles)||!approvals||typeof approvals!=='object'||Array.isArray(approvals))throw new Error('invalid profile or approval registry');
  const shells=new Set(['sh','bash','dash','zsh','fish','cmd','powershell']);
  for(const [id,p] of Object.entries(profiles)){
    if(!/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$/.test(id)||!p||!Array.isArray(p.projects)||!p.projects.every(projectId=>projects.has(projectId))||!Array.isArray(p.command)||!p.command.length||!p.command.every(arg=>typeof arg==='string'&&arg.length>0)||shells.has(p.command[0].split('/').pop()))throw new Error('invalid or unauthorized command profile');
    if(p.runtime_operation!==undefined&&(!['browser_smoke','private_browser_acceptance','mariadb_synthetic'].includes(p.runtime_operation)||p.executor!=='local-ci'||p.role!=='qa'||p.command.length!==1||p.command[0]!=='/usr/bin/true'||!Number.isInteger(p.runtime_timeout_seconds??120)||(p.runtime_timeout_seconds??120)<1||(p.runtime_timeout_seconds??120)>300))throw new Error('invalid fixed project runtime profile');
  }
  const pilot=projects.get(SANRO_QA_PILOT.project_id);
  if(pilot){
    const pilotProfiles=Object.values(profiles).filter(profile=>profile.projects.includes(SANRO_QA_PILOT.project_id));
    if(pilotProfiles.length!==1||pilotProfiles[0].projects.length!==1||pilotProfiles[0].executor!=='local-ci'||pilotProfiles[0].role!=='qa'||pilotProfiles[0].runtime_operation!==SANRO_QA_PILOT.operation)throw new Error('SANRO QA pilot requires exactly one fixed read-only QA runtime profile');
    const grants=[...principals.values()].map(principal=>({principal,grant:principal.projects[SANRO_QA_PILOT.project_id]})).filter(x=>x.grant);
    if(grants.length!==1||grants[0].grant.scopes.length!==2||!['read',SANRO_QA_PILOT.scope].every(scope=>grants[0].grant.scopes.includes(scope))||grants[0].grant.approval_refs.length!==1||grants[0].grant.approval_refs[0]!==SANRO_QA_PILOT.approval_id)throw new Error('SANRO QA pilot requires one least-privilege Owner project grant');
    const approval=approvals[SANRO_QA_PILOT.approval_id],allowed=['qa:execute',SANRO_QA_PILOT.scope];
    const denied=['engineering:execute','git:write','worker:manage','ssh:staging','merge','production:deploy','paid-api','other-repository:write'];
    if(!approval||approval.id!==SANRO_QA_PILOT.approval_id||approval.project_id!==SANRO_QA_PILOT.project_id||approval.subject!==grants[0].principal.subject||approval.owner_actor!==grants[0].principal.subject||approval.status!=='APPROVED'||approval.repository!==SANRO_QA_PILOT.repository||approval.branch!==SANRO_QA_PILOT.branch||approval.environment!=='isolated-development'||approval.max_cost_usd!==0||approval.expires_at!==SANRO_QA_PILOT.expires_at||approval.scopes?.length!==1||approval.scopes[0]!==SANRO_QA_PILOT.scope||approval.allowed_actions?.length!==allowed.length||!allowed.every(scope=>approval.allowed_actions.includes(scope))||!denied.every(scope=>approval.forbidden_actions?.includes(scope)))throw new Error('SANRO QA pilot Owner approval record does not match the fixed mandate');
  }
  return {principals,projects,workspaceRegistry:workspaceOwners,profiles,approvals};
}

export function validateMandate(auth, principal, projectId, mandate) {
  const access=projectAccess(auth,principal,projectId,'engineering:execute');
  if(!access||!mandate||typeof mandate!=='object')return false;
  return mandate.project_id===projectId&&mandate.workspace===access.project.workspace&&
    mandate.permission_profile_version===access.project.permission_profile.version&&
    mandate.owner_actor===principal.subject&&mandate.allow_network===access.project.permission_profile.allow_network&&
    mandate.allow_process_creation===access.project.permission_profile.allow_process_creation;
}
export function authenticate(auth, authorization) {
  const match = /^Bearer ([A-Za-z0-9._~+\/-]{16,512})$/.exec(authorization ?? '');
  if (!match) return null;
  const candidate = hash(match[1]);
  for (const [expectedHex,principal] of auth.principals) {
    const expected = Buffer.from(expectedHex,'hex');
    if (expected.length === candidate.length && timingSafeEqual(expected,candidate)) return principal;
  }
  return null;
}
export function projectAccess(auth, principal, projectId, scope='read') {
  const project = auth.projects.get(projectId), grants = principal?.projects?.[projectId];
  if (!project || !grants || !Array.isArray(grants.scopes) || !grants.scopes.includes(scope)) return null;
  if (grants.workspace !== project.workspace) return null;
  return {project,grants};
}
