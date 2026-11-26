<script setup lang="ts">
import { computed, h, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

import { adminListTeamProblems } from '@/api/admin'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import type { TagType } from '@/constants/dict'
import { formatDateTime } from '@/utils/format'
import { useTeamModuleList } from './useTeamModuleList'
import type { TeamProblemSummary } from '@/types'

const props = defineProps<{ teamId: string }>()

const { t } = useI18n()
const { loading, rows, keyword, page, pageSize, total, load, onSearch, onPage, onPageSize } =
  useTeamModuleList<TeamProblemSummary>((query) => adminListTeamProblems(props.teamId, query))

const STATUS_META: Record<TeamProblemSummary['status'], { labelKey: string; tone: TagType }> = {
  published: { labelKey: 'problems.list.statusPublished', tone: 'success' },
  draft: { labelKey: 'problems.list.statusDraft', tone: 'warning' },
  archived: { labelKey: 'problems.list.statusArchived', tone: 'info' },
}

const columns = computed<AppTableColumn<TeamProblemSummary>[]>(() => [
  {
    key: 'title',
    title: t('problems.list.name'),
    cell: (row) =>
      h('div', { class: 'flex min-w-0 items-center gap-2' }, [
        h('span', { class: 'min-w-0 truncate font-medium', title: row.title }, row.title),
        h(ToneBadge, {
          tone: row.referenced_at ? 'info' : 'primary',
          label: t(row.referenced_at ? 'admin.teams.referenced' : 'admin.teams.created'),
        }),
      ]),
  },
  {
    key: 'status',
    title: t('admin.teams.status'),
    width: '100px',
    cell: (row) => {
      const meta = STATUS_META[row.status]
      return h(ToneBadge, { tone: meta?.tone ?? 'info', label: t(meta?.labelKey ?? row.status) })
    },
  },
  {
    key: 'limits',
    title: t('admin.teams.problemLimits'),
    width: '160px',
    cell: (row) => `${row.time_limit_ms ?? '--'} ms / ${row.memory_limit_mb ?? '--'} MB`,
    cellClass: 'text-[12.5px] text-muted-foreground tabular-nums',
  },
  {
    key: 'counters',
    title: t('admin.teams.problemSubmissions'),
    width: '130px',
    align: 'center',
    cell: (row) => `${row.submission_count ?? 0} / ${row.accepted_count ?? 0}`,
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'created_at',
    title: t('admin.teams.setCreated'),
    width: '160px',
    cell: (row) => (row.created_at ? formatDateTime(row.created_at) : '--'),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
])

onMounted(load)
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-2.5">
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('admin.teams.problemSearch')"
      @update:keyword="keyword = $event"
      @search="onSearch"
      @reset="onSearch"
    >
      <template #actions>
        <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <PaginatedTable
      :columns="columns"
      :data="rows"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[10, 20, 50]"
      show-size-picker
      :empty-text="t('admin.teams.problemsEmpty')"
      @update:page="onPage"
      @update:page-size="onPageSize"
    >
      <template #pager-left>
        <span class="tabular-nums">{{ t('teams.pane.problemTotal', { count: total }) }}</span>
      </template>
    </PaginatedTable>
  </div>
</template>
