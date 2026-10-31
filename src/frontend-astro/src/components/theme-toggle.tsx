"use client"

import { useSyncExternalStore } from "react"
import { MoonIcon, SunIcon, SunMoonIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useTheme } from "@/hooks/use-theme"
import { toggleTheme } from "@/lib/theme"

const noopSubscribe = () => () => {}

/**
 * 明暗主题切换（独立 island，状态经 lib/theme 跨岛同步）。
 *
 * 静态构建时无法得知访客的系统主题，因此首屏先渲染与主题无关的中性图标，
 * 水合完成后再显示实际图标——避免 SSR/CSR 图标不一致触发 hydration 报错。
 */
export function ThemeToggle() {
  const hydrated = useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false
  )
  const { resolved } = useTheme()

  if (!hydrated) {
    return (
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="切换明暗主题"
        title="切换明暗主题"
        disabled
      >
        <SunMoonIcon />
      </Button>
    )
  }

  const label = resolved === "dark" ? "切换到浅色模式" : "切换到深色模式"

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-sm"
      aria-label={label}
      title={label}
      onClick={() => toggleTheme()}
    >
      {resolved === "dark" ? <SunIcon /> : <MoonIcon />}
    </Button>
  )
}
