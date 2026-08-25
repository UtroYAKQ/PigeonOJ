<script setup lang="ts">
import type { DataTableColumns } from 'naive-ui'

defineProps<{
  columns: DataTableColumns<any>
  data: any[]
  loading?: boolean
  /** 分页总数 */
  total: number
  /** 当前页码 v-model */
  page: number
  /** 每页条数 v-model */
  pageSize: number
  /** 可选每页条数 */
  pageSizes?: number[]
  /** 空状态描述文案 */
  emptyText?: string
  /** n-data-table 额外属性（camelCase） */
  tableProps?: Record<string, any>
}>()

defineEmits<{
  'update:page': [value: number]
  'update:pageSize': [value: number]
}>()
</script>

<template>
  <n-data-table
    v-if="loading || data.length"
    class="table-fill"
    :columns="columns"
    :data="data"
    :loading="loading"
    :bordered="false"
    :bottom-bordered="false"
    v-bind="tableProps"
  />
  <div v-else class="table-fill-empty">
    <n-empty size="large" :description="emptyText" />
  </div>

  <div class="pager">
    <slot name="pager-left" />
    <div class="pager__spacer" />
    <n-pagination
      :page="page"
      :page-size="pageSize"
      :item-count="total"
      :page-sizes="pageSizes ?? [20, 50, 100]"
      show-size-picker
      @update:page="$emit('update:page', $event)"
      @update:page-size="$emit('update:pageSize', $event)"
    />
  </div>
</template>

<style scoped>
.pager {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--app-border);
}
.pager__spacer {
  flex: 1;
}
</style>
