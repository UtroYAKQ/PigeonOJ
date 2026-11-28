<script setup lang="ts">
/**
 * 系统日志（admin）：请求 / 登录 / 异常（docs/contracts.md §12）。
 * 列表统一走 WorkbenchShell + SearchFilterBar + PaginatedTable，筛选 / 导出 / 清空统一在工具栏。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import * as adminApi from '@/api/admin'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { usePagination } from '@/composables/usePagination'
import { LOG_LEVEL } from '@/constants/dict'
import { confirmDialog, message } from '@/utils/feedback'
import type { ExceptionLogRow, LoginLogRow, LogType, RequestLogRow } from '@/types'
import {
  exceptionLogColumns,
  loginLogColumns,
  requestLogColumns,
} from './config-components/log-columns'
import { exportLogsCsv } from './config-components/log-export'
import LogTracebackDialog from './config-components/LogTracebackDialog.vue'

type Row = RequestLogRow | LoginLogRow | ExceptionLogRow

const { t } = useI18n()

const type = ref<LogType>('request')
const rows = ref<Row[]>([])
const loading = ref(false)
const level = ref<'all' | 'error' | 'warning' | 'fatal'>('all')
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()
const query = reactive({ keyword: '', nickname: '', start: '', end: '' })

/** datetime-local 输入 → ISO 时间（残缺输入忽略，避免 toISOString 抛错） */
function toIso(value: string): string | undefined {
  if (!value) return undefined
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString()
}

const levelOptions = computed(() =>
  (['error', 'warning', 'fatal'] as const).map((value) => ({
    value,
    label: LOG_LEVEL[value]?.label ?? value,
  })),
)

/**
 * 级别筛选（异常日志）：后端 LogQuery 尚未提供 level 参数，
 * 这里只过滤当前页已加载的行，翻页 / 导出均以过滤后的行为准。
 */
const visibleRows = computed<Row[]>(() =>
  type.value === 'exception' && level.value !== 'all'
    ? rows.value.filter((row) => (row as ExceptionLogRow).level === level.value)
    : rows.value,
)

/** 类型相关的空态 / 搜索占位（key 后缀与 LogType 同名：request / login / exception） */
const typeText = computed(() => ({
  empty: t(`admin.logs.${type.value}Empty`),
  search: t(`admin.logs.${type.value}Search`),
}))

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await adminApi.adminListLogs(type.value, {
      page: page.value,
      page_size: pageSize.value,
      keyword: query.keyword || undefined,
      nickname: query.nickname || undefined,
      start: toIso(query.start),
      end: toIso(query.end),
    })
    if (!isCurrent(seq)) return
    rows.value = result.items as Row[]
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

function switchType(value: unknown): void {
  type.value = String(value) as LogType
  level.value = 'all'
  rows.value = []
  resetPage()
  void load()
}

function onLevelChange(value: unknown): void {
  level.value = String(value) as 'all' | 'error' | 'warning' | 'fatal'
}

function onSearch(): void {
  resetPage()
  void load()
}

function onPage(value: number): void {
  changePage(value)
  void load()
}

function onPageSize(value: number): void {
  changeSize(value)
  void load()
}

function exportCsv(): void {
  if (!visibleRows.value.length) {
    message.warning(t('admin.logs.noExport'))
    return
  }
  exportLogsCsv(type.value, visibleRows.value)
}

async function onClear(): Promise<void> {
  const ok = await confirmDialog({
    title: t('admin.logs.clearTitle', { type: t(`admin.logs.${type.value}`) }),
    content: t('admin.logs.clearConfirm'),
    positiveText: t('admin.logs.clearAction'),
    negativeText: t('action.cancel'),
    danger: true,
  })
  if (!ok) return
  try {
    await adminApi.adminClearLogs(type.value)
    message.success(t('admin.logs.cleared'))
    resetPage()
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

// ---------------- 异常堆栈详情 ----------------
const tracebackOpen = ref(false)
const tracebackRow = ref<ExceptionLogRow | null>(null)

function openTraceback(row: ExceptionLogRow): void {
  tracebackRow.value = row
  tracebackOpen.value = true
}

/** 列定义随类型切换（列文案 / 单元格渲染见 config-components/log-columns.ts） */
const columns = computed<AppTableColumn<any>[]>(() => {
  if (type.value === 'login') return loginLogColumns(t)
  if (type.value === 'exception') return exceptionLogColumns(t, openTraceback)
  return requestLogColumns(t)
})

onMounted(load)
</script>

<template>
  <WorkbenchShell :title="t('nav.logs')">

    <template #toolbar>
      <SearchFilterBar
        :keyword="query.keyword"
        :placeholder="typeText.search"
        @update:keyword="query.keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <Select :model-value="type" @update:model-value="switchType">
          <SelectTrigger class="h-9 w-[160px] text-[13px]" :aria-label="t('admin.logs.title')">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="request">{{ t('admin.logs.request') }}</SelectItem>
            <SelectItem value="login">{{ t('admin.logs.login') }}</SelectItem>
            <SelectItem value="exception">{{ t('admin.logs.exception') }}</SelectItem>
          </SelectContent>
        </Select>

        <Select v-if="type === 'exception'" :model-value="level" @update:model-value="onLevelChange">
          <SelectTrigger class="h-9 w-[132px] text-[13px]" :aria-label="t('admin.logs.level')">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('common.allStatus') }}</SelectItem>
            <SelectItem v-for="option in levelOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <Input
          v-model="query.start"
          type="datetime-local"
          class="h-9 w-[184px] text-[12px]"
          :aria-label="t('admin.logs.start')"
          :title="t('admin.logs.start')"
          @change="onSearch"
        />
        <Input
          v-model="query.end"
          type="datetime-local"
          class="h-9 w-[184px] text-[12px]"
          :aria-label="t('admin.logs.end')"
          :title="t('admin.logs.end')"
          @change="onSearch"
        />
        <Input
          v-model="query.nickname"
          class="h-9 w-[150px] text-[13px]"
          :placeholder="t('admin.logs.nicknameSearch')"
          @keyup.enter="onSearch"
        />

        <template #actions>
          <Button variant="outline" size="toolbar" @click="exportCsv">
            {{ t('action.export') }}
          </Button>
          <Button
            variant="outline"
            size="sm"
            class="h-9 text-destructive hover:text-destructive"
            @click="onClear"
          >
            {{ t('admin.logs.clearAction') }}
          </Button>
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
        </template>
      </SearchFilterBar>
    </template>

    <PaginatedTable
      :columns="columns"
      :data="visibleRows"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[10, 20, 50]"
      show-size-picker
      :empty-text="level === 'all' ? typeText.empty : t('common.noData')"
      @update:page="onPage"
      @update:page-size="onPageSize"
    />

    <LogTracebackDialog v-model:open="tracebackOpen" :row="tracebackRow" />
  </WorkbenchShell>
</template>