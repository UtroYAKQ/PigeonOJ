<script setup lang="ts">
import { computed, h, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

import { adminListTeamContests } from '@/api/admin'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { formatDateTime } from '@/utils/format'
import { useTeamModuleList } from './useTeamModuleList'
import type { ContestSummary } from '@/types'

const props = defineProps<{ teamId: string }>()

const { t } = useI18n()
const { loading, rows, keyword, page, pageSize, total, load, onSearch, onPage, onPageSize } =
  useTeamModuleList<ContestSummary>((query) => adminListTeamContests(props.teamId, query))

const columns = computed<AppTableColumn<ContestSummary>[]>(() => [
  {
    key: 'title',
    title: t('contests.list.titleLabel'),
    cell: (row) => h('span', { class: 'font-medium' }, row.title),
  },
  {
    key: 'rule_type',
    title: t('admin.teams.contestRule'),
    width: '90px',
    cellClass: 'font-mono text-[12px] text-muted-foreground',
  },
  {
    key: 'status',
    title: t('admin.teams.status'),
    width: '100px',
    cell: (row) => {
      if (row.status === 'running') {
        return h(ToneBadge, { tone: 'success', label: t('contests.statusRunning') })
      }
      if (row.status === 'scheduled') {
        return h(ToneBadge, { tone: 'info', label: t('contests.statusScheduled') })
      }
      return h(ToneBadge, { tone: 'default', label: t('contests.statusFinished') })
    },
  },
  {
    key: 'time',
    title: t('admin.teams.contestTime'),
    cell: (row) =>
      h(
        'span',
        { class: 'text-[12.5px] text-muted-foreground' },
        `${formatDateTime(row.start_time)} → ${formatDateTime(row.end_time)}`,
      ),
  },
])

onMounted(load)
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-2.5">
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('contests.list.search')"
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
      :empty-text="t('admin.teams.contestsEmpty')"
      @update:page="onPage"
      @update:page-size="onPageSize"
    >
      <template #pager-left>
        <span class="tabular-nums">{{ t('teams.pane.contestTotal', { count: total }) }}</span>
      </template>
    </PaginatedTable>
  </div>
</template>
