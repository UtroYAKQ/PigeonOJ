<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import {
  adminListSolutions,
  adminSetSolutionStatus,
  getSolution,
} from '@/api/community'
import CommentThread from '@/components/community/CommentThread.vue'
import MarkdownView from '@/components/common/MarkdownView.vue'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import RowActions from '@/components/teams/RowActions.vue'
import type { RowAction } from '@/components/teams/types'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { usePagination } from '@/composables/usePagination'
import { confirmDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { AdminSolution, SolutionDetail, SolutionStatus } from '@/types'

const { t } = useI18n()

const items = ref<AdminSolution[]>([])
const loading = ref(false)
const keyword = ref('')
const status = ref<'all' | SolutionStatus>('all')
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()

const previewOpen = ref(false)
const previewLoading = ref(false)
const preview = ref<SolutionDetail | null>(null)

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await adminListSolutions({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      status: status.value === 'all' ? undefined : status.value,
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

async function openPreview(row: AdminSolution): Promise<void> {
  previewOpen.value = true
  previewLoading.value = true
  preview.value = null
  try {
    preview.value = await getSolution(row.id)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('admin.solutions.previewNotFound'))
  } finally {
    previewLoading.value = false
  }
}

async function setStatus(row: AdminSolution, next: 'published' | 'removed'): Promise<void> {
  if (next === 'removed') {
    const ok = await confirmDialog({
      title: t('admin.solutions.removeTitle'),
      content: t('admin.solutions.removeConfirm', { title: row.title }),
      positiveText: t('admin.solutions.remove'),
      negativeText: t('action.cancel'),
      danger: true,
    })
    if (!ok) return
  }
  try {
    await adminSetSolutionStatus(row.id, next)
    message.success(t('common.success'))
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

function actionsFor(row: AdminSolution): RowAction[] {
  return [
    { key: 'preview', label: t('admin.solutions.preview') },
    row.status === 'published'
      ? { key: 'remove', label: t('admin.solutions.remove'), destructive: true }
      : { key: 'restore', label: t('admin.solutions.restore') },
  ]
}

function onAction(key: string, row: AdminSolution): void {
  if (key === 'preview') {
    void openPreview(row)
    return
  }
  void setStatus(row, key === 'remove' ? 'removed' : 'published')
}

const columns = computed<AppTableColumn<AdminSolution>[]>(() => [
  {
    key: 'title',
    title: t('admin.solutions.title'),
    cell: (row) => h('span', { class: 'font-medium' }, row.title),
  },
  {
    key: 'problem',
    title: t('admin.solutions.problem'),
    width: '220px',
    cell: (row) => row.problem.title,
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'author',
    title: t('admin.solutions.author'),
    width: '140px',
    cell: (row) => row.author.nickname,
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'comment_count',
    title: t('admin.solutions.commentCount'),
    width: '90px',
    align: 'right',
    cell: (row) => String(row.comment_count),
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'status',
    title: t('admin.solutions.status'),
    width: '100px',
    cell: (row) =>
      h(ToneBadge, {
        tone: row.status === 'published' ? 'success' : 'default',
        label:
          row.status === 'published'
            ? t('problems.solutions.status.published')
            : t('problems.solutions.status.removed'),
      }),
  },
  {
    key: 'updated_at',
    title: t('admin.solutions.updatedAt'),
    width: '160px',
    cell: (row) => formatDateTime(row.updated_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'ops',
    width: '56px',
    align: 'right',
    cell: (row) =>
      h(RowActions, {
        actions: actionsFor(row),
        label: t('action.more'),
        onSelect: (key: string) => onAction(key, row),
      }),
  },
])

onMounted(load)
</script>

<template>
  <WorkbenchShell :title="t('nav.solutionsManage')">
    <template #toolbar>
      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('admin.solutions.search')"
        @update:keyword="keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <Select
          :model-value="status"
          @update:model-value="
            (value) => {
              status = value as typeof status
              onSearch()
            }
          "
        >
          <SelectTrigger class="h-9 w-[130px] text-[13px]">
            <SelectValue :placeholder="t('admin.solutions.status')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('common.allStatus') }}</SelectItem>
            <SelectItem value="published">
              {{ t('problems.solutions.status.published') }}
            </SelectItem>
            <SelectItem value="removed">
              {{ t('problems.solutions.status.removed') }}
            </SelectItem>
          </SelectContent>
        </Select>
        <template #actions>
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
        </template>
      </SearchFilterBar>
    </template>

    <PaginatedTable
      :columns="columns"
      :data="items"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      show-size-picker
      :empty-text="t('admin.solutions.empty')"
      :row-click="openPreview"
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
    />

    <Dialog v-model:open="previewOpen">
      <DialogContent class="max-h-[86vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>{{ preview?.title ?? t('admin.solutions.preview') }}</DialogTitle>
          <DialogDescription class="sr-only">{{ t('admin.solutions.preview') }}</DialogDescription>
        </DialogHeader>
        <div v-if="previewLoading" class="grid h-40 place-items-center">
          <Loader2 class="size-6 animate-spin text-muted-foreground" />
        </div>
        <template v-else-if="preview">
          <p class="text-[12.5px] text-muted-foreground">
            {{ preview.problem_id }} · {{ preview.author.nickname }} ·
            {{ formatDateTime(preview.updated_at) }}
          </p>
          <MarkdownView :source="preview.content" />
          <CommentThread
            target-type="solution"
            :target-id="preview.id"
            admin-mode
          />
        </template>
        <p v-else class="py-10 text-center text-[13px] text-muted-foreground">
          {{ t('admin.solutions.previewNotFound') }}
        </p>
      </DialogContent>
    </Dialog>
  </WorkbenchShell>
</template>