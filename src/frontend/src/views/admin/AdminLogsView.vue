<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import * as adminApi from '@/api/admin'
import type { ExceptionLogRow, LoginLogRow, LogType, RequestLogRow } from '@/types'
import { LOG_LEVEL, toNaiveTagType } from '@/constants/dict'
import { downloadCsv } from '@/utils/csv'
import { formatDateTime } from '@/utils/format'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'

const { t } = useI18n()
const loading = ref(false)
const type = ref<LogType>('request')
const rows = ref<unknown[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()
const query = reactive({
  keyword: '',
  range: null as [number, number] | null,
})
async function load() {
  const seq = beginLoad()
  loading.value = true
  try {
    const res = await adminApi.adminListLogs(type.value, {
      page: page.value,
      page_size: pageSize.value,
      keyword: query.keyword || undefined,
      start: query.range ? new Date(query.range[0]).toISOString() : undefined,
      end: query.range ? new Date(query.range[1]).toISOString() : undefined,
    })
    if (!isCurrent(seq)) return
    rows.value = res.items
    total.value = res.total
  } catch (e) {
    if (!isCurrent(seq)) return
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}
watch(type, () => {
  resetPage()
  load()
})
onMounted(load)
function onSearch() {
  resetPage()
  load()
}
function onReset() {
  query.keyword = ''
  query.range = null
  resetPage()
  load()
}

const searchPlaceholder = computed(() =>
  t(
    type.value === 'request'
      ? 'admin.logs.requestSearch'
      : type.value === 'login'
        ? 'admin.logs.loginSearch'
        : 'admin.logs.exceptionSearch',
  ),
)

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
        t('admin.logs.userId'),
        t('admin.logs.method'),
        t('admin.logs.path'),
        t('admin.logs.code'),
        'IP',
        t('admin.logs.duration'),
        t('admin.logs.time'),
      ],
      list.map((r) => [
        r.request_id,
        r.user_id ?? '',
        r.method,
        r.path,
        r.status_code,
        r.ip_address ?? '',
        r.duration_ms ?? '',
        formatDateTime(r.created_at),
      ]),
    )
  } else if (type.value === 'login') {
    const list = rows.value as LoginLogRow[]
    downloadCsv(
      `login-logs-${stamp}.csv`,
      [
        t('admin.logs.userId'),
        t('auth.email'),
        t('admin.logs.action'),
        'IP',
        t('admin.logs.result'),
        t('admin.logs.reason'),
        t('admin.logs.time'),
      ],
      list.map((r) => [
        r.user_id ?? '',
        r.email ?? '',
        r.action,
        r.ip_address ?? '',
        r.success ? t('common.yes') : t('common.no'),
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

const requestColumns = computed<DataTableColumns<RequestLogRow>>(() => [
  { title: t('admin.logs.requestId'), key: 'request_id', width: 180 },
  { title: t('admin.logs.method'), key: 'method', width: 80 },
  { title: t('admin.logs.path'), key: 'path', minWidth: 220 },
  { title: t('admin.logs.code'), key: 'status_code', width: 80 },
  { title: 'IP', key: 'ip_address', width: 120 },
  { title: t('admin.logs.duration'), key: 'duration_ms', width: 100 },
  {
    title: t('admin.logs.time'),
    key: 'created_at',
    width: 150,
    render: (row) => formatDateTime(row.created_at),
  },
])
const loginColumns = computed<DataTableColumns<LoginLogRow>>(() => [
  { title: t('auth.email'), key: 'email', minWidth: 180 },
  { title: t('admin.logs.action'), key: 'action', width: 120 },
  { title: 'IP', key: 'ip_address', width: 130 },
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
  { title: t('admin.logs.reason'), key: 'reason', minWidth: 160 },
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
    width: 90,
    render(row) {
      return h(
        NTag,
        { size: 'small', type: toNaiveTagType(LOG_LEVEL[row.level]?.tag ?? 'info'), bordered: false },
        { default: () => LOG_LEVEL[row.level]?.label ?? row.level },
      )
    },
  },
  { title: t('admin.logs.message'), key: 'message', minWidth: 260 },
  { title: t('admin.logs.requestId'), key: 'request_id', width: 160 },
  { title: t('admin.logs.userId'), key: 'user_id', width: 140 },
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

/** 当前日志类型对应的列定义（三种日志共用同一张分页表格） */
const activeColumns = computed(() =>
  type.value === 'request'
    ? requestColumns.value
    : type.value === 'login'
      ? loginColumns.value
      : exceptionColumns.value,
)
</script>

<template>
  <WorkbenchShell :title="t('admin.logs.title')">
    <template #header-extra>
        <n-button size="small" secondary :loading="loading" @click="exportCsv">{{
          t('action.export')
        }}</n-button>
      </template>

      <n-tabs v-model:value="type" type="line" animated>
        <n-tab-pane name="request" :tab="t('admin.logs.request')" />
        <n-tab-pane name="login" :tab="t('admin.logs.login')" />
        <n-tab-pane name="exception" :tab="t('admin.logs.exception')" />
      </n-tabs>

      <SearchFilterBar
        :keyword="query.keyword"
        :placeholder="searchPlaceholder"
        search-width="200px"
        @update:keyword="(v: string) => { query.keyword = v }"
        @search="onSearch"
        @reset="onReset"
      >
        <n-date-picker
          v-model:value="query.range"
          type="datetimerange"
          clearable
          style="width: 280px"
          :start-placeholder="t('admin.logs.start')"
          :end-placeholder="t('admin.logs.end')"
          @update:value="onSearch"
        />
        <template #actions>
          <n-button type="primary" @click="onSearch">{{ t('action.search') }}</n-button>
          <n-button secondary @click="onReset">{{ t('action.reset') }}</n-button>
        </template>
      </SearchFilterBar>

      <PaginatedDataTable
        :columns="activeColumns"
        :data="(rows as unknown[])"
        :loading="loading"
        :total="total"
        v-model:page="page"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50]"
        :empty-text="emptyText"
        :table-props="type === 'request' ? { remote: true } : {}"
        @update:page="(p: number) => { changePage(p); load() }"
        @update:page-size="(s: number) => { changeSize(s); load() }"
      />
  </WorkbenchShell>
</template>

