<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import * as adminApi from '@/api/admin'
import type { Report, ReportStatus, ReportType } from '@/types'
import { REPORT_STATUS, REPORT_TYPE, toNaiveTagType } from '@/constants/dict'
import { formatDateTime } from '@/utils/format'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import ModalFooter from '@/components/ModalFooter.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'

const { t } = useI18n()
const loading = ref(false)
const list = ref<Report[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()
/** n-select 以 null 表示不限：'' 会被 naive-ui fallback 渲染成空串，placeholder 不展示 */
const query = reactive({ status: null as ReportStatus | null })
const handleDialog = ref(false)
const handleTarget = ref<Report | null>(null)
const handleAction = ref<'handled' | 'ignored'>('handled')
const handling = ref(false)

async function load() {
  const seq = beginLoad()
  loading.value = true
  try {
    const res = await adminApi.adminListReports({
      page: page.value,
      page_size: pageSize.value,
      status: query.status,
    })
    if (!isCurrent(seq)) return
    list.value = res.items
    total.value = res.total
  } catch (e) {
    if (!isCurrent(seq)) return
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}
onMounted(load)
function onFilter() {
  resetPage()
  load()
}

function openHandle(report: Report) {
  handleTarget.value = report
  handleAction.value = 'handled'
  handleDialog.value = true
}
function cancelHandle() {
  handleDialog.value = false
}
async function submitHandle() {
  if (!handleTarget.value) return
  handling.value = true
  try {
    await adminApi.adminHandleReport(handleTarget.value.id, handleAction.value)
    message.success(
      handleAction.value === 'handled'
        ? t('admin.reports.handleSuccess')
        : t('admin.reports.ignored'),
    )
    handleDialog.value = false
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.operationFailed'))
  } finally {
    handling.value = false
  }
}

const statusOptions = computed(() =>
  (Object.keys(REPORT_STATUS) as ReportStatus[]).map((v) => ({
    label: REPORT_STATUS[v].label,
    value: v,
  })),
)

function targetText(row: Report) {
  return row.target_summary ?? `#${row.target_id.slice(0, 8)}`
}

const columns = computed<DataTableColumns<Report>>(() => [
  {
    title: t('admin.reports.type'),
    key: 'target_type',
    width: 90,
    render(row) {
      const type =
        row.target_type === 'comment' ? 'info' : row.target_type === 'post' ? 'warning' : 'primary'
      return h(
        NTag,
        { size: 'small', type, bordered: false },
        { default: () => REPORT_TYPE[row.target_type as ReportType] ?? row.target_type },
      )
    },
  },
  {
    title: t('admin.reports.target'),
    key: 'target',
    minWidth: 220,
    render(row) {
      return h('div', null, [
        h('div', null, targetText(row)),
        h('div', { class: 'cell-muted' }, row.target_id),
      ])
    },
  },
  { title: t('admin.reports.reporter'), key: 'reporter_nickname', width: 120 },
  {
    title: t('admin.reports.reason'),
    key: 'reason',
    minWidth: 180,
    ellipsis: { tooltip: true },
  },
  {
    title: t('admin.reports.status'),
    key: 'status',
    width: 100,
    render(row) {
      const meta = REPORT_STATUS[row.status as ReportStatus]
      return h(
        NTag,
        { size: 'small', type: toNaiveTagType(meta?.tag ?? 'info'), bordered: false },
        { default: () => meta?.label ?? row.status },
      )
    },
  },
  {
    title: t('admin.reports.createdAt'),
    key: 'created_at',
    width: 150,
    render: (row) => formatDateTime(row.created_at),
  },
  {
    title: t('admin.reports.handledAt'),
    key: 'handled_at',
    width: 150,
    render: (row) => formatDateTime(row.handled_at),
  },
  {
    title: t('action.handle'),
    key: 'actions',
    width: 100,
    fixed: 'right',
    render(row) {
      if (row.status !== 'pending')
        return h('span', { class: 'cell-muted' }, t('admin.reports.handled'))
      return h(
        NButton,
        { text: true, type: 'primary', onClick: () => openHandle(row) },
        { default: () => t('action.handle') },
      )
    },
  },
])
</script>

<template>
  <WorkbenchShell>
    <SearchFilterBar :show-search="false">
      <n-select
        v-model:value="query.status"
        clearable
        style="width: 140px"
        :options="statusOptions"
        :placeholder="t('common.allStatus')"
        @update:value="onFilter"
      />
    </SearchFilterBar>

    <PaginatedDataTable
      :columns="columns"
      :data="list"
      :loading="loading"
      :total="total"
      v-model:page="page"
      v-model:page-size="pageSize"
      :page-sizes="[10, 20, 50]"
      :empty-text="t('admin.reports.empty')"
      :table-props="{ scrollX: 1000 }"
      @update:page="
        (p: number) => {
          changePage(p)
          load()
        }
      "
      @update:page-size="
        (s: number) => {
          changeSize(s)
          load()
        }
      "
    />

    <!-- 处理举报 -->
    <n-modal v-model:show="handleDialog" preset="card" style="width: min(440px, 92vw)">
      <n-radio-group v-model:value="handleAction" class="handle-actions">
        <n-radio value="handled">{{ t('admin.reports.approve') }}</n-radio>
        <n-radio value="ignored">{{ t('admin.reports.ignore') }}</n-radio>
      </n-radio-group>
      <template #footer>
        <ModalFooter :loading="handling" @cancel="cancelHandle" @confirm="submitHandle" />
      </template>
    </n-modal>
  </WorkbenchShell>
</template>

<style scoped>
.handle-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
