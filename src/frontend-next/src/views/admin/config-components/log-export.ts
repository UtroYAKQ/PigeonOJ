/**
 * 系统日志导出与设备解析：CSV 表头随 locale 翻译，行值与表格展示口径一致。
 */
import { i18n } from '@/i18n'
import { downloadCsv } from '@/utils/csv'
import { formatDateTime } from '@/utils/format'
import type { ExceptionLogRow, LoginLogRow, LogType, RequestLogRow } from '@/types'

type Translate = (key: string, params?: Record<string, unknown>) => string

const t: Translate = (key, params) =>
  (
    i18n as unknown as { global: { t: (k: string, p?: Record<string, unknown>) => string } }
  ).global.t(key, params)

/** 请求日志设备列：浏览器 · 操作系统（后端 UA 解析结果） */
export function deviceLabel(
  browser: string | null | undefined,
  os: string | null | undefined,
): string {
  return `${browser ?? '--'} · ${os ?? '--'}`
}

/** 登录日志设备展示：轻量 UA 解析（仅展示用缩略版，权威解析在后端） */
export function parseUserAgentDisplay(ua: string): string {
  const browserPatterns: Array<[RegExp, string]> = [
    [/Edg(?:e|A|iOS)?\/(\d+)/, 'Edge'],
    [/MicroMessenger\/(\d+)/, 'WeChat'],
    [/Firefox\/(\d+)/, 'Firefox'],
    [/Version\/(\d+).*Safari/, 'Safari'],
    [/Chrome\/(\d+)/, 'Chrome'],
  ]
  let browser = '--'
  for (const [pattern, name] of browserPatterns) {
    const match = pattern.exec(ua)
    if (match) {
      browser = `${name} ${match[1]}`
      break
    }
  }

  const android = /Android ([\d.]+)/.exec(ua)
  const os = /Windows NT/.test(ua)
    ? 'Windows'
    : /Mac OS X/.test(ua)
      ? 'macOS'
      : android
        ? `Android ${android[1]?.split('.')[0] ?? ''}`.trim()
        : /iPhone|iPad/.test(ua)
          ? 'iOS'
          : /Linux/.test(ua)
            ? 'Linux'
            : '--'

  return `${browser} · ${os}`
}

/** 导出当前页日志为 CSV（文件名含类型与日期） */
export function exportLogsCsv(type: LogType, rows: unknown[]): void {
  const stamp = new Date().toISOString().slice(0, 10)

  if (type === 'request') {
    const list = rows as RequestLogRow[]
    downloadCsv(
      `request-logs-${stamp}.csv`,
      [
        t('admin.logs.requestId'),
        t('admin.logs.nickname'),
        t('admin.logs.method'),
        t('admin.logs.path'),
        t('admin.logs.code'),
        'IP',
        t('admin.logs.location'),
        t('admin.logs.device'),
        t('admin.logs.duration'),
        t('admin.logs.time'),
      ],
      list.map((row) => [
        row.request_id,
        row.nickname ?? '',
        row.method,
        row.path,
        row.status_code,
        row.ip_address ?? '',
        row.location ?? '',
        row.device ? deviceLabel(row.device.browser, row.device.os) : '',
        row.duration_ms ?? '',
        formatDateTime(row.created_at),
      ]),
    )
    return
  }

  if (type === 'login') {
    const list = rows as LoginLogRow[]
    downloadCsv(
      `login-logs-${stamp}.csv`,
      [
        t('admin.logs.nickname'),
        t('auth.email'),
        t('admin.logs.action'),
        'IP',
        t('admin.logs.location'),
        t('admin.logs.device'),
        t('admin.logs.result'),
        t('admin.logs.reason'),
        t('admin.logs.time'),
      ],
      list.map((row) => [
        row.nickname ?? '',
        row.email ?? '',
        row.action,
        row.ip_address ?? '',
        row.location ?? '',
        row.user_agent ?? '',
        row.success ? t('common.success') : t('admin.logs.failed'),
        row.reason ?? '',
        formatDateTime(row.created_at),
      ]),
    )
    return
  }

  const list = rows as ExceptionLogRow[]
  downloadCsv(
    `exception-logs-${stamp}.csv`,
    [
      t('admin.logs.level'),
      t('admin.logs.message'),
      t('admin.logs.requestId'),
      t('admin.logs.userId'),
      t('admin.logs.time'),
    ],
    list.map((row) => [
      row.level,
      row.message,
      row.request_id ?? '',
      row.user_id ?? '',
      formatDateTime(row.created_at),
    ]),
  )
}
