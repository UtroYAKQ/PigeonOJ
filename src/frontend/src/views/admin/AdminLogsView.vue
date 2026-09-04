<script setup lang="ts">
/**
 * 系统日志（admin）—— 请求 / 登录 / 异常（docs/contracts/admin.md）。
 * 结构刻意从简：每类日志一个独立模板分支（不用 n-tabs），切换用 n-select 下拉框；
 * 无标题头部，切换 / 筛选 / 动作统一在工具栏；表格 flex-height 撑满剩余高度，
 * 分页置底；不经过 PaginatedDataTable。
 */
import { computed, h, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import * as adminApi from '@/api/admin'
import type { ExceptionLogRow, LoginLogRow, LogType, RequestLogRow } from '@/types'
import { LOG_LEVEL, toNaiveTagType } from '@/constants/dict'
import { downloadCsv } from '@/utils/csv'
import { formatDateTime } from '@/utils/format'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import RefreshButton from '@/components/RefreshButton.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'

type Row = RequestLogRow | LoginLogRow | ExceptionLogRow

const { t } = useI18n()
const loading = ref(false)
const type = ref<LogType>('request')
const rows = ref<Row[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const query = reactive({
  keyword: '',
  nickname: '',
  range: null as [number, number] | null,
})

async function load() {
  loading.value = true
  try {
    const res = await adminApi.adminListLogs(type.value, {
      page: page.value,
      page_size: pageSize.value,
      keyword: query.keyword || undefined,
      nickname: query.nickname || undefined,
      start: query.range ? new Date(query.range[0]).toISOString() : undefined,
      end: query.range ? new Date(query.range[1]).toISOString() : undefined,
    })
    rows.value = res.items as Row[]
    total.value = res.total
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}

function switchType(value: string | number | Array<string | number> | null) {
  if (typeof value !== 'string') return
  type.value = value as LogType
  page.value = 1
  void load()
}

function changePage(p: number) {
  page.value = p
  void load()
}

function changeSize(s: number) {
  pageSize.value = s
  page.value = 1
  void load()
}

function onSearch() {
  page.value = 1
  void load()
}

function onClearLogs() {
  const label = t(
    type.value === 'request'
      ? 'admin.logs.request'
      : type.value === 'login'
        ? 'admin.logs.login'
        : 'admin.logs.exception',
  )
  confirmAsyncDialog({
    title: t('admin.logs.clearTitle', { type: label }),
    content: t('admin.logs.clearConfirm'),
    positiveText: t('admin.logs.clearAction'),
    action: () => adminApi.adminClearLogs(type.value),
    successMessage: t('admin.logs.cleared'),
    onAfterSuccess: () => load(),
  })
}

// ---- 异常详情弹窗 ----
const tracebackShow = ref(false)
const tracebackRow = ref<ExceptionLogRow | null>(null)

function openTraceback(row: ExceptionLogRow) {
  tracebackRow.value = row
  tracebackShow.value = true
}

/** 登录日志设备展示：前端轻量解析 UA（仅展示用缩略版） */
function parseUserAgentDisplay(ua: string): string {
  const browser =
    /Edg(?:e|A|iOS)?\/([\d]+)/.exec(ua)?.[1] ? `Edge ${RegExp.$1}`
    : /MicroMessenger\/([\d]+)/.exec(ua)?.[1] ? `WeChat ${RegExp.$1}`
    : /Firefox\/([\d]+)/.exec(ua)?.[1] ? `Firefox ${RegExp.$1}`
    : /Version\/([\d]+).*Safari/.exec(ua)?.[1] ? `Safari ${RegExp.$1}`
    : /Chrome\/([\d]+)/.exec(ua)?.[1] ? `Chrome ${RegExp.$1}`
    : '--'
  const os =
    /Windows NT/.test(ua) ? 'Windows'
    : /Mac OS X/.test(ua) ? 'macOS'
    : /Android ([\d.]+)/.exec(ua)?.[1] ? `Android ${RegExp.$1.split('.')[0]}`
    : /iPhone|iPad/.test(ua) ? 'iOS'
    : /Linux/.test(ua) ? 'Linux'
    : '--'
  return `${browser} · ${os}`
}

function deviceCell(browser: string | null | undefined, os: string | null | undefined) {
  return `${browser ?? '--'} · ${os ?? '--'}`
}

// ---- 导出 ----
function exportCsv() {
  if (!rows.value.length) {
    message.warning(t('admin.logs.noExport'))
    return
  }
  const stamp = new Date().toISOString().slice(0, 10)
  if (type.value === 'request') {
    const list = rows.value as RequestLogRow[]
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
      list.map((r) => [
        r.request_id,
        r.nickname ?? '',
        r.method,
        r.path,
        r.status_code,
        r.ip_address ?? '',
        r.location ?? '',
        r.device ? deviceCell(r.device.browser, r.device.os) : '',
        r.duration_ms ?? '',
        formatDateTime(r.created_at),
      ]),
    )
  } else if (type.value === 'login') {
    const list = rows.value as LoginLogRow[]
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
      list.map((r) => [
        r.nickname ?? '',
        r.email ?? '',
        r.action,
        r.ip_address ?? '',
        r.location ?? '',
        r.user_agent ?? '',
        r.success ? t('common.success') : t('admin.logs.failed'),
        r.reason ?? '',
        formatDateTime(r.created_at),
      ]),
    )
  } else {
    const list = rows.value as ExceptionLogRow[]
    downloadCsv(
      `exception-logs-${stamp}.csv`,
      [
        t('admin.logs.level'),
        t('admin.logs.message'),
        t('admin.logs.requestId'),
        t('admin.logs.userId'),
        t('admin.logs.time'),
      ],
      list.map((r) => [
        r.level,
        r.message,
        r.request_id ?? '',
        r.user_id ?? '',
        formatDateTime(r.created_at),
      ]),
    )
  }
}

// ---- 列定义 ----
const requestColumns = computed<DataTableColumns<RequestLogRow>>(() => [
  { title: t('admin.logs.requestId'), key: 'request_id', width: 150 },
  { title: t('admin.logs.nickname'), key: 'nickname', width: 100, render: (r) => r.nickname ?? '--' },
  { title: t('admin.logs.method'), key: 'method', width: 70 },
  { title: t('admin.logs.path'), key: 'path', minWidth: 180 },
  { title: t('admin.logs.code'), key: 'status_code', width: 70 },
  { title: 'IP', key: 'ip_address', width: 110 },
  { title: t('admin.logs.location'), key: 'location', minWidth: 130, render: (r) => r.location ?? '--' },
  {
    title: t('admin.logs.device'),
    key: 'device',
    width: 160,
    render: (r) => (r.device ? deviceCell(r.device.browser, r.device.os) : '--'),
  },
  { title: t('admin.logs.duration'), key: 'duration_ms', width: 80 },
  {
    title: t('admin.logs.time'),
    key: 'created_at',
    width: 150,
    render: (row) => formatDateTime(row.created_at),
  },
])

const loginColumns = computed<DataTableColumns<LoginLogRow>>(() => [
  { title: t('admin.logs.nickname'), key: 'nickname', width: 100, render: (r) => r.nickname ?? '--' },
  { title: t('auth.email'), key: 'email', minWidth: 150 },
  { title: t('admin.logs.action'), key: 'action', width: 100 },
  { title: 'IP', key: 'ip_address', width: 110 },
  { title: t('admin.logs.location'), key: 'location', minWidth: 130, render: (r) => r.location ?? '--' },
  {
    title: t('admin.logs.device'),
    key: 'device',
    width: 160,
    render: (r) => (r.user_agent ? parseUserAgentDisplay(r.user_agent) : '--'),
  },
  {
    title: t('admin.logs.result'),
    key: 'success',
    width: 80,
    render: (row) =>
      h(
        NTag,
        { size: 'small', type: row.success ? 'success' : 'error', bordered: false },
        { default: () => (row.success ? t('common.success') : t('admin.logs.failed')) },
      ),
  },
  { title: t('admin.logs.reason'), key: 'reason', minWidth: 130 },
  {
    title: t('admin.logs.time'),
    key: 'created_at',
    width: 150,
    render: (row) => formatDateTime(row.created_at),
  },
])

const exceptionColumns = computed<DataTableColumns<ExceptionLogRow>>(() => [
  {
    title: t('admin.logs.level'),
    key: 'level',
    width: 80,
    render(row) {
      return h(
        NTag,
        {
          size: 'small',
          type: toNaiveTagType(LOG_LEVEL[row.level]?.tag ?? 'info'),
          bordered: false,
        },
        { default: () => LOG_LEVEL[row.level]?.label ?? row.level },
      )
    },
  },
  { title: t('admin.logs.message'), key: 'message', minWidth: 220 },
  { title: t('admin.logs.requestId'), key: 'request_id', width: 140 },
  {
    title: t('action.view'),
    key: 'actions',
    width: 80,
    render: (row) =>
      h(
        NButton,
        { text: true, type: 'primary', onClick: () => openTraceback(row) },
        { default: () => t('admin.logs.viewTraceback') },
      ),
  },
  {
    title: t('admin.logs.time'),
    key: 'created_at',
    width: 150,
    render: (row) => formatDateTime(row.created_at),
  },
])

const emptyText = computed(() =>
  t(
    type.value === 'request'
      ? 'admin.logs.requestEmpty'
      : type.value === 'login'
        ? 'admin.logs.loginEmpty'
        : 'admin.logs.exceptionEmpty',
  ),
)

const typeOptions = computed(() => [
  { label: t('admin.logs.request'), value: 'request' },
  { label: t('admin.logs.login'), value: 'login' },
  { label: t('admin.logs.exception'), value: 'exception' },
])

const searchPlaceholder = computed(() =>
  t(
    type.value === 'request'
      ? 'admin.logs.requestSearch'
      : type.value === 'login'
        ? 'admin.logs.loginSearch'
        : 'admin.logs.exceptionSearch',
  ),
)
</script>

<template>
  <WorkbenchShell>
    <!-- 类型切换 + 筛选 + 动作统一在工具栏（无标题头部） -->
    <div class="logs-toolbar">
      <n-select
        :value="type"
        size="small"
        :options="typeOptions"
        style="width: 180px"
        @update:value="switchType"
      />
      <n-date-picker
        v-model:value="query.range"
        type="datetimerange"
        clearable
        style="width: 280px"
        :start-placeholder="t('admin.logs.start')"
        :end-placeholder="t('admin.logs.end')"
        @update:value="onSearch"
      />
      <n-input
        v-model:value="query.nickname"
        clearable
        :placeholder="t('admin.logs.nicknameSearch')"
        style="width: 180px"
        @keyup.enter="onSearch"
        @clear="onSearch"
      />
      <n-input
        v-model:value="query.keyword"
        clearable
        :placeholder="searchPlaceholder"
        style="width: 220px"
        @keyup.enter="onSearch"
        @clear="onSearch"
      />
      <n-button type="primary" size="small" @click="onSearch">{{ t('action.search') }}</n-button>
      <div class="logs-actions">
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
        <n-button size="small" secondary @click="exportCsv">{{ t('action.export') }}</n-button>
        <n-button size="small" type="error" secondary @click="onClearLogs">
          {{ t('admin.logs.clearAction') }}
        </n-button>
      </div>
    </div>

    <div class="table-fill">
      <!-- 请求日志 -->
      <n-data-table
        v-if="type === 'request'"
        class="logs-table"
        flex-height
        size="small"
        :columns="requestColumns"
        :data="(rows as RequestLogRow[])"
        :loading="loading"
        :bordered="false"
        :row-key="(r: RequestLogRow) => r.id"
        :empty="emptyText"
        remote
      />
      <!-- 登录日志 -->
      <n-data-table
        v-else-if="type === 'login'"
        class="logs-table"
        flex-height
        size="small"
        :columns="loginColumns"
        :data="(rows as LoginLogRow[])"
        :loading="loading"
        :bordered="false"
        :row-key="(r: LoginLogRow) => r.id"
        :empty="emptyText"
      />
      <!-- 异常日志 -->
      <n-data-table
        v-else
        class="logs-table"
        flex-height
        size="small"
        :columns="exceptionColumns"
        :data="(rows as ExceptionLogRow[])"
        :loading="loading"
        :bordered="false"
        :row-key="(r: ExceptionLogRow) => r.id"
        :empty="emptyText"
      />

      <n-pagination
        class="logs-pager"
        :page="page"
        :page-size="pageSize"
        :item-count="total"
        show-size-picker
        :page-sizes="[10, 20, 50]"
        @update:page="changePage"
        @update:page-size="changeSize"
      />
    </div>

    <!-- 异常堆栈详情 -->
    <n-modal
      v-model:show="tracebackShow"
      preset="card"
      style="width: min(860px, 92vw)"
      :title="t('admin.logs.tracebackTitle')"
    >
      <template v-if="tracebackRow">
        <p class="tb-message">{{ tracebackRow.message }}</p>
        <p v-if="tracebackRow.request_id" class="tb-request">
          {{ t('admin.logs.requestId') }}: {{ tracebackRow.request_id }}
        </p>
        <pre v-if="tracebackRow.traceback" class="tb-pre">{{ tracebackRow.traceback }}</pre>
        <n-empty v-else size="small" :description="t('admin.logs.noTraceback')" />
      </template>
    </n-modal>
  </WorkbenchShell>
</template>

<style scoped>
.logs-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
}
.logs-actions {
  display: inline-flex;
  gap: 8px;
  margin-left: auto;
}
.logs-table {
  flex: 1;
  min-height: 0;
}
.logs-pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.tb-message {
  margin: 0 0 8px;
  font-weight: 600;
  word-break: break-all;
}
.tb-request {
  margin: 0 0 12px;
  color: var(--app-text-secondary);
  font-size: 12px;
}
.tb-pre {
  margin: 0;
  max-height: 60vh;
  overflow: auto;
  padding: 12px 14px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-muted-bg);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
