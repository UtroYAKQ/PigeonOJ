<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus } from '@lucide/vue'

import { archiveProblem } from '@/api/problems'
import { listOrgProblems } from '@/api/orgs'
import FilterCheckbox from '@/components/common/FilterCheckbox.vue'
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

const props = defineProps<{ orgId: string; canManage: boolean }>()

const router = useRouter()
const { t } = useI18n()

const problems = ref<TeamProblemSummary[]>([])
const loading = ref(false)
const keyword = ref('')
const draftOnly = ref(false)
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listOrgProblems(props.orgId, {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      status: draftOnly.value ? 'draft' : undefined,
    })
    if (!isCurrent(seq)) return
    problems.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('orgs.detail.loadFailed'))
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

function onDraftChange(value: boolean): void {
  draftOnly.value = value
  onSearch()
}

function openProblem(row: TeamProblemSummary): void {
  if (draftOnly.value) {
    void router.push(`/orgs/${props.orgId}/problems/${row.id}/edit/statement`)
    return
  }
  void router.push(`/orgs/${props.orgId}/problems/${row.id}`)
}

function openCreate(): void {
  void router.push(`/orgs/${props.orgId}/problems/new`)
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

function onAction(key: string, row: TeamProblemSummary): void {
  if (key === 'edit') {
    void router.push(`/orgs/${props.orgId}/problems/${row.id}/edit/statement`)
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
      cell: (row) => h('span', { class: 'font-medium text-[13.5px]' }, row.title),
    },
    {
      key: 'verified',
      title: t('problems.manage.shareTitle'),
      width: '120px',
      cell: (row) => h(ToneBadge, { tone: verifyTone(row), label: verifyLabel(row) }),
    },
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
  ]
  if (props.canManage) {
    cols.push({
      key: 'ops',
      width: '56px',
      align: 'right',
      cell: (row) =>
        h(RowActions, {
          actions: actionsFor(row),
          label: t('teams.detail.more'),
          onSelect: (key: string) => onAction(key, row),
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
      :placeholder="t('orgs.problems.search')"
      @update:keyword="keyword = $event"
      @search="onSearch"
      @reset="onSearch"
    >
      <template #actions>
        <Button v-if="canManage" variant="outline" size="toolbar" @click="openCreate">
          <Plus class="size-4" />
          {{ t('orgs.problems.create') }}
        </Button>
        <FilterCheckbox
          v-if="canManage"
          id="org-problem-draft"
          :model-value="draftOnly"
          :label="t('orgs.problems.draftBox')"
          @update:model-value="onDraftChange"
        />
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
      :empty-text="t(draftOnly ? 'orgs.problems.draftsEmpty' : 'orgs.problems.empty')"
      :row-click="openProblem"
      @update:page="onPageChange"
    >
      <template #pager-left>
        <span class="tabular-nums">{{ t('teams.pane.problemTotal', { count: total }) }}</span>
      </template>
    </PaginatedTable>
  </div>
</template>
