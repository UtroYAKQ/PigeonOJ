<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import EmptyState from '@/components/common/EmptyState.vue'
import Pager from '@/components/common/Pager.vue'
import VNodeContent from '@/components/common/VNodeContent'
import type { AppTableColumn } from '@/components/common/table-types'
import { Checkbox } from '@/components/ui/checkbox'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

/**
 * 列驱动的数据表格：由 AppTableColumn 生成 shadcn Table 的表头与单元格。
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


const effectiveMinWidth = computed(() => props.minWidth ?? '640px')

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

function onToggleAll(value: boolean | 'indeterminate'): void {
  toggleAll(value === true)
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

/** 固定像素 / 百分比宽度落到 colgroup；弹性宽度（1fr / minmax）交给 table-fixed 均分 */
function colWidth(column: AppTableColumn<any>): string | undefined {
  const width = column.width
  if (!width || /fr\b/.test(width) || width.includes('minmax')) return undefined
  return width
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <div
      class="flex min-h-0 flex-1 flex-col overflow-auto [&_[data-slot=table-container]]:overflow-visible"
    >
      <Table
        class="table-fixed"
        :style="{ minWidth: effectiveMinWidth }"
      >
        <colgroup>
          <col v-if="selectable" style="width: 40px" />
          <col v-for="column in columns" :key="column.key" :style="{ width: colWidth(column) }" />
        </colgroup>

        <TableHeader class="sticky top-0 z-10 bg-background">
          <TableRow class="hover:bg-transparent">
            <TableHead v-if="selectable" class="w-10">
              <Checkbox
                :aria-label="t('action.selectAll')"
                :model-value="someSelected ? 'indeterminate' : allSelected"
                @update:model-value="onToggleAll"
              />
            </TableHead>
            <TableHead
              v-for="column in columns"
              :key="column.key"
              :class="[column.headerClass, alignClass(column), 'px-3 text-xs']"
            >
              {{ column.title }}
            </TableHead>
          </TableRow>
        </TableHeader>

        <TableBody>
          <template v-if="loading">
            <TableRow
              v-for="index in skeletonCount ?? 6"
              :key="`skeleton-${index}`"
              class="hover:bg-transparent"
            >
              <TableCell v-if="selectable">
                <Skeleton class="size-3.5" />
              </TableCell>
              <TableCell v-for="column in columns" :key="column.key" class="px-3 py-4">
                <Skeleton class="h-3.5 w-full max-w-[160px]" />
              </TableCell>
            </TableRow>
          </template>

          <template v-else-if="items.length">
            <TableRow
              v-for="(item, index) in items"
              :key="keyOf(item, index)"
              :class="[rowClick ? 'cursor-pointer' : '', rowClass?.(item)]"
              :role="rowClick ? 'button' : undefined"
              :tabindex="rowClick ? 0 : undefined"
              @click="rowClick?.(item)"
              @keydown="onRowKeydown($event, item)"
            >
              <TableCell v-if="selectable" class="w-10" @click.stop>
                <Checkbox
                  :aria-label="t('action.selectRow')"
                  :model-value="selectedSet.has(keyOf(item, index))"
                  @update:model-value="toggleRow(item, index)"
                />
              </TableCell>
              <TableCell
                v-for="column in columns"
                :key="column.key"
                :class="[column.cellClass, alignClass(column), 'overflow-hidden text-[13.5px] text-ellipsis px-3']"
              >
                <VNodeContent v-if="column.cell" :node="column.cell(item, index)" />
                <template v-else>{{ item[column.key] }}</template>
              </TableCell>
            </TableRow>
          </template>

          </TableBody>
      </Table>

      <div
        v-if="!loading && !items.length"
        class="grid min-h-[240px] flex-1 place-items-center px-4"
      >
        <slot name="empty">
          <EmptyState :text="emptyText ?? t('common.noData')" />
        </slot>
      </div>
    </div>

    <div v-if="showPager" class="shrink-0 border-t border-border pt-3">
      <Pager
        :page="page ?? 1"
        :page-size="pageSize ?? items.length"
        :total="total ?? items.length"
        :page-sizes="pageSizes"
        :show-size-picker="showSizePicker"
        @update:page="emit('update:page', $event)"
        @update:page-size="emit('update:pageSize', $event)"
      >
        <template #left>
          <slot name="pager-left">
            <span class="tabular-nums">{{ t('app.totalItems', { count: total ?? items.length }) }}</span>
          </slot>
        </template>
      </Pager>
    </div>
  </div>
</template>