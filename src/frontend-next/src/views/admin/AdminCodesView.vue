<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import {
  adminListCodeShares,
  adminSetCodeShareStatus,
  getCodeShare,
} from '@/api/community'
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
import { languageOptions } from '@/constants/languages'
import { usePagination } from '@/composables/usePagination'
import { confirmDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { AdminCodeShare, CodeShareDetail, CodeShareStatus } from '@/types'

const { t } = useI18n()

const items = ref<AdminCodeShare[]>([])
const loading = ref(false)
const keyword = ref('')
const status = ref<'all' | CodeShareStatus>('all')
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()

const previewOpen = ref(false)
const previewLoading = ref(false)
const preview = ref<CodeShareDetail | null>(null)

function languageLabel(value: string): string {
  return languageOptions.find((item) => item.value === value)?.label ?? value
}

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await adminListCodeShares({
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

async function openPreview(row: AdminCodeShare): Promise<void> {
  previewOpen.value = true
  previewLoading.value = true
  preview.value = null
  try {
    preview.value = await getCodeShare(row.id)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('admin.codes.previewNotFound'))
  } finally {
    previewLoading.value = false
  }
}

async function setStatus(row: AdminCodeShare, next: 'published' | 'removed'): Promise<void> {
  if (next === 'removed') {
    const ok = await confirmDialog({
      title: t('admin.codes.removeTitle'),
      content: t('admin.codes.removeConfirm', { title: row.title }),
      positiveText: t('admin.solutions.remove'),
      negativeText: t('action.cancel'),
      danger: true,
    })
    if (!ok) return
  }
  try {
    await adminSetCodeShareStatus(row.id, next)
    message.success(t('common.success'))
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

function actionsFor(row: AdminCodeShare): RowAction[] {
  return [
    { key: 'preview', label: t('admin.codes.preview') },
    row.status === 'published'
      ? { key: 'remove', label: t('admin.solutions.remove'), destructive: true }
      : { key: 'restore', label: t('admin.solutions.restore') },
  ]
}

function onAction(key: string, row: AdminCodeShare): void {
  if (key === 'preview') {
    void openPreview(row)
    return
  }
  void setStatus(row, key === 'remove' ? 'removed' : 'published')
}

const columns = computed<AppTableColumn<AdminCodeShare>[]>(() => [
  {
    key: 'title',
    title: t('admin.codes.title'),
    cell: (row) => h('span', { class: 'font-medium' }, row.title),
  },
  {
    key: 'language',
    title: t('admin.codes.language'),
    width: '120px',
    cell: (row) => h(ToneBadge, { tone: 'info', label: languageLabel(row.language) }),
  },
  {
    key: 'author',
    title: t('admin.codes.author'),
    width: '140px',
    cell: (row) => row.author.nickname,
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'status',
    title: t('admin.codes.status'),
    width: '100px',
    cell: (row) =>
      h(ToneBadge, {
        tone: row.status === 'published' ? 'success' : 'default',
        label:
          row.status === 'published'
            ? t('codes.statusPublished')
            : t('codes.statusRemoved'),
      }),
  },
  {
    key: 'updated_at',
    title: t('admin.codes.updatedAt'),
    width: '160px',
    cell: (row) => formatDateTime(row.updated_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'ops',
    width: '56px',
    align: 'right',
    cellClass: 'overflow-visible text-clip px-1',
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
  <WorkbenchShell :title="t('nav.codesManage')">
    <template #toolbar>
      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('admin.codes.search')"
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
            <SelectValue :placeholder="t('admin.codes.status')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('common.allStatus') }}</SelectItem>
            <SelectItem value="published">{{ t('codes.statusPublished') }}</SelectItem>
            <SelectItem value="removed">{{ t('codes.statusRemoved') }}</SelectItem>
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
      :empty-text="t('admin.codes.empty')"
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
      <DialogContent class="max-h-[86vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{{ preview?.title ?? t('admin.codes.preview') }}</DialogTitle>
          <DialogDescription class="sr-only">{{ t('admin.codes.preview') }}</DialogDescription>
        </DialogHeader>
        <div v-if="previewLoading" class="grid h-40 place-items-center">
          <Loader2 class="size-6 animate-spin text-muted-foreground" />
        </div>
        <template v-else-if="preview">
          <p class="text-[12.5px] text-muted-foreground">
            {{ preview.author.nickname }} · {{ languageLabel(preview.language) }} ·
            {{ formatDateTime(preview.updated_at) }}
          </p>
          <MarkdownView v-if="preview.description" :source="preview.description" />
          <pre
            class="max-h-[420px] overflow-auto whitespace-pre-wrap break-all rounded-lg border border-border bg-code px-4 py-3 font-mono text-[12.5px] leading-6 text-code-foreground"
            >{{ preview.code }}</pre
          >
        </template>
        <p v-else class="py-10 text-center text-[13px] text-muted-foreground">
          {{ t('admin.codes.previewNotFound') }}
        </p>
      </DialogContent>
    </Dialog>
  </WorkbenchShell>
</template>