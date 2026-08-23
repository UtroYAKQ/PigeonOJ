/** 主题应用：users.theme 字段（'light' / 'dark'），切换 document 根节点 class 驱动 Element Plus 暗色变量。 */
export function applyTheme(theme: string): void {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('dark', theme === 'dark')
}
