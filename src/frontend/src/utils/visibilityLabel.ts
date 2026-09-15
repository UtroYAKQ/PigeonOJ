/** 题单可见性 → i18n key / 标签类型（全站 public/private，团队 team_visible/admin_visible）。 */

const SET_VISIBILITY_KEYS = new Set(['public', 'private', 'team_visible', 'admin_visible'])

export function problemSetVisibilityKey(visibility: string): string {
  const value = SET_VISIBILITY_KEYS.has(visibility) ? visibility : 'private'
  return `problemSets.visibility.${value}`
}

export function problemSetVisibilityTagType(
  visibility: string,
): 'info' | 'warning' | 'error' | 'default' {
  if (visibility === 'public' || visibility === 'team_visible') return 'info'
  if (visibility === 'admin_visible') return 'warning'
  return 'error'
}
