<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { listContests } from '@/api/contests'
import PaginatedCardGrid from '@/components/common/PaginatedCardGrid.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import ContestCard from '@/components/contests/ContestCard.vue'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { usePagination } from '@/composables/usePagination'
import { message } from '@/utils/feedback'
import type { ContestStatusType, ContestSummary } from '@/types'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const rows = ref<ContestSummary[]>([])
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

const keyword = ref('')
const statusFilter = ref<ContestStatusType | null>(null)

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listContests({
      page: page.value,
      page_size: pageSize.value,
      status: statusFilter.value ?? undefined,
      keyword: keyword.value || undefined,
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

function onSearch(): void {
  resetPage()
  void load()
}

function onStatusChange(value: unknown): void {
  const next = String(value ?? 'all')
  statusFilter.value = next === 'all' ? null : (next as ContestStatusType)
  onSearch()
}

function onPageChange(value: number): void {
  if (value === page.value) return
  changePage(value)
  void load()
}

function openContest(row: ContestSummary): void {
  void router.push(`/contests/${row.id}`)
}

onMounted(() => {
  void load()
})
</script>

<template>
  <WorkbenchShell :title="t('nav.contests')">
    <template #toolbar>
      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('contests.list.search')"
        search-width="300px"
        @update:keyword="keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <Select :model-value="statusFilter ?? 'all'" @update:model-value="onStatusChange">
          <SelectTrigger class="h-9 w-[136px] text-[13px]">
            <SelectValue :placeholder="t('common.allStatus')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('common.allStatus') }}</SelectItem>
            <SelectItem value="running">{{ t('contests.statusRunning') }}</SelectItem>
            <SelectItem value="scheduled">{{ t('contests.statusScheduled') }}</SelectItem>
            <SelectItem value="finished">{{ t('contests.statusFinished') }}</SelectItem>
          </SelectContent>
        </Select>

        <template #actions>
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
        </template>
      </SearchFilterBar>
    </template>

    <PaginatedCardGrid
      :items="rows"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :empty-text="t('contests.list.empty')"
      @update:page="onPageChange"
    >
      <template #default="{ item }">
        <ContestCard :contest="item" @open="openContest" />
      </template>
      <template #pager-left>
        <span class="tabular-nums">{{ t('contests.list.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedCardGrid>
  </WorkbenchShell>
</template>
