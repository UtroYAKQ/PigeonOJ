/**
 * 智能返回：优先回退到 SPA 内来源页，无历史（直达 URL / 新标签页）时落固定兜底路径。
 *
 * vue-router 4 在 history.state 中维护 back 字段，仅当存在同源 SPA 内的上一跳时非空；
 * 借此区分「应用内导航而来」与「直达打开」，避免 back() 无效或把用户带离站点。
 */
import type { Router } from 'vue-router'

interface HistoryStateWithBack {
  back?: string | null
}

export function goBackOrFallback(router: Router, fallback: string): void {
  const state = window.history.state as HistoryStateWithBack | null
  if (state?.back != null) {
    router.back()
  } else {
    void router.push(fallback)
  }
}
