/** 提交/测试点状态 → n-tag type 映射（详情提交历史与结果页测试点表共用；ok = 自测运行成功） */
export function submissionStatusTagType(status?: string): 'success' | 'info' | 'warning' | 'error' {
  if (status === 'accepted' || status === 'ok') return 'success'
  if (status === 'pending' || status === 'judging') return 'info'
  if (status === 'wrong_answer') return 'warning'
  return 'error'
}

const KNOWN_STATUS_LABELS = new Set([
  'pending',
  'judging',
  'accepted',
  'ok',
  'wrong_answer',
  'time_limit_exceeded',
  'memory_limit_exceeded',
  'output_limit_exceeded',
  'runtime_error',
  'compile_error',
  'system_error',
])

/** 提交/测试点状态 → i18n 键；未知状态兜底原值，避免生产环境渲染裸 key（missingWarn 关闭） */
export function submissionStatusLabelKey(status?: string): string {
  return status && KNOWN_STATUS_LABELS.has(status) ? `problems.status.${status}` : status || '--'
}
