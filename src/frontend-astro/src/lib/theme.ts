/**
 * 主题（明 / 暗 / 跟随系统）单一事实来源。
 * - 持久化到 localStorage；首屏由 BaseLayout 内联脚本在绘制前应用，避免闪烁
 * - 跨 React island 通过自定义事件同步（Astro 多 island 不共享 React Context）
 */
export type Theme = "light" | "dark" | "system"

export const THEME_STORAGE_KEY = "pigeonoj.theme"
export const THEME_CHANGE_EVENT = "pigeonoj:theme-change"

export function getStoredTheme(): Theme {
  if (typeof localStorage === "undefined") return "system"
  const value = localStorage.getItem(THEME_STORAGE_KEY)
  return value === "light" || value === "dark" || value === "system"
    ? value
    : "system"
}

export function resolveTheme(theme: Theme): "light" | "dark" {
  if (theme !== "system") return theme
  if (typeof window === "undefined") return "light"
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light"
}

export function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") return
  const resolved = resolveTheme(theme)
  document.documentElement.classList.toggle("dark", resolved === "dark")
  document.documentElement.style.colorScheme = resolved
  localStorage.setItem(THEME_STORAGE_KEY, theme)
  window.dispatchEvent(
    new CustomEvent(THEME_CHANGE_EVENT, { detail: { theme, resolved } })
  )
}

export function toggleTheme(): Theme {
  const next: Theme =
    resolveTheme(getStoredTheme()) === "dark" ? "light" : "dark"
  applyTheme(next)
  return next
}

export function subscribeTheme(onChange: () => void): () => void {
  const handler = () => onChange()
  window.addEventListener(THEME_CHANGE_EVENT, handler)
  window.addEventListener("storage", handler)
  const media = window.matchMedia("(prefers-color-scheme: dark)")
  media.addEventListener("change", handler)
  return () => {
    window.removeEventListener(THEME_CHANGE_EVENT, handler)
    window.removeEventListener("storage", handler)
    media.removeEventListener("change", handler)
  }
}
