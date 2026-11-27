<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { UserPlus } from '@lucide/vue'

import { archiveProblem } from '@/api/problems'
import { listTeamProblems } from '@/api/teams'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import RowActions from '@/components/teams/RowActions.vue'
import type { RowAction } from '@/components/teams/types'
import { Button } from '@/components/ui/button'
import { usePagination } from '@/composables/usePagination'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import type { TagType } from '@/constants/dict'
import type { TeamProblemSummary } from '@/types'

type ProblemAction = 'edit' | 'archive'

const props = defineProps<{
  teamId: string
  isAdmin: boolean
}>()

const router = useRouter()
const { t } = useI18n()

const problems = ref<TeamProblemSummary[]>([])
const loading = ref(false)
const keyword = ref('')
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listTeamProblems(props.teamId, {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    })
    if (!isCurrent(seq)) return
    problems.value = result.items
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

function openProblem(row: TeamProblemSummary): void {
  void router.push(`/teams/${props.teamId}/problems/${row.id}`)
}

function openReference(): void {
  void router.push(`/teams/${props.teamId}/problems/new`)
}

function verifyTone(row: TeamProblemSummary): TagType {
  if (row.is_verified && row.needs_reverification) return 'warning'
  return row.is_verified ? 'success' : 'info'
}

function verifyLabel(row: TeamProblemSummary): string {
  if (row.is_verified && row.needs_reverification) return t('problems.manage.reverifyTag')
  return t(row.is_verified ? 'problems.manage.verifiedTag' : 'problems.manage.unverifiedTag')
}

function actionsFor(row: TeamProblemSummary): RowAction[] {
  const actions: RowAction[] = [{ key: 'edit', label: t('action.edit') }]
  if (row.status === 'published') {
    actions.push({
      key: 'archive',
      label: t('problems.detail.archive'),
      destructive: true,
    })
  }
  return actions
}

function onAction(key: ProblemAction, row: TeamProblemSummary): void {
  if (key === 'edit') {
    void router.push(`/teams/${props.teamId}/problems/${row.id}/edit/statement`)
    return
  }
  confirmAsyncDialog({
    title: t('problems.detail.archive'),
    content: t('problems.mine.archiveConfirm'),
    positiveText: t('problems.detail.archive'),
    danger: true,
    action: () => archiveProblem(row.id),
    successMessage: t('problems.detail.archiveSuccess'),
    onAfterSuccess: () => load(),
  })
}

const columns = computed<AppTableColumn<TeamProblemSummary>[]>(() => {
  const cols: AppTableColumn<TeamProblemSummary>[] = [
    {
      key: 'title',
      title: t('problems.list.name'),
      cell: (row) =>
        h('div', { class: 'flex flex-wrap items-center gap-2 py-0.5' }, [
          h('span', { class: 'font-medium text-[13.5px]' }, row.title),
          row.visibility === 'admin_visible'
            ? h(ToneBadge, { tone: 'warning', label: t('problems.visibility.admin_visible') })
            : null,
        ]),
    },
  ]

  if (props.isAdmin) {
    cols.push({
      key: 'verified',
      title: t('problems.manage.shareTitle'),
      width: '120px',
      cell: (row) => h(ToneBadge, { tone: verifyTone(row), label: verifyLabel(row) }),
    })

  }

  cols.push(
    {
      key: 'difficulty',
      title: t('problems.list.difficulty'),
      width: '80px',
      align: 'center',
      cell: (row) => ((row.difficulty ?? null) === null ? '--' : String(row.difficulty)),
      cellClass: 'tabular-nums text-muted-foreground',
    },
    {
      key: 'limits',
      title: t('problems.list.limits'),
      width: '150px',
      cell: (row) => `${row.time_limit_ms ?? '--'} ms / ${row.memory_limit_mb ?? '--'} MB`,
      cellClass: 'text-[12.5px] text-muted-foreground tabular-nums',
    },
    {
      key: 'rate',
      title: t('problems.list.passRate'),
      width: '110px',
      align: 'center',
      cell: (row) => {
        const submitted = row.submission_count ?? 0
        if (!submitted) return '--'
        return `${row.accepted_count ?? 0}/${submitted}`
      },
      cellClass: 'tabular-nums text-muted-foreground',
    },
  )

  if (props.isAdmin) {
    cols.push({
      key: 'ops',
      width: '56px',
      align: 'right',
      cell: (row) =>
        h(RowActions, {
          actions: actionsFor(row),
          label: t('teams.detail.more'),
          onSelect: (key: string) => onAction(key as ProblemAction, row),
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
      :placeholder="t('teams.space.problemSearch')"
      @update:keyword="keyword = $event"
      @search="onSearch"
      @reset="onSearch"
    >
      <template #actions>
        <Button
          v-if="isAdmin"
          variant="outline"
          size="sm"
          class="h-9"
          @click="openReference"
        >
          <UserPlus class="size-4" />
          {{ t('teams.space.referenceProblem') }}
        </Button>
        <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <PaginatedTable
      :columns="columns"
      :data="problems"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :empty-text="t('teams.space.problemsEmpty')"
      :row-click="openProblem"
      @update:page="onPageChange"
    >
      <template #pager-left>
        <span class="tabular-nums">{{ t('teams.pane.problemTotal', { count: total }) }}</span>
      </template>
    </PaginatedTable>
  </div>
</template>
