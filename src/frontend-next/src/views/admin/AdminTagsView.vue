<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Plus } from '@lucide/vue'

import { adminArchiveTag, adminListTags } from '@/api/admin'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { usePagination } from '@/composables/usePagination'
import { confirmDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import TagEditorDialog from './tag-components/TagEditorDialog.vue'
import type { ProblemTagItem } from '@/types'

const { t } = useI18n()

const loading = ref(false)
const list = ref<ProblemTagItem[]>([])
const keyword = ref('')
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await adminListTags({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    })
    if (!isCurrent(seq)) return
    list.value = result.items
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

const editorOpen = ref(false)
const editing = ref<ProblemTagItem | null>(null)

function openCreate(): void {
  editing.value = null
  editorOpen.value = true
}

function openEdit(tag: ProblemTagItem): void {
  editing.value = tag
  editorOpen.value = true
}

async function archive(tag: ProblemTagItem): Promise<void> {
  const ok = await confirmDialog({
    title: t('admin.tags.archive'),
    content: t('admin.tags.archiveConfirm', { name: tag.name }),
    positiveText: t('admin.tags.archive'),
    negativeText: t('action.cancel'),
    danger: true,
  })
  if (!ok) return
  try {
    await adminArchiveTag(tag.id)
    message.success(t('admin.tags.archivedSuccess'))
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

const columns = computed<AppTableColumn<ProblemTagItem>[]>(() => [
  {
    key: 'name',
    title: t('admin.tags.name'),
    width: '220px',
    cell: (row) =>
      h(
        Badge,
        {
          variant: 'outline',
          class: 'h-5 px-2 text-[11.5px] font-medium',
          style: row.color
            ? {
                color: row.color,
                borderColor: row.color,
                backgroundColor: `color-mix(in srgb, ${row.color} 10%, transparent)`,
              }
            : undefined,
        },
        { default: () => row.name },
      ),
  },
  {
    key: 'color',
    title: t('admin.tags.color'),
    width: '130px',
    cell: (row) => {
      if (!row.color) return h('span', { class: 'text-[12.5px] text-muted-foreground' }, '—')
      return h('div', { class: 'flex items-center gap-1.5' }, [
        h('span', {
          class: 'inline-block size-3 shrink-0 rounded-[3px] border border-border/60',
          style: { backgroundColor: row.color },
        }),
        h('span', { class: 'font-mono text-[12px] text-muted-foreground' }, row.color),
      ])
    },
  },
  {
    key: 'status',
    title: t('admin.tags.status'),
    width: '100px',
    cell: (row) =>
      h(ToneBadge, {
        tone: row.status === 'archived' ? 'info' : 'success',
        label: t(row.status === 'archived' ? 'admin.tags.archived' : 'admin.tags.active'),
      }),
  },
  {
    key: 'created_at',
    title: t('admin.tags.createdAt'),
    width: '160px',
    cell: (row) => formatDateTime(row.created_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'actions',
    title: t('action.edit'),
    width: '150px',
    align: 'right',
    cell: (row) => {
      const buttons = [
        h(
          Button,
          { variant: 'ghost', size: 'xs', onClick: () => openEdit(row) },
          { default: () => t('action.edit') },
        ),
      ]
      if (row.status !== 'archived') {
        buttons.push(
          h(
            Button,
            {
              variant: 'ghost',
              size: 'xs',
              class: 'text-destructive hover:text-destructive',
              onClick: () => archive(row),
            },
            { default: () => t('admin.tags.archive') },
          ),
        )
      }
      return h('div', { class: 'flex items-center justify-end gap-1' }, buttons)
    },
  },
])

onMounted(load)
</script>

<template>
  <WorkbenchShell :title="t('nav.tags')">
    <template #toolbar>
      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('admin.tags.search')"
        @update:keyword="keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <template #actions>
          <Button size="toolbar" @click="openCreate">
            <Plus class="size-4" />
            {{ t('admin.tags.create') }}
          </Button>
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
        </template>
      </SearchFilterBar>
    </template>

    <PaginatedTable
      :columns="columns"
      :data="list"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      show-size-picker
      :empty-text="t('admin.tags.empty')"
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

    <TagEditorDialog v-model:open="editorOpen" :tag="editing" @saved="load" />
  </WorkbenchShell>
</template>
