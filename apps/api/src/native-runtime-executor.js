/**
 * Adapt a real host native-approval provider to the fixed Workforce runtime
 * callback.  This module deliberately has no default provider: Hermes plugin
 * approval transports route an approval that already exists, but do not
 * create per-job approvals.  Without an installed, supported provider jobs
 * remain fail-closed.
 */
export function createNativeRuntimeExecutor({ requestNativeApproval } = {}) {
  if (typeof requestNativeApproval !== 'function') {
    throw new Error('native per-job approval provider is required');
  }

  return async context => {
    const expected = {
      actor: context.principal?.subject,
      project_id: context.project?.id,
      job_id: context.request?.idempotency_key,
      operation: context.profile?.runtime_operation,
    };
    if (!context.nativeApprovalRequired || typeof context.invokeAfterNativeApproval !== 'function'
        || Object.values(expected).some(value => typeof value !== 'string' || !value)) {
      throw Object.assign(new Error('native runtime admission context is incomplete'), { status: 503 });
    }

    const approval = await requestNativeApproval(Object.freeze({ ...expected }));
    if (!approval || approval.approved !== true
        || approval.actor !== expected.actor
        || approval.project_id !== expected.project_id
        || approval.job_id !== expected.job_id
        || approval.operation !== expected.operation
        || typeof approval.id !== 'string' || approval.id.length < 8 || approval.id.length > 512) {
      throw Object.assign(new Error('native per-job approval is absent, denied, or mismatched'), { status: 403 });
    }
    return context.invokeAfterNativeApproval(approval);
  };
}
