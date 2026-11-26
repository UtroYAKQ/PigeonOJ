<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import EmptyState from '@/components/common/EmptyState.vue'
import Pager from '@/components/common/Pager.vue'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * 无框横线列表壳（Naive UI n-list 风格）：表头 + 逐行分隔线，无卡片外框。
 * 只管布局、骨架 / 空态和分页；行内容由调用方经 #item 插槽填充。
 * #raw 供仍需要表格语义的列表（如多列数值表）整块接管内容区。
 */
withDefaults(
  defineProps<{
    items: any[]
    loading?: boolean
    total?: number
    page?: number
    pageSize?: number
    pageSizes?: number[]
    showSizePicker?: boolean
    emptyText?: string
    skeletonCount?: number
    getKey?: (item: any, index: number) => string | number
    minWidth?: string
    showPager?: boolean
  }>(),
  { loading: false, total: 0, page: 1, pageSize: 20, skeletonCount: 6, showPager: false },
)

const emit = defineEmits<{
  'update:page': [value: number]
  'update:pageSize': [value: number]
}>()

const { t } = useI18n()
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <div class="min-h-0 flex-1 overflow-auto">
      <div class="flex min-h-full flex-col" :style="minWidth ? { minWidth } : undefined">
        <template v-if="$slots.raw">
          <slot name="raw" />
        </template>
        <template v-else>
          <div v-if="$slots.header" class="sticky top-0 z-10 border-b border-border bg-background">
            <slot name="header" />
          </div>

          <div v-if="loading" class="animate-pulse divide-y divide-border">
            <slot name="skeleton">
              <div
                v-for="index in skeletonCount"
                :key="`skeleton-${index}`"
                class="flex items-center gap-4 px-3 py-4"
              >
                <Skeleton class="h-3.5 w-1/3" />
                <Skeleton class="h-3.5 w-1/4" />
              </div>
            </slot>
          </div>

          <div v-else-if="items.length" class="divide-y divide-border">
            <div
              v-for="(item, index) in items"
              :key="getKey ? getKey(item, index) : index"
              class="transition-colors hover:bg-muted/40 focus-within:bg-muted/40"
            >
              <slot name="item" :item="item" :index="index" />
            </div>
          </div>

          <div v-else class="grid min-h-[240px] flex-1 place-items-center">
            <slot name="empty">
              <EmptyState :text="emptyText ?? t('common.noData')" />
            </slot>
          </div>
        </template>
      </div>
    </div>

    <div v-if="showPager" class="shrink-0 border-t border-border pt-3">
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
