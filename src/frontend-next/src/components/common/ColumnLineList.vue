<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import LineList from '@/components/common/LineList.vue'
import VNodeContent from '@/components/common/VNodeContent'
import type { AppTableColumn } from '@/components/common/table-types'

/**
 * 列驱动的横线列表：由 AppTableColumn 生成表头与逐行单元格，统一交给 LineList。
 * 不分页的列表直接使用；分页列表用 PaginatedTable（本组件 + 分页开关）。
 */
const props = withDefaults(
  defineProps<{
    columns: AppTableColumn<any>[]
    items: any[]
    loading?: boolean
    total?: number
    page?: number
    pageSize?: number
    pageSizes?: number[]
    showSizePicker?: boolean
    showPager?: boolean
    emptyText?: string
    skeletonCount?: number
    rowClick?: (row: any) => void
    rowClass?: (row: any) => string
    selectable?: boolean
    rowKey?: (row: any) => string | number
    selectedKeys?: Array<string | number>
    minWidth?: string
  }>(),
  { selectedKeys: () => [] },
)

type ColumnLineListEmits = {
  'update:page': [value: number]
  'update:pageSize': [value: number]
  'update:selectedKeys': [value: Array<string | number>]
}

const emit = defineEmits<ColumnLineListEmits>()

const { t } = useI18n()

const gridTemplateColumns = computed(() => {
  const columns = props.columns.map((column) => column.width ?? 'minmax(0, 1fr)')
  if (props.selectable) columns.unshift('40px')
  return columns.join(' ')
})

const selectedSet = computed(() => new Set(props.selectedKeys))

function keyOf(row: any, index: number): string | number {
  return props.rowKey ? props.rowKey(row) : index
}

const pageKeys = computed(() => props.items.map((row, index) => keyOf(row, index)))
const selectedOnPage = computed(() => pageKeys.value.filter((key) => selectedSet.value.has(key)))
const allSelected = computed(
  () => pageKeys.value.length > 0 && selectedOnPage.value.length === pageKeys.value.length,
)
const someSelected = computed(
  () => selectedOnPage.value.length > 0 && selectedOnPage.value.length < pageKeys.value.length,
)

function toggleAll(checked: boolean): void {
  const next = new Set(props.selectedKeys)
  for (const key of pageKeys.value) {
    if (checked) next.add(key)
    else next.delete(key)
  }
  emit('update:selectedKeys', [...next])
}

function toggleRow(row: any, index: number): void {
  const key = keyOf(row, index)
  const next = new Set(props.selectedKeys)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  emit('update:selectedKeys', [...next])
}

function onToggleAll(event: Event): void {
  toggleAll((event.target as HTMLInputElement).checked)
}

function onRowKeydown(event: KeyboardEvent, row: any): void {
  if (event.target instanceof HTMLInputElement) return
  if (event.key !== 'Enter' && event.key !== ' ') return
  event.preventDefault()
  props.rowClick?.(row)
}

function alignClass(column: AppTableColumn<any>): string {
  if (column.align === 'right') return 'text-right'
  if (column.align === 'center') return 'text-center'
  return ''
}
</script>

<template>
  <LineList
    :items="items"
    :loading="loading"
    :total="total ?? items.length"
    :page="page ?? 1"
    :page-size="pageSize ?? items.length"
    :page-sizes="pageSizes"
    :show-size-picker="showSizePicker"
    :show-pager="showPager"
    :empty-text="emptyText"
    :skeleton-count="skeletonCount"
    :min-width="minWidth"
    @update:page="emit('update:page', $event)"
    @update:page-size="emit('update:pageSize', $event)"
  >
    <template #header>
      <div
        class="grid items-center gap-3 px-3 pb-2 text-xs font-medium text-muted-foreground"
        :style="{ gridTemplateColumns }"
      >
        <div v-if="selectable" class="flex items-center">
          <input
            type="checkbox"
            class="size-3.5 accent-foreground"
            :aria-label="t('action.selectAll')"
            :checked="allSelected"
            :indeterminate="someSelected"
            @change="onToggleAll"
          />
        </div>
        <span
          v-for="column in columns"
          :key="column.key"
          class="min-w-0 truncate"
          :class="[column.headerClass, alignClass(column)]"
        >
          {{ column.title }}
        </span>
      </div>
    </template>

    <template #skeleton>
      <div
        v-for="index in skeletonCount ?? 6"
        :key="`skeleton-${index}`"
        class="grid items-center gap-3 px-3 py-4"
        :style="{ gridTemplateColumns }"
      >
        <div v-if="selectable" class="size-3.5 animate-pulse rounded bg-muted" />
        <div
          v-for="column in columns"
          :key="column.key"
          class="h-3.5 w-full max-w-[160px] animate-pulse rounded bg-muted"
        />
      </div>
    </template>

    <template #item="{ item, index }">
      <div
        class="grid w-full items-center gap-3 px-3 py-3 text-left transition-colors"
        :class="[rowClick ? 'cursor-pointer' : '', rowClass?.(item)]"
        :style="{ gridTemplateColumns }"
        :role="rowClick ? 'button' : undefined"
        :tabindex="rowClick ? 0 : undefined"
        @click="rowClick?.(item)"
        @keydown="onRowKeydown($event, item)"
      >
        <div v-if="selectable" class="flex items-center" @click.stop>
          <input
            type="checkbox"
            class="size-3.5 accent-foreground"
            :aria-label="t('action.selectRow')"
            :checked="selectedSet.has(keyOf(item, index))"
            @change="toggleRow(item, index)"
          />
        </div>
        <div
          v-for="column in columns"
          :key="column.key"
          class="min-w-0 text-[13.5px]"
          :class="[column.cellClass, alignClass(column)]"
        >
          <VNodeContent v-if="column.cell" :node="column.cell(item, index)" />
          <template v-else>{{ item[column.key] }}</template>
        </div>
      </div>
    </template>

    <template v-if="$slots.empty" #empty><slot name="empty" /></template>
    <template v-if="$slots['pager-left']" #pager-left><slot name="pager-left" /></template>
  </LineList>
</template>
