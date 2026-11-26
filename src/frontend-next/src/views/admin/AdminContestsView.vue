<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus } from '@lucide/vue'

import { adminListContests } from '@/api/admin'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import RowActions from '@/components/teams/RowActions.vue'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { usePagination } from '@/composables/usePagination'
import { formatDateTime } from '@/utils/format'
import { message } from '@/utils/feedback'
import type { ContestSummary } from '@/types'
import ContestStatusBadge from '@/components/contests/ContestStatusBadge.vue'

const router = useRouter()
const { t } = useI18n()

type TypeFilter = 'all' | 'public' | 'team'

const loading = ref(false)
const rows = ref<ContestSummary[]>([])
const keyword = ref('')
const typeFilter = ref<TypeFilter>('all')
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await adminListContests({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      contest_type: typeFilter.value === 'all' ? undefined : typeFilter.value,
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

function changeType(value: string): void {
  typeFilter.value = value as TypeFilter
  onSearch()
}

function openManage(row: ContestSummary): void {
  if (row.status !== 'scheduled') return
  void router.push(`/admin/contests/${row.id}/edit/basic`)
}

function openTools(row: ContestSummary): void {
  void router.push(`/admin/contests/${row.id}/tools`)
}

/** 赛前点进编辑向导；开赛后进赛时工具 */
function openContest(row: ContestSummary): void {
  if (row.status === 'scheduled') openManage(row)
  else openTools(row)
}

onMounted(() => {
  void load()
})

const columns = computed<AppTableColumn<ContestSummary>[]>(() => [
  {
    key: 'title',
    title: t('contests.list.titleLabel'),
    cell: (row) =>
      h('div', { class: 'flex min-w-[220px] items-center gap-2.5' }, [
        h(BaseAvatar, {
          kind: 'contest',
          src: row.logo,
          name: row.title,
          size: 28,
          round: false,
          radius: 6,
          bordered: true,
        }),
        h('div', { class: 'flex min-w-0 items-center gap-2' }, [
          h('span', { class: 'truncate text-[13.5px] font-medium', title: row.title }, row.title),
          row.board_frozen
            ? h(ToneBadge, { tone: 'warning', label: t('contests.boardFrozenTag') })
            : null,
        ]),
      ]),
  },
  {
    key: 'rule_type',
    title: t('contests.list.ruleType'),
    width: '80px',
    cell: (row) => h('span', { class: 'text-[12.5px] text-muted-foreground' }, row.rule_type),
  },
  {
    key: 'contest_type',
    title: t('contests.list.type'),
    width: '90px',
    cell: (row) =>
      h(ToneBadge, {
        tone: row.contest_type === 'team' ? 'warning' : 'info',
        label: t(
          row.contest_type === 'team' ? 'contests.list.typeTeam' : 'contests.list.typePublic',
        ),
      }),
  },
  {
    key: 'status',
    title: t('action.status'),
    width: '100px',
    cell: (row) => h(ContestStatusBadge, { status: row.status }),
  },
  {
    key: 'start_time',
    title: t('contests.list.startTime'),
    width: '150px',
    cell: (row) => formatDateTime(row.start_time),
    cellClass: 'text-[12.5px] text-muted-foreground tabular-nums',
  },
  {
    key: 'end_time',
    title: t('contests.list.endTime'),
    width: '150px',
    cell: (row) => formatDateTime(row.end_time),
    cellClass: 'text-[12.5px] text-muted-foreground tabular-nums',
  },
  {
    key: 'problem_count',
    title: t('contests.list.problems'),
    width: '90px',
    align: 'right',
    cell: (row) => t('contests.list.problemCount', { count: row.problem_count }),
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'ops',
    width: '56px',
    align: 'right',
    cellClass: 'overflow-visible text-clip px-1',
    cell: (row) =>
      h(RowActions, {
        actions: [
          {
            key: 'manage',
            label: t('contests.detail.manage'),
            disabled: row.status !== 'scheduled',
          },
          { key: 'tools', label: t('contests.tools.title') },
        ],
        label: t('action.more'),
        onSelect: (key: string) => (key === 'manage' ? openManage(row) : openTools(row)),
      }),
  },
])

const typeTabs = computed(() => [
  { value: 'all', label: t('contests.list.tabAll') },
  { value: 'public', label: t('contests.list.typePublic') },
  { value: 'team', label: t('contests.list.typeTeam') },
])
</script>

<template>
  <WorkbenchShell :title="t('nav.contestsManage')">
    <template #toolbar>
      <div class="space-y-2.5">
        <SearchFilterBar
          :keyword="keyword"
          :placeholder="t('contests.list.search')"
          search-width="280px"
          @update:keyword="keyword = $event"
          @search="onSearch"
          @reset="onSearch"
        >
          <template #actions>
            <Button size="toolbar" @click="router.push('/admin/contests/create')">
              <Plus class="size-3.5" />
              {{ t('contests.list.create') }}
            </Button>
            <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
          </template>
        <Select
            :model-value="typeFilter"
            @update:model-value="(value) => changeType(String(value))"
          >
            <SelectTrigger class="h-9 w-[130px] text-[13px]">
              <SelectValue :placeholder="t('contests.list.tabAll')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="tab in typeTabs" :key="tab.value" :value="tab.value">
                {{ tab.label }}
              </SelectItem>
            </SelectContent>
          </Select>
        </SearchFilterBar>
      </div>
    </template>

    <PaginatedTable
      :columns="columns"
      :data="rows"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      show-size-picker
      :empty-text="t('contests.list.empty')"
      :row-click="openContest"
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
    >
      <template #pager-left>
        <span class="tabular-nums">{{ t('contests.list.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedTable>
  </WorkbenchShell>
</template>
