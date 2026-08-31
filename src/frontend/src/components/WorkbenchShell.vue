<script setup lang="ts">
/**
 * 表格工作台外壳（docs/frontend.md「表格工作台」）：
 * page-fill 视口锁定 + 无边框卡片，头部可选（title / header / header-extra），
 * 内容区由页面组装（SearchFilterBar / tabs + PaginatedDataTable 或自定义填充区）。
 * 高度链（卡片、内容区 flex 伸缩）由 assets/main.css 的 .page-fill 规则承载。
 */
defineProps<{ title?: string }>()
</script>

<template>
  <div class="page-fill">
    <n-card :bordered="false">
      <template v-if="title || $slots.header" #header>
        <slot name="header">{{ title }}</slot>
      </template>
      <template v-if="$slots['header-extra']" #header-extra>
        <slot name="header-extra" />
      </template>
      <slot />
    </n-card>
  </div>
</template>
