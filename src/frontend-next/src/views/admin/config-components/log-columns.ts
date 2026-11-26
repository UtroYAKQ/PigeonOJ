/**
 * 系统日志列定义：请求 / 登录 / 异常三类表格列，与 CSV 导出口径一致。
 * 从 AdminLogsView 拆出，避免单文件超长；异常列的「堆栈」动作由宿主注入。
 */
import { h } from 'vue'

import ToneBadge from '@/components/common/ToneBadge.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { Button } from '@/components/ui/button'
import { LOG_LEVEL } from '@/constants/dict'
import { formatDateTime } from '@/utils/format'
import type { ExceptionLogRow, LoginLogRow, RequestLogRow } from '@/types'
import { deviceLabel, parseUserAgentDisplay } from './log-export'

type Translate = (key: string) => string

const muted = 'text-[12px] text-muted-foreground'
const mono = 'font-mono text-[11.5px] text-muted-foreground'

function codeClass(status: number): string {
  if (status >= 500) return 'tabular-nums text-destructive'
  if (status >= 400) return 'tabular-nums text-amber-600 dark:text-amber-400'
  return 'tabular-nums text-emerald-700 dark:text-emerald-400'
}

export function requestLogColumns(t: Translate): AppTableColumn<RequestLogRow>[] {
  return [
    {
      key: 'request_id',
      title: t('admin.logs.requestId'),
      width: '128px',
      cell: (row) => h('span', { class: mono, title: row.request_id }, row.request_id),
    },
    {
      key: 'nickname',
      title: t('admin.logs.nickname'),
      width: '96px',
      cell: (row) => row.nickname ?? '--',
    },
    {
      key: 'method',
      title: t('admin.logs.method'),
      width: '68px',
      cell: (row) => h('span', { class: 'font-mono text-[11.5px]' }, row.method),
    },
    {
      key: 'path',
      title: t('admin.logs.path'),
      cell: (row) =>
        h(
          'span',
          { class: 'block max-w-[320px] truncate font-mono text-[12px]', title: row.path },
          row.path,
        ),
    },
    {
      key: 'status_code',
      title: t('admin.logs.code'),
      width: '68px',
      align: 'right',
      cell: (row) => h('span', { class: codeClass(row.status_code) }, String(row.status_code)),
    },
    {
      key: 'ip_address',
      title: 'IP',
      width: '112px',
      cell: (row) => h('span', { class: mono }, row.ip_address ?? '--'),
    },
    { key: 'location', title: t('admin.logs.location'), cell: (row) => row.location ?? '--' },
    {
      key: 'device',
      title: t('admin.logs.device'),
      width: '140px',
      cell: (row) => (row.device ? deviceLabel(row.device.browser, row.device.os) : '--'),
      cellClass: muted,
    },
    {
      key: 'duration_ms',
      title: t('admin.logs.duration'),
      width: '76px',
      align: 'right',
      cell: (row) => (row.duration_ms === null ? '--' : String(row.duration_ms)),
      cellClass: 'tabular-nums text-muted-foreground',
    },
    {
      key: 'created_at',
      title: t('admin.logs.time'),
      width: '132px',
      cell: (row) => formatDateTime(row.created_at),
      cellClass: muted,
    },
  ]
}

export function loginLogColumns(t: Translate): AppTableColumn<LoginLogRow>[] {
  return [
    {
      key: 'nickname',
      title: t('admin.logs.nickname'),
      width: '96px',
      cell: (row) => row.nickname ?? '--',
    },
    { key: 'email', title: t('auth.email') },
    {
      key: 'action',
      title: t('admin.logs.action'),
      width: '96px',
      cell: (row) => h('span', { class: 'font-mono text-[12px]' }, row.action),
    },
    {
      key: 'ip_address',
      title: 'IP',
      width: '112px',
      cell: (row) => h('span', { class: mono }, row.ip_address ?? '--'),
    },
    { key: 'location', title: t('admin.logs.location'), cell: (row) => row.location ?? '--' },
    {
      key: 'device',
      title: t('admin.logs.device'),
      width: '150px',
      cell: (row) => (row.user_agent ? parseUserAgentDisplay(row.user_agent) : '--'),
      cellClass: muted,
    },
    {
      key: 'success',
      title: t('admin.logs.result'),
      width: '76px',
      cell: (row) =>
        h(ToneBadge, {
          tone: row.success ? 'success' : 'danger',
          label: row.success ? t('common.success') : t('admin.logs.failed'),
        }),
    },
    {
      key: 'reason',
      title: t('admin.logs.reason'),
      cell: (row) => row.reason ?? '--',
      cellClass: muted,
    },
    {
      key: 'created_at',
      title: t('admin.logs.time'),
      width: '132px',
      cell: (row) => formatDateTime(row.created_at),
      cellClass: muted,
    },
  ]
}

export function exceptionLogColumns(
  t: Translate,
  onView: (row: ExceptionLogRow) => void,
): AppTableColumn<ExceptionLogRow>[] {
  return [
    {
      key: 'level',
      title: t('admin.logs.level'),
      width: '76px',
      cell: (row) =>
        h(ToneBadge, {
          tone: LOG_LEVEL[row.level]?.tag ?? 'info',
          label: LOG_LEVEL[row.level]?.label ?? row.level,
        }),
    },
    {
      key: 'message',
      title: t('admin.logs.message'),
      cell: (row) =>
        h(
          'span',
          { class: 'block max-w-[460px] truncate text-[12.5px]', title: row.message },
          row.message,
        ),
    },
    {
      key: 'request_id',
      title: t('admin.logs.requestId'),
      width: '128px',
      cell: (row) => h('span', { class: mono }, row.request_id ?? '--'),
    },
    {
      key: 'actions',
      title: t('action.view'),
      width: '72px',
      cell: (row) =>
        h(
          Button,
          {
            variant: 'link',
            size: 'xs',
            class: 'h-6 px-0 text-[12px]',
            onClick: () => onView(row),
          },
          { default: () => t('admin.logs.viewTraceback') },
        ),
    },
    {
      key: 'created_at',
      title: t('admin.logs.time'),
      width: '132px',
      cell: (row) => formatDateTime(row.created_at),
      cellClass: muted,
    },
  ]
}
