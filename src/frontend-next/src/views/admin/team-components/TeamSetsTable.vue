<script setup lang="ts">
import { computed, h, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

import { adminListTeamProblemSets } from '@/api/admin'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { formatDateTime } from '@/utils/format'
import { useTeamModuleList } from './useTeamModuleList'
import type { ProblemSetSummary } from '@/types'

const props = defineProps<{ teamId: string }>()

const { t } = useI18n()
const { loading, rows, keyword, page, pageSize, total, load, onSearch, onPage, onPageSize } =
  useTeamModuleList<ProblemSetSummary>((query) => adminListTeamProblemSets(props.teamId, query))

const columns = computed<AppTableColumn<ProblemSetSummary>[]>(() => [
  {
    key: 'title',
    title: t('problemSets.list.titleLabel'),
    cell: (row) => h('span', { class: 'min-w-0 truncate font-medium', title: row.title }, row.title),
  },
  {
    key: 'item_count',
    title: t('admin.teams.setVisible'),
    width: '90px',
    align: 'center',
    cell: (row) => String(row.item_count),
    cellClass: 'tabular-nums',
  },
  {
    key: 'status',
    title: t('problemSets.list.status'),
    width: '100px',
    cell: (row) =>
      row.status === 'active'
        ? h(ToneBadge, { tone: 'success', label: t('problemSets.list.active') })
        : h(ToneBadge, { tone: 'default', label: t('problemSets.detail.archived') }),
  },
  {
    key: 'created_at',
    title: t('admin.teams.setCreated'),
    width: '160px',
    cell: (row) => formatDateTime(row.created_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
])

onMounted(load)
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-2.5">
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('problemSets.list.search')"
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
      :empty-text="t('admin.teams.setsEmpty')"
      @update:page="onPage"
      @update:page-size="onPageSize"
    >
      <template #pager-left>
        <span class="tabular-nums">{{ t('teams.pane.setTotal', { count: total }) }}</span>
      </template>
    </PaginatedTable>
  </div>
</template>
