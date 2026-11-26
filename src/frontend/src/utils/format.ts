/** 时间格式化工具 */
export function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

export function formatDateTime(iso: string | null | undefined, fallback = '—'): string {
  if (!iso) return fallback
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return fallback
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}

/** 紧凑时间（MM-DD HH:mm，比赛 / 团队卡片墙列表用；跨年展示不携带年份，随客户端时区） */
export function formatCompact(iso: string | null | undefined, fallback = '—'): string {
  if (!iso) return fallback
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return fallback
  return `${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}

/** 时长倒计时（≥1 天显示「X天 HH:mm:ss」，否则 HH:mm:ss；dayUnit 本地化文案由调用方注入） */
export function formatDuration(ms: number, dayUnit: string): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  if (days > 0) {
    return `${days}${dayUnit} ${pad2(hours)}:${pad2(minutes)}:${pad2(seconds)}`
  }
  return `${pad2(hours)}:${pad2(minutes)}:${pad2(seconds)}`
}
