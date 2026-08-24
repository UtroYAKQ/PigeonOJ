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

const { t } = useI18n()
const loading = ref(false)
const list = ref<Report[]>([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 20, status: '' as ReportStatus | '' })
const handleDialog = ref(false)
const handleTarget = ref<Report | null>(null)
const handleAction = ref<'handled' | 'ignored'>('handled')
const handling = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await adminApi.adminListReports(query)
    list.value = res.items
    total.value = res.total
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}
onMounted(load)
function onFilter() {
  query.page = 1
  load()
}
function changePage(page: number) {
  query.page = page
  load()
}
function changeSize(size: number) {
  query.page_size = size
  query.page = 1
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
        h('div', { class: 'cell-target-id' }, row.target_id),
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
      if (row.status !== 'pending') return h('span', { class: 'cell-muted' }, t('admin.reports.handled'))
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
  <div class="page-fill">
    <n-card :title="t('admin.reports.title')" :bordered="false">
    <div class="toolbar">
      <n-select
        v-model:value="query.status"
        clearable
        class="toolbar__filter"
        :options="statusOptions"
        :placeholder="t('common.allStatus')"
        @update:value="onFilter"
      />
    </div>

    <n-data-table
      v-if="loading || list.length"
      class="table-fill"
      :columns="columns"
      :data="list"
      :loading="loading"
      :scroll-x="1000"
      :bordered="false"
    />
    <div v-else class="table-fill-empty">
      <n-empty size="large" :description="t('admin.reports.empty')" />
    </div>

    <div class="pager">
      <n-pagination
        :page="query.page"
        :page-size="query.page_size"
        :item-count="total"
        :page-sizes="[10, 20, 50]"
        show-size-picker
        @update:page="changePage"
        @update:page-size="changeSize"
      />
    </div>

    <!-- 处理举报 -->
    <n-modal
      v-model:show="handleDialog"
      preset="card"
      style="width: min(440px, 92vw)"
      :title="t('admin.reports.handleTitle', { target: handleTarget ? targetText(handleTarget) : '' })"
    >
      <n-radio-group v-model:value="handleAction" class="handle-actions">
        <n-radio value="handled">{{ t('admin.reports.approve') }}</n-radio>
        <n-radio value="ignored">{{ t('admin.reports.ignore') }}</n-radio>
      </n-radio-group>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="cancelHandle">{{ t('action.cancel') }}</n-button>
          <n-button type="primary" :loading="handling" @click="submitHandle">{{
            t('action.confirm')
          }}</n-button>
        </div>
      </template>
    </n-modal>
    </n-card>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}
.toolbar__filter {
  width: 140px;
}
.cell-target-id,
.cell-muted {
  color: var(--app-text-secondary);
  font-size: 12px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
.handle-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
