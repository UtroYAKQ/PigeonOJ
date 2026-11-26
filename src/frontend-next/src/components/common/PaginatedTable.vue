<script setup lang="ts">
import ColumnLineList from '@/components/common/ColumnLineList.vue'
import type { AppTableColumn } from '@/components/common/table-types'

withDefaults(
  defineProps<{
    columns: AppTableColumn<any>[]
    data: any[]
    loading?: boolean
    total: number
    page: number
    pageSize: number
    pageSizes?: number[]
    showSizePicker?: boolean
    emptyText?: string
    rowClick?: (row: any) => void
    rowClass?: (row: any) => string
    selectable?: boolean
    rowKey?: (row: any) => string | number
    selectedKeys?: Array<string | number>
  }>(),
  { selectedKeys: () => [] },
)

const emit = defineEmits<{
  'update:page': [value: number]
  'update:pageSize': [value: number]
  'update:selectedKeys': [value: Array<string | number>]
}>()
</script>

<template>
  <ColumnLineList
    v-bind="$props"
    :items="data"
    :show-pager="true"
    @update:page="emit('update:page', $event)"
    @update:page-size="emit('update:pageSize', $event)"
    @update:selected-keys="emit('update:selectedKeys', $event)"
  >
    <template v-if="$slots.empty" #empty><slot name="empty" /></template>
    <template v-if="$slots['pager-left']" #pager-left><slot name="pager-left" /></template>
  </ColumnLineList>
</template>
