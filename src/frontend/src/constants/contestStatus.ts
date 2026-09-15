/**
 * 比赛状态 → 文案 i18n 键与 n-tag type（前台列表 / 管理列表 / 赛时工具共用；
 * 与 submissionStatus.ts 同一模式）。
 */

type ContestStatusTagType = 'success' | 'info' | 'warning' | 'error' | 'default'

/** 比赛状态 → i18n 键；未知状态兜底原值避免渲染裸 key */
export function contestStatusLabelKey(status?: string): string {
  if (status === 'running') return 'contests.statusRunning'
  if (status === 'scheduled') return 'contests.statusScheduled'
  if (status === 'finished') return 'contests.statusFinished'
  return status || '--'
}

/** 比赛状态 → n-tag type（running=success / scheduled=info / 其余 default，兼容未知值） */
export function contestStatusTagType(status?: string): ContestStatusTagType {
  if (status === 'running') return 'success'
  if (status === 'scheduled') return 'info'
  return 'default'
}