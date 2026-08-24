/** 主题应用：切换 document 根节点 dark class，驱动 Tailwind 暗色变体 / CSS 变量 / Monaco 主题。 */
export function applyTheme(theme: string): void {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('dark', theme === 'dark')
}
