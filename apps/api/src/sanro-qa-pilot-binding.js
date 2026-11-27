export const SANRO_QA_PILOT = Object.freeze({
  project_id: 'sanro-browser-qa',
  repository: 'arioguswara-oss/SANRO-Browser-QA',
  workspace: '/home/sanro/workforce-dev/SANRO-Browser-QA-pilot',
  branch: 'main',
  source_sha: '4436660bfc4dbdf11aadb0800b043c2c75ce6eaa',
  worker_id: 'sanro-qa',
  approval_id: 'SANRO-QA-PILOT-OPS-V1',
  expires_at: '2026-12-28T23:59:59Z',
  operation: 'private_browser_acceptance',
  capability: 'private_browser_runtime',
  scope: 'runtime:browser',
});

export const SANRO_QA_PILOT_PERMISSION_PROFILE = Object.freeze({
  version: 1,
  read_only: true,
  write_scope: 'none',
  allow_network: false,
  allow_process_creation: true,
});

export function isSanroQaPilotRuntime(project, request, commandProfile) {
  return project?.id === SANRO_QA_PILOT.project_id
    && project.repository === SANRO_QA_PILOT.repository
    && project.workspace === SANRO_QA_PILOT.workspace
    && project.branch === SANRO_QA_PILOT.branch
    && project.worker_id === SANRO_QA_PILOT.worker_id
    && project.source_sha === SANRO_QA_PILOT.source_sha
    && project.permission_profile?.read_only === true
    && project.permission_profile?.write_scope === 'none'
    && project.permission_profile?.allow_network === false
    && project.permission_profile?.allow_process_creation === true
    && request?.action === 'runtime'
    && commandProfile?.executor === 'local-ci'
    && commandProfile?.role === 'qa'
    && commandProfile?.runtime_operation === SANRO_QA_PILOT.operation;
}

export function hasSanroQaPilotPermissionProfile(profile) {
  return !!profile
    && Object.keys(profile).length === Object.keys(SANRO_QA_PILOT_PERMISSION_PROFILE).length
    && Object.entries(SANRO_QA_PILOT_PERMISSION_PROFILE).every(([key, value]) => profile[key] === value);
}
