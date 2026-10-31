"use client"

import { useSyncExternalStore } from "react"
import {
  getStoredTheme,
  resolveTheme,
  subscribeTheme,
  type Theme,
} from "@/lib/theme"

/**
 * 订阅全局主题状态（跨 island 一致）。
 * 服务端渲染时返回 system，客户端首帧会立即校正。
 */
export function useTheme(): { theme: Theme; resolved: "light" | "dark" } {
  const theme = useSyncExternalStore(
    subscribeTheme,
    getStoredTheme,
    () => "system" as Theme
  )
  return { theme, resolved: resolveTheme(theme) }
}
