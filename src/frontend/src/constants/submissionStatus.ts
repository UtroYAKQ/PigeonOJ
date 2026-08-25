/** 提交/测试点状态 → n-tag type 映射（详情提交历史与结果页测试点表共用） */
export function submissionStatusTagType(
  status?: string,
): 'success' | 'info' | 'warning' | 'error' {
  if (status === 'accepted') return 'success'
  if (status === 'pending' || status === 'judging') return 'info'
  if (status === 'wrong_answer') return 'warning'
  return 'error'
}
