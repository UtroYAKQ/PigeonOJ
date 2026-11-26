/** 时间格式化工具 */

interface DateParts {
  year: number
  month: string
  day: string
  hour: string
  minute: string
}

function dateParts(iso: string | null | undefined): DateParts | null {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const pad = (n: number) => String(n).padStart(2, '0')
  return {
    year: d.getFullYear(),
    month: pad(d.getMonth() + 1),
    day: pad(d.getDate()),
    hour: pad(d.getHours()),
    minute: pad(d.getMinutes()),
  }
}

export function formatDateTime(iso: string | null | undefined, fallback = '—'): string {
  const p = dateParts(iso)
  if (!p) return fallback
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}`
}

/** 列表卡片日期（YYYY-MM-DD，不含时刻） */
export function formatDate(iso: string | null | undefined, fallback = '—'): string {
  const p = dateParts(iso)
  if (!p) return fallback
  return `${p.year}-${p.month}-${p.day}`
}

/** 列表卡片时间区间：同日 / 同年省略重复的日期部分，保持单行可读 */
export function formatDateTimeRange(
  start: string | null | undefined,
  end: string | null | undefined,
  fallback = '—',
): string {
  const a = dateParts(start)
  const b = dateParts(end)
  if (!a && !b) return fallback
  if (!a || !b) return formatDateTime(a ? start : end, fallback)
  const startText = `${a.year}-${a.month}-${a.day} ${a.hour}:${a.minute}`
  if (a.year === b.year && a.month === b.month && a.day === b.day) {
    return `${startText} – ${b.hour}:${b.minute}`
  }
  if (a.year === b.year) {
    return `${startText} – ${b.month}-${b.day} ${b.hour}:${b.minute}`
  }
  return `${startText} – ${b.year}-${b.month}-${b.day} ${b.hour}:${b.minute}`
}