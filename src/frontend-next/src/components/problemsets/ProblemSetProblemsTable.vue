<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import ColumnLineList from '@/components/common/ColumnLineList.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { renderSolveMark } from '@/utils/solveMark'
import type { ProblemSetItem } from '@/types'

const props = withDefaults(defineProps<{ items: ProblemSetItem[]; emptyText?: string }>(), {
  emptyText: '',
})

const emit = defineEmits<{ open: [item: ProblemSetItem] }>()
const { t } = useI18n()

function limits(item: ProblemSetItem): string {
  return `${item.time_limit_ms ?? '--'} ms / ${item.memory_limit_mb ?? '--'} MB`
}

function difficulty(item: ProblemSetItem): string {
  return (item.difficulty ?? null) === null ? '--' : String(item.difficulty)
}

const columns = computed<AppTableColumn<ProblemSetItem>[]>(() => [
  {
    key: 'order',
    title: t('problemSets.detail.orderLabel'),
    width: '64px',
    cell: (_item, index) => String(index + 1),
    cellClass: 'text-[12px] tabular-nums text-muted-foreground',
  },
  {
    key: 'solved',
    title: '',
    width: '52px',
    cell: (item) => renderSolveMark(t, item.solved),
  },
  {
    key: 'title',
    title: t('problemSets.list.titleLabel'),
    cell: (item) => item.title,
    cellClass: 'font-medium',
  },
  {
    key: 'limits',
    title: t('problems.list.limits'),
    width: '180px',
    cell: (item) => limits(item),
    cellClass: 'text-[12.5px] tabular-nums text-muted-foreground',
  },
  {
    key: 'difficulty',
    title: t('problemSets.detail.difficulty'),
    width: '90px',
    cell: (item) => difficulty(item),
    cellClass: 'text-[12.5px] tabular-nums text-muted-foreground',
  },
])
</script>

<template>
  <ColumnLineList
    :columns="columns"
    :items="props.items"
    :row-click="(item) => emit('open', item)"
    :empty-text="emptyText || t('problemSets.detail.empty')"
  />
</template>
