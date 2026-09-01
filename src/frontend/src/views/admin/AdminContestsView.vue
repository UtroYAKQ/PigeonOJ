<script setup lang="ts">
/**
 * 比赛管理（管理后台，admin/tutor；docs/contracts/contests.md）：
 * 全量比赛列表；行点击进入编辑页，创建走全页表单（/admin/contests/create）。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import RefreshButton from '@/components/RefreshButton.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { listContests } from '@/api/contests'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatDateTime } from '@/utils/format'
import type { ContestSummary, PageResult } from '@/types'

const router = useRouter()
const { t } = useI18n()
const loading = ref(false)
const rows = ref<ContestSummary[]>([])
const { page, pageSize, total, changePage, changeSize, beginLoad, isCurrent } = usePagination()
const keyword = ref('')

async function load() {
  const seq = beginLoad()
  loading.value = true
  try {
    const result: PageResult<ContestSummary> = await listContests({
      page: page.value,
      page_size: pageSize.value,
    })
    if (!isCurrent(seq)) return
    rows.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

onMounted(load)

const statusMap = computed(() => ({
  running: { label: t('contests.statusRunning'), type: 'success' as const },
  scheduled: { label: t('contests.statusScheduled'), type: 'info' as const },
  finished: { label: t('contests.statusFinished'), type: 'default' as const },
}))

const columns = computed<DataTableColumns<ContestSummary>>(() => [
  {
    title: t('contests.list.titleLabel'),
    key: 'title',
    minWidth: 260,
    render(row) {
      return h('div', { class: 'contest-name' }, [
        h('strong', null, row.title),
        row.description ? h('span', null, row.description) : null,
      ])
    },
  },
  { title: t('contests.list.ruleType'), key: 'rule_type', width: 80 },
  {
    title: t('contests.statusRunning'),
    key: 'status',
    width: 100,
    render: (row) =>
      h(
        NTag,
        { size: 'small', bordered: false, type: statusMap.value[row.status].type },
        { default: () => statusMap.value[row.status].label },
      ),
  },
  {
    title: t('contests.list.startTime'),
    key: 'start_time',
    width: 170,
    render: (row) => formatDateTime(row.start_time),
  },
  {
    title: t('contests.list.endTime'),
    key: 'end_time',
    width: 170,
    render: (row) => formatDateTime(row.end_time),
  },
  {
    title: t('contests.detail.problems'),
    key: 'problem_count',
    width: 90,
    render: (row) => t('contests.list.problemCount', { count: row.problem_count }),
  },
  {
    title: t('action.edit'),
    key: 'actions',
    width: 90,
    render: () =>
      h(NTag, { size: 'small', bordered: false }, { default: () => t('contests.detail.manage') }),
  },
])

/** 行点击进入向导第一步（基本信息；下一步编排题目） */
function rowProps(row: ContestSummary) {
  return {
    style: 'cursor: pointer;',
    onClick: () => router.push(`/admin/contests/${row.id}/edit/basic`),
  }
}
</script>

<template>
  <WorkbenchShell>
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('contests.list.search')"
      search-width="260px"
      manual
      @update:keyword="
        (v: string) => {
          keyword = v
        }
      "
      @search="load"
      @reset="load"
    >
      <template #actions>
        <n-button type="primary" size="small" @click="router.push('/admin/contests/create')">
          {{ t('contests.list.create') }}
        </n-button>
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <PaginatedDataTable
      :columns="columns"
      :data="rows"
      :loading="loading"
      :total="total"
      v-model:page="page"
      v-model:page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      :empty-text="t('contests.list.empty')"
      :table-props="{ rowProps }"
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
    >
      <template #pager-left>
        <span class="pager__total">{{ t('contests.list.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedDataTable>
  </WorkbenchShell>
</template>

<style scoped>
.contest-name {
  display: grid;
  gap: 4px;
}
.contest-name strong {
  font-size: 14px;
}
.contest-name span {
  color: var(--app-text-secondary);
  font-size: 12px;
}
</style>
