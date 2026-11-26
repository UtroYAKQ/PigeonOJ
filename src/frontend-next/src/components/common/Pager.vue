<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import { useI18n } from 'vue-i18n'

import { Button } from '@/components/ui/button'
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

const pageCount = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

type PageToken = number | '…'

/** 页码窗口：1 … 当前±1 … 末页，避免页码项无限增长 */
const tokens = computed<PageToken[]>(() => {
  const count = pageCount.value
  const current = props.page
  if (count <= 7) return Array.from({ length: count }, (_, index) => index + 1)
  const pages = new Set<number>([1, count, current - 1, current, current + 1])
  if (current <= 3) [2, 3, 4].forEach((page) => pages.add(page))
  if (current >= count - 2) [count - 3, count - 2, count - 1].forEach((page) => pages.add(page))
  const sorted = [...pages].filter((page) => page >= 1 && page <= count).sort((a, b) => a - b)
  const result: PageToken[] = []
  sorted.forEach((page, index) => {
    if (index > 0 && page - sorted[index - 1]! > 1) result.push('…')
    result.push(page)
  })
  return result
})

const sizeValue = computed({
  get: () => String(props.pageSize),
  set: (value: string) => {
    emit('update:pageSize', Number(value))
  },
})

function go(page: number): void {
  if (page < 1 || page > pageCount.value || page === props.page) return
  emit('update:page', page)
}
</script>

<template>
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="flex items-center gap-2 text-xs text-muted-foreground">
      <slot name="left">
        <span class="tabular-nums">{{ t('app.totalItems', { count: total }) }}</span>
      </slot>
    </div>

    <div class="flex flex-wrap items-center gap-3">
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

      <div class="flex items-center gap-1">
        <Button
          variant="outline"
          size="icon-sm"
          class="size-8"
          :disabled="page <= 1"
          :aria-label="t('action.prevPage')"
          @click="go(page - 1)"
        >
          <ChevronLeft class="size-4" />
        </Button>
        <template v-for="(token, index) in tokens" :key="`${token}-${index}`">
          <span
            v-if="token === '…'"
            class="grid size-8 place-items-center text-xs text-muted-foreground"
          >
            …
          </span>
          <Button
            v-else
            :variant="token === page ? 'default' : 'ghost'"
            size="icon-sm"
            class="size-8 text-xs tabular-nums"
            :class="token === page ? '' : 'text-muted-foreground'"
            :aria-current="token === page ? 'page' : undefined"
            @click="go(token)"
          >
            {{ token }}
          </Button>
        </template>
        <Button
          variant="outline"
          size="icon-sm"
          class="size-8"
          :disabled="page >= pageCount"
          :aria-label="t('action.nextPage')"
          @click="go(page + 1)"
        >
          <ChevronRight class="size-4" />
        </Button>
      </div>
    </div>
  </div>
</template>
