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
  <!-- v-show 而非 v-if：多根 fragment 内分支切换会做锚点增删，在真实浏览器中
       触发 Vue patch 的 insertBefore(null) 崩溃（渲染器带伤 → 整页卡死）。
       DOM 恒定、仅切显示，加载态由表格自身遮罩表达 -->
  <n-data-table
    v-show="loading || data.length"
    class="table-fill"
    :columns="columns"
    :data="data"
    :loading="loading"
    :bordered="false"
    :bottom-bordered="false"
    v-bind="tableProps"
  />
  <div v-show="!loading && !data.length" class="table-fill-empty">
    <n-empty size="large" :description="emptyText" />
  </div>

  <div class="pager">
    <slot name="pager-left" />
    <div class="pager__spacer" />
    <!-- :key 强制整树重建：naive-ui Pagination 页码项增量 patch 存在
         insertBefore(null) 崩溃（跨大页码跳转触发，等上游发版后移除） -->
    <n-pagination
      :key="`${page}:${pageSize}`"
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
