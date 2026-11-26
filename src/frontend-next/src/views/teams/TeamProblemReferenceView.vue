<script setup lang="ts">
/**
 * 团队题目引用页（/teams/:teamId/problems/new）：团队题目 = 引用制，
 * 列出本人已发布且未被该团队引用的全站题目（服务端候选），点「引用」进入团队题库。
 */
import { computed, h, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2, RefreshCw } from '@lucide/vue'

import { referenceTeamProblem, searchTeamReferenceableProblems } from '@/api/teams'
import ErrorState from '@/components/common/ErrorState.vue'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { Button } from '@/components/ui/button'
import { usePagination } from '@/composables/usePagination'
import { message } from '@/utils/feedback'
import type { TeamProblemSummary } from '@/types'
import { useTeamAdminGate } from './useTeamAdminGate'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const teamId = String(route.params.teamId)
const {
  allowed,
  loading: gateLoading,
  failed,
  forbidden,
  load: reloadGate,
} = useTeamAdminGate(teamId)

const denied = computed(() => !gateLoading.value && !allowed.value)

const items = ref<TeamProblemSummary[]>([])
const loading = ref(false)
const keyword = ref('')
const referencingId = ref('')
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    // 候选端点已在服务端排除：他人题、未发布、团队题、已被该团队引用过的源题
    const result = await searchTeamReferenceableProblems(teamId, {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    })
    if (!isCurrent(seq)) return
    items.value = result.items
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

function backToTeam(): void {
  void router.replace(`/teams/${teamId}`)
}

async function retryGate(): Promise<void> {
  await reloadGate()
}

async function reference(row: TeamProblemSummary): Promise<void> {
  if (referencingId.value) return
  referencingId.value = row.id
  try {
    await referenceTeamProblem(teamId, { problem_id: row.id, visibility: 'team_visible' })
    message.success(t('teams.space.referenceSuccess'))
    void router.replace(`/teams/${teamId}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    referencingId.value = ''
  }
}

const columns = computed<AppTableColumn<TeamProblemSummary>[]>(() => [
  {
    key: 'title',
    title: t('problems.list.name'),
    cell: (row) => h('span', { class: 'font-medium text-[13.5px]' }, row.title),
  },
  {
    key: 'visibility',
    title: t('problems.list.visibility'),
    width: '100px',
    cell: (row) =>
      (row.visibility as string) === 'public'
        ? h(ToneBadge, { tone: 'success', label: t('problems.visibility.public') })
        : h(ToneBadge, { tone: 'default', label: t('problems.visibility.private') }),
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
    key: 'ops',
    width: '90px',
    align: 'right',
    cell: (row) =>
      h(
        Button,
        {
          size: 'xs',
          variant: 'outline',
          disabled: Boolean(referencingId.value),
          onClick: () => reference(row),
        },
        {
          default: () => [
            referencingId.value === row.id ? h(Loader2, { class: 'size-3 animate-spin' }) : null,
            t('teams.space.reference'),
          ],
        },
      ),
  },
])

// 团队门控通过后再拉候选（避免非成员场景多发一次 403 请求）
watch(
  allowed,
  (value) => {
    if (value) void load()
  },
  { immediate: true },
)
</script>

<template>
  <WorkbenchShell :title="t('teams.space.referenceProblem')">
    <template #actions>
      <Button variant="outline" size="sm" @click="backToTeam">
        {{ t('action.cancel') }}
      </Button>
    </template>

    <div v-if="gateLoading" class="grid min-h-0 flex-1 place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <div
      v-else-if="denied || failed"
      class="grid min-h-0 flex-1 place-items-center rounded-xl border border-border bg-card"
    >
      <ErrorState
        :message="
          failed
            ? forbidden
              ? t('teams.detail.forbidden')
              : t('teams.detail.loadFailed')
            : t('teams.space.referenceNoPermission')
        "
      >
        <template #actions>
          <Button v-if="failed" variant="outline" size="sm" @click="retryGate">
            <RefreshCw class="size-3.5" />
            {{ t('action.refresh') }}
          </Button>
          <Button variant="outline" size="sm" @click="backToTeam">
            {{ t('contests.list.backToTeam') }}
          </Button>
        </template>
      </ErrorState>
    </div>

    <div v-else class="flex min-h-0 flex-1 flex-col gap-2.5">
      <p class="shrink-0 text-[12px] leading-5 text-muted-foreground">
        {{ t('teams.space.referenceProblemHint') }}
      </p>

      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('problems.list.search')"
        search-width="300px"
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
        :data="items"
        :loading="loading"
        :total="total"
        :page="page"
        :page-size="pageSize"
        :empty-text="t('teams.space.referenceEmpty')"
        @update:page="onPageChange"
      >
        <template #pager-left>
          <span class="tabular-nums">{{ t('teams.pane.problemTotal', { count: total }) }}</span>
        </template>
      </PaginatedTable>
    </div>
  </WorkbenchShell>
</template>
