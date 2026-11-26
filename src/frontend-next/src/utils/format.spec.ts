import { describe, expect, it } from 'vitest'

import { formatDateTime } from './format'

describe('formatDateTime', () => {
  it('格式化合法 ISO 时间为 YYYY-MM-DD HH:mm（本地时区）', () => {
    const d = new Date(2026, 7, 24, 9, 5) // 本地时区 2026-08-24 09:05
    const iso = d.toISOString()
    expect(formatDateTime(iso)).toBe('2026-08-24 09:05')
  })

  it('月 / 日 / 时 / 分补零', () => {
    const d = new Date(2026, 0, 3, 8, 7)
    expect(formatDateTime(d.toISOString())).toBe('2026-01-03 08:07')
  })

  it('空值返回占位符', () => {
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime(undefined)).toBe('—')
    expect(formatDateTime('')).toBe('—')
    expect(formatDateTime(null, 'N/A')).toBe('N/A')
  })

  it('非法时间串返回占位符', () => {
    expect(formatDateTime('not-a-date')).toBe('—')
  })
})
