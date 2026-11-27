<script setup lang="ts">
import { computed, h, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { listActiveTagsPaged } from '@/api/problems'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { usePagination } from '@/composables/usePagination'
import type { ProblemTagItem } from '@/types'

const props = defineProps<{
  show: boolean
  /** 已选标签名：用于去重与「已添加」禁用态 */
  chosenNames?: Set<string>
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  select: [tag: ProblemTagItem]
}>()

const { t } = useI18n()

const keyword = ref('')
const items = ref<ProblemTagItem[]>([])
const loading = ref(false)
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listActiveTagsPaged({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    })
    if (!isCurrent(seq)) return
    items.value = result.items
    total.value = result.total
  } catch {
    if (!isCurrent(seq)) return
    items.value = []
    total.value = 0
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

watch(
  () => props.show,
  (show) => {
    if (!show) return
    keyword.value = ''
    resetPage()
    void load()
  },
)

function onSearch(): void {
  resetPage()
  void load()
}

function onPage(value: number): void {
  changePage(value)
  void load()
}

const columns = computed<AppTableColumn<ProblemTagItem>[]>(() => {
  // 在 computed 求值时读取，确保父级已选集合变化能驱动列重新渲染
  const chosen = props.chosenNames
  return [
    {
      key: 'name',
      title: t('problems.create.tags'),
      cell: (row) =>
        h(
          'span',
          {
            class:
              'inline-flex h-5 items-center rounded-md border px-1.5 text-[11.5px] text-muted-foreground',
            style: row.color ? { borderColor: `${row.color}55`, color: row.color } : undefined,
          },
          row.name,
        ),
    },
    {
      key: 'color',
      title: t('problems.create.tagColor'),
      width: '140px',
      cell: (row) => {
        if (!row.color) return '—'
        return h('span', { class: 'flex items-center gap-1.5 font-mono text-[12px]' }, [
          h('span', {
            class: 'inline-block size-3 rounded-none',
            style: { backgroundColor: row.color },
          }),
          row.color,
        ])
      },
    },
    {
      key: 'actions',
      width: '96px',
      align: 'right',
      cell: (row) => {
        const added = chosen?.has(row.name) ?? false
        return h(
          Button,
          {
            variant: added ? 'outline' : 'default',
            size: 'xs',
            disabled: added,
            onClick: () => emit('select', row),
          },
          () => (added ? t('problemSets.form.added') : t('problems.create.selectTag')),
        )
      },
    },
  ]
})
</script>

<template>
  <Dialog :open="props.show" @update:open="emit('update:show', $event)">
    <DialogContent class="w-full max-w-[620px] gap-4">
      <DialogHeader>
        <DialogTitle class="text-[15px] font-semibold">
          {{ t('problems.create.selectTagTitle') }}
        </DialogTitle>
        <DialogDescription class="sr-only">
          {{ t('problems.create.selectTagTitle') }}
        </DialogDescription>
      </DialogHeader>

      <div class="flex flex-wrap items-center gap-2">
        <Input
          v-model="keyword"
          class="h-9 max-w-[320px] text-[13px]"
          :placeholder="t('problems.create.searchTagPlaceholder')"
          @keyup.enter="onSearch"
        />
        <Button variant="outline" size="toolbar" @click="onSearch">
          {{ t('action.search') }}
        </Button>
      </div>

      <div class="flex h-[320px] flex-col">
        <PaginatedTable
          :columns="columns"
          :data="items"
          :loading="loading"
          :total="total"
          :page="page"
          :page-size="pageSize"
          :empty-text="t('problems.create.noTagsFound')"
          @update:page="onPage"
        />
      </div>
    </DialogContent>
  </Dialog>
</template>
