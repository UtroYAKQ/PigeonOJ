<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus } from '@lucide/vue'

import { archiveTeamProblemSet, listTeamProblemSets } from '@/api/teams'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import type { AppTableColumn } from '@/components/common/table-types'

import RowActions from '@/components/teams/RowActions.vue'
import type { RowAction } from '@/components/teams/types'
import { Button } from '@/components/ui/button'
import { usePagination } from '@/composables/usePagination'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import type { ProblemSetSummary } from '@/types'

type SetAction = 'arrange' | 'archive'

const props = defineProps<{
  teamId: string
  isAdmin: boolean
}>()

const router = useRouter()
const { t } = useI18n()

const sets = ref<ProblemSetSummary[]>([])
const loading = ref(false)
const keyword = ref('')
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listTeamProblemSets(props.teamId, {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    })
    if (!isCurrent(seq)) return
    sets.value = result.items
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

function openSet(row: ProblemSetSummary): void {
  void router.push(`/teams/${props.teamId}/sets/${row.id}`)
}

function openCreate(): void {
  void router.push(`/teams/${props.teamId}/sets/new`)
}

function actionsFor(row: ProblemSetSummary): RowAction[] {
  const actions: RowAction[] = [{ key: 'arrange', label: t('teams.space.arrange') }]
  if (row.status === 'active') {
    actions.push({
      key: 'archive',
      label: t('teams.space.archiveSet'),
      destructive: true,
    })
  }
  return actions
}

function onAction(key: SetAction, row: ProblemSetSummary): void {
  if (key === 'arrange') {
    void router.push(`/teams/${props.teamId}/sets/${row.id}/arrange`)
    return
  }
  confirmAsyncDialog({
    title: t('teams.space.archiveSet'),
    content: t('teams.space.archiveSetConfirm', { title: row.title }),
    positiveText: t('teams.space.archiveSet'),
    danger: true,
    action: () => archiveTeamProblemSet(props.teamId, row.id),
    successMessage: t('teams.space.setArchived'),
    onAfterSuccess: () => load(),
  })
}

const columns = computed<AppTableColumn<ProblemSetSummary>[]>(() => {
  const cols: AppTableColumn<ProblemSetSummary>[] = [
    {
      key: 'title',
      title: t('problemSets.list.titleLabel'),
      cell: (row) => h('span', { class: 'font-medium text-[13.5px]' }, row.title),
    },
    {
      key: 'item_count',
      title: t('admin.teams.setVisible'),
      width: '90px',
      align: 'center',
      cell: (row) => t('teams.space.itemCount', { count: row.item_count }),
      cellClass: 'tabular-nums text-muted-foreground',
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
          onSelect: (key: string) => onAction(key as SetAction, row),
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
      :placeholder="t('problemSets.list.search')"
      @update:keyword="keyword = $event"
      @search="onSearch"
      @reset="onSearch"
    >
      <template #actions>
        <Button v-if="isAdmin" size="toolbar" @click="openCreate">
          <Plus class="size-4" />
          {{ t('teams.space.createSet') }}
        </Button>
        <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <PaginatedTable
      :columns="columns"
      :data="sets"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :empty-text="t('teams.space.setsEmpty')"
      :row-click="openSet"
      @update:page="onPageChange"
    >
      <template #pager-left>
        <span class="tabular-nums">{{ t('teams.pane.setTotal', { count: total }) }}</span>
      </template>
    </PaginatedTable>
  </div>
</template>
