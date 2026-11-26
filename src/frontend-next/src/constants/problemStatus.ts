/** 题目状态 → n-tag type 映射（供列表与详情复用） */
export function problemStatusTagType(status?: string): 'success' | 'warning' | 'default' {
  return status === 'published' ? 'success' : status === 'archived' ? 'default' : 'warning'
}

/** 题目状态 → i18n key 映射 */
export const problemStatusLabelKey: Record<string, string> = {
  draft: 'problems.list.statusDraft',
  published: 'problems.list.statusPublished',
  archived: 'problems.list.statusArchived',
}
