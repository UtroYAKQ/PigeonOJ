<script setup lang="ts">
/**
 * 系统配置左侧分类导航：桌面端纵向列表，窄屏横向滚动标签。
 */
import { ChevronRight } from '@lucide/vue'

import type { ConfigCategory } from '@/types'

defineProps<{
  categories: Array<{ value: ConfigCategory; label: string }>
  modelValue: ConfigCategory
}>()

const emit = defineEmits<{ 'update:modelValue': [value: ConfigCategory] }>()
</script>

<template>
  <nav
    class="flex gap-1 overflow-x-auto border-b border-border pb-2 lg:sticky lg:top-3 lg:flex-col lg:overflow-visible lg:border-b-0 lg:border-r lg:pb-0 lg:pr-4"
  >
    <button
      v-for="item in categories"
      :key="item.value"
      type="button"
      class="flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-left text-[13px] transition-colors lg:w-full"
      :class="
        item.value === modelValue
          ? 'bg-muted font-medium text-foreground'
          : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
      "
      :aria-current="item.value === modelValue ? 'true' : undefined"
      @click="emit('update:modelValue', item.value)"
    >
      <span class="truncate">{{ item.label }}</span>
      <ChevronRight
        v-if="item.value === modelValue"
        class="ml-auto hidden size-3.5 shrink-0 text-muted-foreground lg:block"
      />
    </button>
  </nav>
</template>
