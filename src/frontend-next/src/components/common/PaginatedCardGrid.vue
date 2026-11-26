<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import EmptyState from '@/components/common/EmptyState.vue'
import Pager from '@/components/common/Pager.vue'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * 卡片列表壳：与 PaginatedTable 对位的前台浏览布局。
 * 只负责响应式网格、骨架 / 空态 / 分页；卡片内容由调用方经默认插槽填充，
 * 领域卡片统一使用 components/common/EntityCard.vue 作为可点击外壳。
 */
withDefaults(
  defineProps<{
    items: any[]
    loading?: boolean
    total: number
    page: number
    pageSize: number
    pageSizes?: number[]
    showSizePicker?: boolean
    emptyText?: string
    skeletonCount?: number
  }>(),
  { loading: false, skeletonCount: 6 },
)

const emit = defineEmits<{
  'update:page': [value: number]
  'update:pageSize': [value: number]
}>()

const { t } = useI18n()
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3">
    <div class="flex min-h-0 flex-1 flex-col overflow-auto pr-0.5">
      <div
        v-if="loading"
        class="grid shrink-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
      >
        <Card
          v-for="index in skeletonCount"
          :key="`skeleton-${index}`"
          class="flex min-h-[172px] flex-col p-4"
        >
          <div class="flex items-center gap-3">
            <Skeleton class="size-10 shrink-0 rounded-lg" />
            <div class="min-w-0 flex-1 space-y-2">
              <Skeleton class="h-3.5 w-1/2" />
              <Skeleton class="h-3 w-1/3" />
            </div>
          </div>
          <div class="mt-4 space-y-2">
            <Skeleton class="h-3 w-full" />
            <Skeleton class="h-3 w-2/3" />
          </div>
          <div class="mt-auto flex gap-3 pt-4">
            <Skeleton class="h-3 w-16" />
            <Skeleton class="h-3 w-24" />
          </div>
        </Card>
      </div>

      <div
        v-else-if="items.length"
        class="grid shrink-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
      >
        <slot v-for="(item, index) in items" :key="index" :item="item" :index="index" />
      </div>

      <div v-else class="flex min-h-[280px] flex-1 items-center justify-center">
        <slot name="empty">
          <EmptyState :text="emptyText ?? t('common.noData')" />
        </slot>
      </div>
    </div>

    <div class="shrink-0 px-1">
      <Pager
        :page="page"
        :page-size="pageSize"
        :total="total"
        :page-sizes="pageSizes"
        :show-size-picker="showSizePicker"
        @update:page="emit('update:page', $event)"
        @update:page-size="emit('update:pageSize', $event)"
      >
        <template #left>
          <slot name="pager-left">
            <span class="tabular-nums">{{ t('app.totalItems', { count: total }) }}</span>
          </slot>
        </template>
      </Pager>
    </div>
  </div>
</template>
