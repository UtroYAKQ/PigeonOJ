<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { adminListReports } from '@/api/admin'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { REPORT_STATUS, REPORT_TYPE } from '@/constants/dict'
import { usePagination } from '@/composables/usePagination'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import ReportHandleDialog from './report-components/ReportHandleDialog.vue'
import type { Report, ReportStatus } from '@/types'

const { t } = useI18n()

const loading = ref(false)
const list = ref<Report[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()

const query = reactive({ status: 'all' as ReportStatus | 'all' })

const statusTabs = computed(() => [
  { value: 'all', label: t('common.allStatus') },
  ...(Object.keys(REPORT_STATUS) as ReportStatus[]).map((value) => ({
    value,
    label: REPORT_STATUS[value].label,
  })),
])

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await adminListReports({
      page: page.value,
      page_size: pageSize.value,
      status: query.status === 'all' ? undefined : query.status,
    })
    if (!isCurrent(seq)) return
    list.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

function onSearch(): void {
  resetPage()
  void load()
}

function onStatusChange(value: string | number): void {
  query.status = String(value) as ReportStatus | 'all'
  onSearch()
}

const handleOpen = ref(false)
const handleTarget = ref<Report | null>(null)

function openHandle(report: Report): void {
  handleTarget.value = report
  handleOpen.value = true
}

function targetText(report: Report): string {
  return report.target_summary ?? `#${report.target_id.slice(0, 8)}`
}

const columns = computed<AppTableColumn<Report>[]>(() => [
  {
    key: 'target_type',
    title: t('admin.reports.type'),
    width: '90px',
    cell: (row) => {
      const tone =
        row.target_type === 'comment' ? 'info' : row.target_type === 'post' ? 'warning' : 'primary'
      return h(ToneBadge, { tone, label: REPORT_TYPE[row.target_type] ?? row.target_type })
    },
  },
  {
    key: 'target',
    title: t('admin.reports.target'),
    cell: (row) =>
      h('div', { class: 'space-y-0.5' }, [
        h('div', { class: 'text-[13px]' }, targetText(row)),
        h('div', { class: 'font-mono text-[11px] text-muted-foreground' }, row.target_id),
      ]),
  },
  {
    key: 'reporter_nickname',
    title: t('admin.reports.reporter'),
    width: '130px',
  },
  {
    key: 'reason',
    title: t('admin.reports.reason'),
    cell: (row) =>
      h('span', { class: 'line-clamp-2 text-[12.5px]', title: row.reason }, row.reason),
  },
  {
    key: 'status',
    title: t('admin.reports.status'),
    width: '100px',
    cell: (row) => {
      const meta = REPORT_STATUS[row.status]
      return h(ToneBadge, { tone: meta?.tag ?? 'info', label: meta?.label ?? row.status })
    },
  },
  {
    key: 'created_at',
    title: t('admin.reports.createdAt'),
    width: '150px',
    cell: (row) => formatDateTime(row.created_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'handled_at',
    title: t('admin.reports.handledAt'),
    width: '150px',
    cell: (row) => formatDateTime(row.handled_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'actions',
    title: t('action.handle'),
    width: '90px',
    align: 'right',
    cell: (row) =>
      row.status === 'pending'
        ? h(
            Button,
            { variant: 'ghost', size: 'xs', onClick: () => openHandle(row) },
            { default: () => t('action.handle') },
          )
        : h('span', { class: 'text-[12.5px] text-muted-foreground' }, t('admin.reports.handled')),
  },
])

onMounted(load)
</script>

<template>
  <WorkbenchShell :title="t('nav.reports')">
    <template #toolbar>
      <SearchFilterBar :show-search="false">
        <Select
          :model-value="query.status"
          @update:model-value="(value) => (typeof value === 'string' ? onStatusChange(value) : undefined)"
        >
          <SelectTrigger class="h-9 w-[140px] text-[13px]">
            <SelectValue :placeholder="t('common.allStatus')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="tab in statusTabs" :key="tab.value" :value="tab.value">
              {{ tab.label }}
            </SelectItem>
          </SelectContent>
        </Select>
        <template #actions>
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load()" />
        </template>
      </SearchFilterBar>
    </template>

    <PaginatedTable
      :columns="columns"
      :data="list"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[10, 20, 50]"
      show-size-picker
      :empty-text="t('admin.reports.empty')"
      @update:page="
        (value: number) => {
          changePage(value)
          load()
        }
      "
      @update:page-size="
        (value: number) => {
          changeSize(value)
          load()
        }
      "
    />

    <ReportHandleDialog v-model:open="handleOpen" :report="handleTarget" @done="load" />
  </WorkbenchShell>
</template>
