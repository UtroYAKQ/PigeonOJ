<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import { useMediaQuery } from '@vueuse/core'
import { useI18n } from 'vue-i18n'

import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const props = withDefaults(
  defineProps<{
    page: number
    pageSize: number
    total: number
    pageSizes?: number[]
    showSizePicker?: boolean
  }>(),
  { pageSizes: () => [20, 50, 100], showSizePicker: false },
)

const emit = defineEmits<{
  'update:page': [value: number]
  'update:pageSize': [value: number]
}>()

const { t } = useI18n()
/** 窄屏收缩页码窗口，避免 11 个控件撑破 320~375px 视口 */
const isNarrow = useMediaQuery('(max-width: 640px)')

const sizeValue = computed({
  get: () => String(props.pageSize),
  set: (value: string) => {
    emit('update:pageSize', Number(value))
  },
})

const pageValue = computed({
  get: () => props.page,
  set: (value: number) => {
    if (value !== props.page) emit('update:page', value)
  },
})
</script>

<template>
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="flex items-center gap-2 text-xs text-muted-foreground">
      <slot name="left">
        <span class="tabular-nums">{{ t('app.totalItems', { count: total }) }}</span>
      </slot>
    </div>

    <div class="flex min-w-0 max-w-full flex-wrap items-center gap-3">
      <div v-if="showSizePicker" class="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span>{{ t('app.perPage') }}</span>
        <Select v-model="sizeValue">
          <SelectTrigger size="sm" class="h-8 w-[74px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="size in pageSizes" :key="size" :value="String(size)">
              {{ size }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Pagination
        v-model:page="pageValue"
        :total="total"
        :items-per-page="pageSize"
        :sibling-count="isNarrow ? 0 : 1"
        show-edges
        class="w-auto justify-end"
      >
        <PaginationContent v-slot="{ items }">
          <PaginationPrevious :aria-label="t('action.prevPage')">
            <ChevronLeft class="size-4" />
          </PaginationPrevious>
          <template v-for="(item, index) in items" :key="`${item.type}-${index}`">
            <PaginationEllipsis v-if="item.type === 'ellipsis'" />
            <PaginationItem v-else :value="item.value" :is-active="item.value === page">
              {{ item.value }}
            </PaginationItem>
          </template>
          <PaginationNext :aria-label="t('action.nextPage')">
            <ChevronRight class="size-4" />
          </PaginationNext>
        </PaginationContent>
      </Pagination>
    </div>
  </div>
</template>
