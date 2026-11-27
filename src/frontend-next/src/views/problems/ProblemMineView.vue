<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, type Component } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Archive, FileArchive, History, Pencil, Plus } from '@lucide/vue'

import { archiveProblem, listProblems } from '@/api/problems'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

import { TooltipHint } from '@/components/ui/tooltip'
import { problemStatusLabelKey } from '@/constants/problemStatus'
import { usePagination } from '@/composables/usePagination'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import type { TagType } from '@/constants/dict'
import type { ProblemSummary } from '@/types'
import FpsTransferDialog from '@/views/problems/components/FpsTransferDialog.vue'

type ProblemStatus = 'draft' | 'published' | 'archived'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const list = ref<ProblemSummary[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()

const query = reactive({
  keyword: '',
  status: '' as ProblemStatus | '',
  ownership: 'all' as 'all' | 'solo' | 'org' | 'team',
})

const statusTabs = [
  { value: 'all', labelKey: 'problems.mine.all' },
  { value: 'draft', labelKey: 'problems.list.statusDraft' },
  { value: 'published', labelKey: 'problems.list.statusPublished' },
  { value: 'archived', labelKey: 'problems.list.statusArchived' },
] as const

const statusTone: Record<string, TagType> = {
  published: 'success',
  archived: 'info',
  draft: 'warning',
}

/** FPS 题库导入 / 导出：同一弹窗双 tab；导出按列表勾选（跨页保留选中） */
const fpsOpen = ref(false)
const selectedKeys = ref<Array<string | number>>([])
const selectedIds = computed(() => selectedKeys.value.map(String))

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listProblems({
      page: page.value,
      page_size: pageSize.value,
      keyword: query.keyword || undefined,
      scope: 'mine',
      status: query.status || undefined,
      ownership: query.ownership === 'all' ? undefined : query.ownership,
    })
    if (!isCurrent(seq)) return
    list.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('problems.list.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

function onSearch(): void {
  resetPage()
  void load()
}

function switchStatus(value: string): void {
  query.status = value === 'all' ? '' : (value as ProblemStatus)
  onSearch()
}

function switchOwnership(value: unknown): void {
  const next = String(value ?? 'all')
  query.ownership = next === 'solo' || next === 'org' || next === 'team' ? next : 'all'
  onSearch()
}

function goEdit(row: ProblemSummary): void {
  void router.push(`/admin/problems/${row.id}/edit/statement`)
}

function goDetail(row: ProblemSummary): void {
  // 管理动线只读预览：留在后台，不进前台写题页
  void router.push(`/admin/problems/${row.id}/preview`)
}

function goSubmissions(row: ProblemSummary): void {
  void router.push(`/admin/problems/${row.id}/submissions`)
}

function doArchive(row: ProblemSummary): void {
  confirmAsyncDialog({
    title: t('problems.detail.archive'),
    content: t('problems.mine.archiveConfirm'),
    positiveText: t('problems.detail.archive'),
    danger: true,
    action: async () => {
      Object.assign(row, await archiveProblem(row.id))
    },
    successMessage: t('problems.detail.archiveSuccess'),
    onAfterSuccess: () => load(),
  })
}

function rowAction(icon: Component, label: string, run: () => void) {
  return h(TooltipHint, { text: label }, () =>
    h(
      Button,
      {
        variant: 'ghost',
        size: 'icon-xs',
        'aria-label': label,
        onClick: (event: MouseEvent) => {
          event.stopPropagation()
          run()
        },
      },
      () => h(icon, { class: 'size-3.5' }),
    ),
  )
}

const columns = computed<AppTableColumn<ProblemSummary>[]>(() => [
  {
    key: 'id',
    title: t('problems.list.id'),
    width: '96px',
    cell: (row) =>
      h(
        'span',
        { class: 'font-mono text-[11.5px] text-muted-foreground', title: row.id },
        row.id.slice(0, 8),
      ),
  },
  {
    key: 'title',
    title: t('problems.list.name'),
    cell: (row) => h('strong', { class: 'text-[13.5px] font-medium' }, row.title),
  },
  {
    key: 'status',
    title: t('problems.list.type'),
    width: '88px',
    cell: (row) =>
      h(ToneBadge, {
        tone: statusTone[row.status] ?? 'info',
        label: t(problemStatusLabelKey[row.status] ?? row.status),
      }),
  },
  {
    key: 'visibility',
    title: t('problems.list.visibility'),
    width: '88px',
    cell: (row) =>
      h(ToneBadge, {
        tone: row.visibility === 'private' ? 'danger' : 'info',
        label: t(`problems.visibility.${row.visibility ?? 'public'}`),
      }),
  },
  {
    key: 'source',
    title: t('problems.list.source'),
    width: '88px',
    cell: (row) => {
      // 团队题（引用快照 / 团队直建）与全站题来源区分
      const isTeam = row.visibility === 'team_visible' || row.visibility === 'admin_visible'
      const isOrg = row.visibility === 'org_visible'
      return h(ToneBadge, {
        tone: isTeam ? 'warning' : 'info',
        label: t(
          isOrg
            ? 'problems.mine.ownershipOrg'
            : isTeam
              ? 'problems.mine.ownershipTeam'
              : 'problems.mine.ownershipSolo',
        ),
      })
    },
  },
  {
    key: 'is_verified',
    title: t('problems.manage.shareTitle'),
    width: '116px',
    cell: (row) => {
      if (row.needs_reverification) {
        return h(ToneBadge, { tone: 'warning', label: t('problems.manage.reverifyTag') })
      }
      if (row.is_verified) {
        return h(ToneBadge, { tone: 'success', label: t('problems.manage.verifiedTag') })
      }
      return h(
        'span',
        { class: 'text-[12px] text-muted-foreground' },
        t('problems.manage.unverifiedTag'),
      )
    },
  },
  {
    key: 'limits',
    title: t('problems.list.limits'),
    width: '150px',
    cell: (row) => `${row.time_limit_ms} ms / ${row.memory_limit_mb} MB`,
    cellClass: 'text-[12.5px] text-muted-foreground tabular-nums',
  },
  {
    key: 'actions',
    title: t('action.edit'),
    width: '100px',
    align: 'right',
    cell: (row) => {
      const buttons = [
        rowAction(History, t('problems.mine.viewSubmissions'), () => goSubmissions(row)),
      ]
      if (row.status !== 'archived') {
        buttons.push(rowAction(Pencil, t('action.edit'), () => goEdit(row)))
      }
      if (row.status === 'published') {
        buttons.push(rowAction(Archive, t('problems.detail.archive'), () => doArchive(row)))
      }
      return h('div', { class: 'flex items-center justify-end gap-0.5' }, buttons)
    },
  },
])

onMounted(load)
</script>

<template>
  <WorkbenchShell :title="t('nav.problemsManage')">
    <template #toolbar>
      <div class="space-y-2.5">
        <SearchFilterBar
          :keyword="query.keyword"
          :placeholder="t('problems.mine.search')"
          search-width="280px"
          @update:keyword="query.keyword = $event"
          @search="onSearch"
          @reset="onSearch"
        >
          <Select :model-value="query.ownership" @update:model-value="switchOwnership($event)">
            <SelectTrigger class="h-9 w-[160px] text-[13px]">
              <SelectValue :placeholder="t('problems.mine.ownershipAll')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{{ t('problems.mine.ownershipAll') }}</SelectItem>
              <SelectItem value="solo">{{ t('problems.mine.ownershipSolo') }}</SelectItem>
              <SelectItem value="org">{{ t('problems.mine.ownershipOrg') }}</SelectItem>
              <SelectItem value="team">{{ t('problems.mine.ownershipTeam') }}</SelectItem>
            </SelectContent>
          </Select>

          <template #actions>
            <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
            <Button variant="outline" size="toolbar" @click="fpsOpen = true">
              <FileArchive class="size-4" />
              {{ t('problems.importFps.button') }}
            </Button>
            <Button size="toolbar" @click="router.push('/admin/problems/new')">
              <Plus class="size-4" />
              {{ t('problems.list.create') }}
            </Button>
          </template>
        <Select
            :model-value="query.status || 'all'"
            @update:model-value="(value) => switchStatus(String(value))"
          >
            <SelectTrigger class="h-9 w-[120px] text-[13px]">
              <SelectValue :placeholder="t('problems.mine.all')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="tab in statusTabs" :key="tab.value" :value="tab.value">
                {{ t(tab.labelKey) }}
              </SelectItem>
            </SelectContent>
          </Select>
        </SearchFilterBar>
      </div>
    </template>

    <PaginatedTable
      :columns="columns"
      :data="list"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      min-width="1072px"
      show-size-picker
      selectable
      :row-key="(row: ProblemSummary) => row.id"
      :selected-keys="selectedKeys"
      :empty-text="t('problems.mine.empty')"
      :row-click="goDetail"
      @update:selected-keys="selectedKeys = $event"
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
        <span class="tabular-nums">{{ t('problems.list.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedTable>

    <FpsTransferDialog v-model:open="fpsOpen" :selected-ids="selectedIds" @imported="load" />
  </WorkbenchShell>
</template>
