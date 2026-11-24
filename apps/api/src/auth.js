import {createHash,timingSafeEqual} from 'node:crypto';
import {realpathSync,readFileSync,lstatSync} from 'node:fs';

const hash = value => createHash('sha256').update(value).digest();
export function loadAuth(path) {
  if (!path) throw new Error('WORKFORCE_AUTH_FILE is required; authorization is deny-by-default');
  const fileStat=lstatSync(path);if(fileStat.isSymbolicLink()||!fileStat.isFile()||fileStat.uid!==process.getuid()||(fileStat.mode&0o077)!==0)throw new Error('authorization file must be a real file owned by current user with mode 0600');
  const config = JSON.parse(readFileSync(path,'utf8'));
  if (config.version !== 1 || !Array.isArray(config.principals) || !Array.isArray(config.projects)) throw new Error('invalid authorization file schema');
  const principals = new Map();
  for (const p of config.principals) {
    if (!/^[a-f0-9]{64}$/.test(p.token_sha256) || !p.subject || !p.projects || typeof p.projects !== 'object') throw new Error('invalid principal entry');
    principals.set(p.token_sha256,p);
  }
  const projects = new Map();
  for (const p of config.projects) {
    if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$/.test(p.id) || !p.name || !p.workspace) throw new Error('invalid project entry');
    const workspace = realpathSync(p.workspace);
    projects.set(p.id,{...p,workspace});
  }
  const profiles=config.command_profiles??{},approvals=config.approvals??{};
  if(!profiles||typeof profiles!=='object'||Array.isArray(profiles)||!approvals||typeof approvals!=='object'||Array.isArray(approvals))throw new Error('invalid profile or approval registry');
  const shells=new Set(['sh','bash','dash','zsh','fish','cmd','powershell']);
  for(const [id,p] of Object.entries(profiles))if(!/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$/.test(id)||!p||!Array.isArray(p.projects)||!p.projects.every(projectId=>projects.has(projectId))||!Array.isArray(p.command)||!p.command.length||!p.command.every(arg=>typeof arg==='string'&&arg.length>0)||shells.has(p.command[0].split('/').pop()))throw new Error('invalid or unauthorized command profile');
  return {principals,projects,profiles,approvals};
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
