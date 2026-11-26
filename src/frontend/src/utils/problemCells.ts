/**
 * 题目表格单元格 helper（M9）：难度 / 通过率 / 提交比率的统一渲染，
 * 供前台题目列表、题单、团队 / 组织题目表与后台各管理列表复用。
 */

export interface DifficultyRow {
  difficulty?: number | null
}

export interface AcceptedRatioRow {
  submission_count?: number | null
  accepted_count?: number | null
}

/** 难度渲染：null/undefined 显示占位‘--’，否则原样数字串 */
export function renderDifficulty<T extends DifficultyRow>(row: T): string {
  return row.difficulty === null || row.difficulty === undefined ? '--' : String(row.difficulty)
}

/** 提交比率渲染（accepted/total）：无提交显示‘--’ */
export function renderRatio<T extends AcceptedRatioRow>(row: T): string {
  const total = row.submission_count ?? 0
  if (!total) return '--'
  return `${row.accepted_count ?? 0}/${total}`
}

/** 通过率渲染（百分制）：无提交显示‘--’ */
export function renderPassRate<T extends AcceptedRatioRow>(row: T): string {
  const total = row.submission_count ?? 0
  if (!total) return '--'
  return `${Math.round(((row.accepted_count ?? 0) / total) * 100)}%`
}