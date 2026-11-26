import {createHash,timingSafeEqual} from 'node:crypto';
import {realpathSync,readFileSync,lstatSync,statSync} from 'node:fs';

const hash = value => createHash('sha256').update(value).digest();
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
    const workspace = realpathSync(p.workspace);
    const wsStat=statSync(workspace);if(!wsStat.isDirectory())throw new Error('project workspace must be a directory');
    if(workspaceOwners.has(workspace))throw new Error('workspace is already registered to another project');
    const permissionProfile=p.permission_profile??{version:1,read_only:false,allow_network:false,allow_process_creation:false,write_scope:'project-worktree'};
    if(!permissionProfile||permissionProfile.version!==1||typeof permissionProfile.read_only!=='boolean'||typeof permissionProfile.allow_network!=='boolean'||typeof permissionProfile.allow_process_creation!=='boolean'||permissionProfile.write_scope!=='project-worktree')throw new Error('invalid project permission profile');
    workspaceOwners.set(workspace,p.id);
    projects.set(p.id,{...p,workspace,permission_profile:permissionProfile});
  }
  const profiles=config.command_profiles??{},approvals=config.approvals??{};
  if(!profiles||typeof profiles!=='object'||Array.isArray(profiles)||!approvals||typeof approvals!=='object'||Array.isArray(approvals))throw new Error('invalid profile or approval registry');
  const shells=new Set(['sh','bash','dash','zsh','fish','cmd','powershell']);
  for(const [id,p] of Object.entries(profiles))if(!/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$/.test(id)||!p||!Array.isArray(p.projects)||!p.projects.every(projectId=>projects.has(projectId))||!Array.isArray(p.command)||!p.command.length||!p.command.every(arg=>typeof arg==='string'&&arg.length>0)||shells.has(p.command[0].split('/').pop()))throw new Error('invalid or unauthorized command profile');
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
