<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus } from '@lucide/vue'

import { listTeamContests } from '@/api/teams'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import ContestStatusBadge from '@/components/contests/ContestStatusBadge.vue'
import RowActions from '@/components/teams/RowActions.vue'
import type { RowAction } from '@/components/teams/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { usePagination } from '@/composables/usePagination'
import { message } from '@/utils/feedback'
import type { ContestSummary } from '@/types'

type ContestAction = 'manage' | 'tools'

const props = defineProps<{
  teamId: string
  isAdmin: boolean
}>()

const router = useRouter()
const { t } = useI18n()

const contests = ref<ContestSummary[]>([])
const loading = ref(false)
const keyword = ref('')
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

function formatCompact(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listTeamContests(props.teamId, {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    })
    if (!isCurrent(seq)) return
    contests.value = result.items
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

function onPageChange(value: number): void {
  changePage(value)
  void load()
}

function openContest(row: ContestSummary): void {
  // 限界上下文：留在团队路由前缀内
  void router.push(`/teams/${props.teamId}/contests/${row.id}`)
}

function openCreate(): void {
  void router.push(`/teams/${props.teamId}/contests/new`)
}

function actionsFor(row: ContestSummary): RowAction[] {
  return [
    {
      key: 'manage',
      label: t('contests.detail.manage'),
      disabled: row.status !== 'scheduled',
    },
    { key: 'tools', label: t('contests.tools.title') },
  ]
}

function onAction(key: ContestAction, row: ContestSummary): void {
  if (key === 'manage') {
    if (row.status !== 'scheduled') return
    void router.push(`/teams/${props.teamId}/contests/${row.id}/edit/basic`)
    return
  }
  void router.push(`/teams/${props.teamId}/contests/${row.id}/tools`)
}

const columns = computed<AppTableColumn<ContestSummary>[]>(() => {
  const cols: AppTableColumn<ContestSummary>[] = [
    {
      key: 'title',
      title: t('contests.list.titleLabel'),
      cell: (row) =>
        h('div', { class: 'flex min-w-0 items-center gap-2.5 py-0.5' }, [
          h(BaseAvatar, {
            kind: 'contest',
            src: row.logo,
            name: row.title,
            size: 32,
            round: false,
            radius: 8,
            bordered: true,
          }),
          h('div', { class: 'min-w-0 space-y-0.5' }, [
            h('div', { class: 'flex flex-wrap items-center gap-1.5' }, [
              h('span', { class: 'text-[13.5px] font-medium' }, row.title),
              row.board_frozen
                ? h(ToneBadge, { tone: 'warning', label: t('contests.boardFrozenTag') })
                : null,
            ]),
            h(
              'div',
              { class: 'max-w-[420px] truncate text-[12px] text-muted-foreground' },
              row.description || '—',
            ),
          ]),
        ]),
    },
    {
      key: 'status',
      title: t('problems.detail.status'),
      width: '110px',
      cell: (row) => h(ContestStatusBadge, { status: row.status }),
    },
    {
      key: 'rule',
      title: t('contests.list.ruleType'),
      width: '84px',
      cell: (row) =>
        h(
          Badge,
          { variant: 'outline', class: 'h-5 border px-2 text-[11.5px]' },
          () => row.rule_type,
        ),
    },
    {
      key: 'problems',
      title: t('contests.list.problems'),
      width: '90px',
      align: 'center',
      cell: (row) => t('contests.list.problemCount', { count: row.problem_count }),
      cellClass: 'tabular-nums text-muted-foreground',
    },
    {
      key: 'registered',
      title: t('contests.detail.registeredCount'),
      width: '100px',
      align: 'center',
      cell: (row) => t('contests.list.registeredCount', { count: row.registered_count }),
      cellClass: 'tabular-nums text-muted-foreground',
    },
    {
      key: 'schedule',
      title: t('contests.detail.schedule'),
      width: '190px',
      cell: (row) => `${formatCompact(row.start_time)} → ${formatCompact(row.end_time)}`,
      cellClass: 'text-[12.5px] text-muted-foreground tabular-nums',
    },
  ]

  if (props.isAdmin) {
    cols.push({
      key: 'ops',
      width: '56px',
      align: 'right',
      cell: (row) =>
        h(RowActions, {
          actions: actionsFor(row),
          label: t('teams.detail.more'),
          onSelect: (key: string) => onAction(key as ContestAction, row),
        }),
    })
  }

  return cols
})

onMounted(load)
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3">
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('contests.list.search')"
      @update:keyword="keyword = $event"
      @search="onSearch"
      @reset="onSearch"
    >
      <template #actions>
        <Button v-if="isAdmin" size="toolbar" @click="openCreate">
          <Plus class="size-4" />
          {{ t('teams.space.createContest') }}
        </Button>
        <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <PaginatedTable
      :columns="columns"
      :data="contests"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :empty-text="t('teams.space.contestsEmpty')"
      :row-click="openContest"
      @update:page="onPageChange"
    >
      <template #pager-left>
        <span class="tabular-nums">{{ t('teams.pane.contestTotal', { count: total }) }}</span>
      </template>
    </PaginatedTable>
  </div>
</template>
